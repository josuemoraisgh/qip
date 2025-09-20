# -*- coding: utf-8 -*-
r"""
Treino iterativo com logs de melhor até agora, warm-start e knowledge distillation.
Na primeira iteração pode usar um modelo pronto como 'best' inicial (--best-init).
Pressione 'q' para parar a qualquer momento.

Exemplo:
  python 07_modelo_discriminativo_ensemble_fixed2.py ^
      --excel "C:/SourceCode/qip/python/banco_dados.xlsx" ^
      --sheet-pont "Pontuacao" --top3-threshold 0.85 --distill ^
      --best-init "C:/SourceCode/qip/saida_modelo/best_model"
"""

import os
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight

# Keras (compatível com TF >= 2.13)
try:
    import keras
    from keras import layers, regularizers
except ImportError:
    from tensorflow import keras
    from tensorflow.keras import layers, regularizers

import tensorflow as tf


# ========= CLI =========
def parse_args():
    ap = argparse.ArgumentParser(description="Treino iterativo com warm-start e distillation (+best-init).")

    ap.add_argument("--excel", type=str, default=r"C:/SourceCode/qip/python/banco_dados.xlsx",
                    help="Caminho do Excel.")
    ap.add_argument("--sheet-dados", type=str, default="TDados_Clean",
                    help="Aba de dados (fixa por requisito).")
    ap.add_argument("--sheet-pont", type=str, default=None,
                    help="Aba Pontuação (ex.: 'Pontuação'/'Pontuacao'). Se None, tento detectar.")
    ap.add_argument("--target", type=str, default="A",
                    help="Alvo: nome de coluna OU letra Excel ('A' = 1ª coluna).")
    ap.add_argument("--sem-label", type=str, default="Sem Transtorno",
                    help="Rótulo excluído do treino/validação.")
    ap.add_argument("--top3-threshold", type=float, default=0.99,
                    help="Critério de parada (Top-3 em validação).")
    ap.add_argument("--max-trials", type=int, default=300,
                    help="Máximo de tentativas.")
    ap.add_argument("--outdir", type=str, default=r"C:/SourceCode/qip/saida_modelo",
                    help="Diretório de saída.")

    # knobs do loop (padrão True com BooleanOptionalAction)
    ap.add_argument(
        "--distill",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Ativa knowledge distillation quando houver professor (padrão: %(default)s). Use --no-distill para desligar."
    )
    ap.add_argument("--temperature", type=float, default=3.0,
                    help="Temperatura da distillation (T>1 suaviza).")
    ap.add_argument("--alpha", type=float, default=0.7,
                    help="Peso da loss supervisionada (0..1) na distillation.")

    # best inicial
    ap.add_argument("--best-init", type=str, default="C:/SourceCode/qip/saida_modelo/best_model",
                    help="Caminho de um best inicial (diretório com model.keras, scaler.pkl, features.json, classes.json; "
                         "ou arquivo .keras/.h5). Se compatível, é usado como referência/teacher na 1ª iteração.")
    return ap.parse_args()


# ========= Utils básicos =========
def pick_sheet(xls: pd.ExcelFile, prefer_name: str | None, candidates=None):
    if prefer_name and prefer_name in xls.sheet_names:
        return prefer_name
    if candidates is None:
        candidates = []
    def _n(s): return s.lower().strip()
    names_n = [_n(s) for s in xls.sheet_names]
    for cand in candidates:
        if cand in names_n:
            return xls.sheet_names[names_n.index(cand)]
    return xls.sheet_names[0]


def excel_col_letter_to_index(letter: str) -> int:
    s = letter.strip().upper()
    val = 0
    for ch in s:
        if not ('A' <= ch <= 'Z'):
            raise ValueError(f"Letra inválida: {letter}")
        val = val * 26 + (ord(ch) - ord('A') + 1)
    return val - 1


def resolve_target_series(df: pd.DataFrame, target_spec: str) -> tuple[pd.Series, str]:
    if target_spec in df.columns:
        return df[target_spec], target_spec
    try:
        idx = excel_col_letter_to_index(target_spec)
        if 0 <= idx < df.shape[1]:
            return df.iloc[:, idx], df.columns[idx]
    except Exception:
        pass
    raise ValueError(f"Alvo '{target_spec}' não existe como nome/letra. Colunas: {list(df.columns)}")


def select_feature_columns(df_features: pd.DataFrame, df_pont: pd.DataFrame | None, target_name: str):
    """
    Entra como feature a coluna da TDados_Clean cuja homônima na Pontuação NÃO seja toda zero.
    Fallback: colunas numéricas de TDados_Clean (exceto o alvo).
    Remove colunas com variância ~ 0.
    """
    sel = []
    if df_pont is not None:
        common = [c for c in df_features.columns if c in df_pont.columns and c != target_name]
        for c in common:
            s = pd.to_numeric(df_pont[c], errors="coerce").fillna(0).to_numpy()
            if (s != 0).any():  # não é toda zero
                sel.append(c)
    if not sel:
        sel = [c for c in df_features.select_dtypes(include=[np.number]).columns if c != target_name]

    good = []
    for c in sel:
        arr = pd.to_numeric(df_features[c], errors="coerce").values
        if np.nanstd(arr) > 0:
            good.append(c)
    return good if good else sel


def split_two_thirds_one_third_per_class(X, y, random_state=42, return_indices=False):
    """
    Split por classe: n>=3 -> ~1/3 validação; n<3 -> tudo treino.
    Se return_indices=True, também retorna (train_idx, val_idx).
    """
    rng = np.random.default_rng(random_state)
    X = np.asarray(X)
    y = np.asarray(y)
    classes, y_idx = np.unique(y, return_inverse=True)
    idxs = np.arange(len(y))
    train_idx_all, val_idx_all = [], []
    for ci, _ in enumerate(classes):
        c_idx = idxs[y_idx == ci]
        rng.shuffle(c_idx)
        n = len(c_idx)
        if n >= 3:
            n_val = max(1, int(round(n/3)))
            val_idx = c_idx[:n_val]
            train_idx = c_idx[n_val:]
        else:
            val_idx = np.array([], dtype=int)
            train_idx = c_idx
        train_idx_all.append(train_idx)
        val_idx_all.append(val_idx)
    train_idx = np.concatenate(train_idx_all) if train_idx_all else np.array([], dtype=int)
    val_idx = np.concatenate([v for v in val_idx_all if v.size>0]) if any(v.size>0 for v in val_idx_all) else np.array([], dtype=int)
    X_train, y_train = X[train_idx], y[train_idx]
    X_val   = X[val_idx] if val_idx.size>0 else None
    y_val   = y[val_idx] if val_idx.size>0 else None
    if return_indices:
        return X_train, X_val, y_train, y_val, train_idx, val_idx
    return X_train, X_val, y_train, y_val


# tecla 'q'
try:
    import msvcrt
    def is_quit_pressed():
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch.lower() == 'q'
        return False
except Exception:
    def is_quit_pressed(): return False


class QuitOnQCallback(keras.callbacks.Callback):
    def on_train_batch_end(self, batch, logs=None):
        if is_quit_pressed():
            print("\n[INFO] 'q' pressionada — parando este treino.")
            self.model.stop_training = True


class BestSoFarPrinter(keras.callbacks.Callback):
    def __init__(self, get_best_callable):
        super().__init__()
        self._get_best = get_best_callable  # função que retorna best_val_top3
    def on_epoch_end(self, epoch, logs=None):
        if logs is None: logs = {}
        best_so_far = self._get_best()
        cur = logs.get("val_top3", None)
        if cur is not None:
            print(f"[epoch {epoch+1:03d}] val_top3={cur:.4f} | best_so_far={best_so_far:.4f}")


# ========= Modelo / treino =========
def build_model(input_dim, n_classes, hidden=(128,64), dropout=0.25, l2=0.0, lr=1e-3):
    reg = regularizers.l2(l2) if l2 and l2>0 else None
    inputs = keras.Input(shape=(input_dim,), name="features")
    x = layers.Dense(hidden[0], activation="relu", kernel_initializer="he_normal",
                     kernel_regularizer=reg)(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout)(x)
    if len(hidden) > 1:
        x = layers.Dense(hidden[1], activation="relu", kernel_initializer="he_normal",
                         kernel_regularizer=reg)(x)
        x = layers.BatchNormalization()(x)
        x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(n_classes, activation="softmax", name="probs")(x)
    model = keras.Model(inputs, outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(lr),
        loss="categorical_crossentropy",  # usamos one-hot
        metrics=["accuracy", keras.metrics.TopKCategoricalAccuracy(k=3, name="top3")]
    )
    return model


# Distiller com entradas separadas (aluno/professor) e suporte a sample_weight
class Distiller(keras.Model):
    def __init__(self, student, teacher, temperature=3.0, alpha=0.7, teacher_reorder_idx=None):
        super().__init__()
        self.student = student
        self.teacher = teacher
        self.temperature = float(temperature)
        self.alpha = float(alpha)
        self.teacher_reorder_idx = None
        if teacher_reorder_idx is not None:
            self.teacher_reorder_idx = tf.convert_to_tensor(teacher_reorder_idx, dtype=tf.int32)

    def compile(self, optimizer, metrics, student_loss_fn, distillation_loss_fn):
        super().compile(optimizer=optimizer, metrics=metrics)
        self.student_loss_fn = student_loss_fn
        self.distillation_loss_fn = distillation_loss_fn

    def _split_inputs(self, x):
        # aceita x_student ou (x_student, x_teacher)
        if isinstance(x, (tuple, list)) and len(x) == 2:
            return x[0], x[1]
        return x, x

    def _unpack_data(self, data):
        """Aceita (x, y) ou (x, y, sample_weight)."""
        if isinstance(data, (tuple, list)) and len(data) == 3:
            x, y, sw = data
        else:
            x, y = data
            sw = None
        return x, y, sw

    def train_step(self, data):
        x, y, sample_weight = self._unpack_data(data)
        x_student, x_teacher = self._split_inputs(x)
        y_true = y
        teacher_pred = self.teacher(x_teacher, training=False)
        if self.teacher_reorder_idx is not None:
            teacher_pred = tf.gather(teacher_pred, self.teacher_reorder_idx, axis=-1)
        with tf.GradientTape() as tape:
            student_pred = self.student(x_student, training=True)
            # losses
            s_loss = self.student_loss_fn(y_true, student_pred, sample_weight=sample_weight)
            t_soft = tf.nn.softmax(teacher_pred / self.temperature)
            s_soft = tf.nn.softmax(student_pred / self.temperature)
            d_loss = self.distillation_loss_fn(t_soft, s_soft, sample_weight=sample_weight) * (self.temperature ** 2)
            loss = self.alpha * s_loss + (1. - self.alpha) * d_loss
        trainable_vars = self.student.trainable_variables
        grads = tape.gradient(loss, trainable_vars)
        self.optimizer.apply_gradients(zip(grads, trainable_vars))
        # métricas
        for m in self.metrics:
            try:
                m.update_state(y_true, student_pred, sample_weight=sample_weight)
            except TypeError:
                m.update_state(y_true, student_pred)
        return {"loss": loss, **{m.name: m.result() for m in self.metrics}}

    def test_step(self, data):
        x, y, sample_weight = self._unpack_data(data)
        x_student, _ = self._split_inputs(x)
        student_pred = self.student(x_student, training=False)
        s_loss = self.student_loss_fn(y, student_pred, sample_weight=sample_weight)
        for m in self.metrics:
            try:
                m.update_state(y, student_pred, sample_weight=sample_weight)
            except TypeError:
                m.update_state(y, student_pred)
        return {"loss": s_loss, **{m.name: m.result() for m in self.metrics}}


def evaluate_history(history):
    hist = history.history
    val_top3 = max(hist.get("val_top3", [0.0]))
    train_top3 = max(hist.get("top3", [0.0]))
    return float(train_top3), float(val_top3)


def save_best(model, scaler, classes, features, outdir, score, cfg, meta_extra=None):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(outdir) / f"best_{score:.4f}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    model.save(run_dir / "model.keras")
    # salvar scaler e metadados
    import pickle
    with open(run_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(run_dir / "classes.json", "w", encoding="utf-8") as f:
        json.dump(list(classes), f, ensure_ascii=False, indent=2)
    with open(run_dir / "features.json", "w", encoding="utf-8") as f:
        json.dump(list(features), f, ensure_ascii=False, indent=2)
    meta = {"best_val_top3": score, "config": cfg}
    if meta_extra: meta.update(meta_extra)
    with open(run_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    # atualizar atalho "best_model"
    best_link = Path(outdir) / "best_model"
    if best_link.exists():
        shutil.rmtree(best_link, ignore_errors=True)
    shutil.copytree(run_dir, best_link)
    return run_dir


# ========= Carregar 'best-init' =========
def load_model_bundle(best_path: Path):
    """
    Aceita:
      - diretório contendo: model.keras, scaler.pkl, features.json, classes.json
      - arquivo .keras / .h5 (apenas modelo; sem scaler/features/classes)
    Retorna dict com chaves: model, scaler (ou None), features (ou None), classes (np.array ou None), dir (Path ou None)
    """
    best_path = Path(best_path)
    bundle = {"model": None, "scaler": None, "features": None, "classes": None, "dir": None}
    if best_path.is_dir():
        model_file = best_path / "model.keras"
        if not model_file.exists():
            # tentar .h5
            h5s = list(best_path.glob("*.h5"))
            if h5s:
                model_file = h5s[0]
        bundle["model"] = keras.models.load_model(model_file)
        # opcionais
        import pickle
        scaler_pkl = best_path / "scaler.pkl"
        if scaler_pkl.exists():
            with open(scaler_pkl, "rb") as f:
                bundle["scaler"] = pickle.load(f)
        feats_json = best_path / "features.json"
        if feats_json.exists():
            with open(feats_json, "r", encoding="utf-8") as f:
                bundle["features"] = json.load(f)
        classes_json = best_path / "classes.json"
        if classes_json.exists():
            with open(classes_json, "r", encoding="utf-8") as f:
                bundle["classes"] = np.array(json.load(f))
        bundle["dir"] = best_path
        return bundle
    else:
        # arquivo de modelo
        bundle["model"] = keras.models.load_model(best_path)
        return bundle


def compute_top3_acc_from_probs(proba, classes_order, y_true_text):
    """
    Calcula top-3 accuracy dado probs (n, C), ordem de classes (array de strings),
    e rótulos verdadeiros (array de strings).
    """
    classes_order = np.array(classes_order)
    idx = np.argsort(-proba, axis=1)[:, :3]
    top3_labels = classes_order[idx]
    y_true_text = np.asarray(y_true_text)
    hits = np.array([y_true_text[i] in top3_labels[i] for i in range(len(y_true_text))], dtype=np.float32)
    return float(hits.mean()) if len(hits) else 0.0


def same_arch(cfg1, cfg2):
    """Define 'mesma arquitetura' para warm-start (camadas e dropout iguais)."""
    return cfg1["hidden"] == cfg2["hidden"] and abs(cfg1["dropout"] - cfg2["dropout"]) < 1e-9 and abs(cfg1["l2"] - cfg2["l2"]) < 1e-12


# ========= Main =========
def main():
    args = parse_args()
    EXCEL_PATH = Path(args.excel)
    OUT_DIR = Path(args.outdir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {EXCEL_PATH}")

    # --- Ler dados
    xls = pd.ExcelFile(EXCEL_PATH)
    tdados = pick_sheet(xls, args.sheet_dados, [s.lower() for s in ["tdados_clean","tdados","dados_clean","dados"]])
    pont = pick_sheet(xls, args.sheet_pont, [s.lower() for s in ["pontuação","pontuacao","pont","scores"]]) if args.sheet_pont is None else args.sheet_pont

    df_feat = pd.read_excel(EXCEL_PATH, sheet_name=tdados)
    df_pont = pd.read_excel(EXCEL_PATH, sheet_name=pont) if isinstance(pont, str) and (pont in xls.sheet_names) else None

    y_series, target_name = resolve_target_series(df_feat, args.target)
    y_all = y_series.astype(str).fillna("")
    feature_cols = select_feature_columns(df_feat, df_pont, target_name)
    if not feature_cols:
        raise RuntimeError("Nenhuma feature válida encontrada.")
    X_all = df_feat[feature_cols].copy()
    for c in feature_cols:
        col = pd.to_numeric(X_all[c], errors="coerce")
        X_all[c] = col.fillna(col.median())

    # excluir 'Sem Transtorno'
    mask_sem = y_all.str.strip().str.lower() == args.sem_label.lower()
    df_labeled = df_feat.loc[~mask_sem].reset_index(drop=True)  # <<< robusto para .iloc
    X_labeled = X_all.loc[~mask_sem].to_numpy()
    y_labeled = y_all.loc[~mask_sem].to_numpy()
    if X_labeled.shape[0] == 0:
        raise RuntimeError("Sem dados rotulados após remover 'Sem Transtorno'.")
    classes_unique = np.unique(y_labeled)
    if classes_unique.size < 2:
        raise RuntimeError(f"É preciso ≥2 classes. Encontradas: {classes_unique.tolist()}")

    # split & scaler (com índices relativos ao conjunto rotulado)
    X_train, X_val, y_train_txt, y_val_txt, train_idx, val_idx = split_two_thirds_one_third_per_class(
        X_labeled, y_labeled, random_state=42, return_indices=True
    )
    use_internal_val = X_val is None
    classes_unique = np.unique(y_labeled)
    cls_to_idx = {c: i for i, c in enumerate(classes_unique)}
    y_train_idx = np.array([cls_to_idx[c] for c in y_train_txt], dtype=np.int64)
    if not use_internal_val:
        y_val_idx = np.array([cls_to_idx[c] for c in y_val_txt], dtype=np.int64)

    scaler = StandardScaler()
    X_train_student = scaler.fit_transform(X_train)
    if not use_internal_val:
        X_val_student = scaler.transform(X_val)

    # ======== BEST-INIT (opcional) ========
    teacher_bundle = None
    teacher_reorder_idx = None
    best_val_top3 = -1.0
    best_cfg = None
    best_dir = None

    if args.best_init:
        bpath = Path(args.best_init)
        if not bpath.exists():
            print(f"[WARN] --best-init não encontrado: {bpath}")
        else:
            teacher_bundle = load_model_bundle(bpath)
            print(f"[INFO] best-init carregado de: {bpath}")
            # se houver classes no pacote, tentar alinhar classes e avaliar
            if (teacher_bundle.get("classes") is not None) and (teacher_bundle.get("features") is not None):
                classes_best = np.array(teacher_bundle["classes"])
                # mapear ordem do professor -> ordem do aluno (precisa ter as mesmas classes)
                if set(classes_best.tolist()) == set(classes_unique.tolist()):
                    label_to_teacher = {lbl: i for i, lbl in enumerate(classes_best)}
                    teacher_reorder_idx = np.array([label_to_teacher[lbl] for lbl in classes_unique], dtype=np.int32)
                    # preparar entradas do professor na validação (se houver)
                    if not use_internal_val and (teacher_bundle.get("scaler") is not None):
                        feats = teacher_bundle["features"]
                        # reconstruir X_val nas features do professor a partir do df_labeled
                        X_val_teacher_df = df_labeled.iloc[val_idx][feats].copy()
                        for c in feats:
                            X_val_teacher_df[c] = pd.to_numeric(X_val_teacher_df[c], errors="coerce").fillna(X_val_teacher_df[c].median())
                        X_val_teacher = teacher_bundle["scaler"].transform(X_val_teacher_df.to_numpy())
                        # avaliar teacher
                        proba_teacher = teacher_bundle["model"].predict(X_val_teacher, verbose=0)
                        # reordenar probs do professor para a ordem do aluno
                        proba_teacher = proba_teacher[:, teacher_reorder_idx]
                        best_val_top3 = compute_top3_acc_from_probs(proba_teacher, classes_unique, y_val_txt)
                        print(f"[INFO] best-init val_top3 (avaliado neste dataset): {best_val_top3:.4f}")
                        # marcar como 'best_dir' o caminho (se for diretório)
                        if teacher_bundle.get("dir"):
                            best_dir = teacher_bundle["dir"]
                    else:
                        print("[WARN] Não foi possível avaliar best-init (sem validação ou sem scaler/features).")
                else:
                    print("[WARN] Classes do best-init diferem das atuais — distillation e avaliação inicial desativadas.")
            else:
                print("[WARN] best-init sem features/classes — distillation desativada.")

    print(f"[INFO] Critério: val_top3 >= {args.top3_threshold:.3f} | Max trials: {args.max_trials}")
    print("[INFO] Pressione 'q' para interromper a qualquer momento.\n")

    def get_best():
        return float(max(best_val_top3, 0.0))

    # ======== LOOP DE TENTATIVAS ========
    base_cfg = {"hidden": (128, 64), "dropout": 0.25, "l2": 0.0, "lr": 1e-3, "batch": 32}
    trials = 0

    while trials < args.max_trials:
        trials += 1
        cfg = base_cfg.copy()

        n_features = X_train_student.shape[1]
        n_classes  = classes_unique.size

        print(f"===== TENTATIVA {trials} | cfg={cfg} | best_so_far={best_val_top3:.4f} =====")

        # constrói aluno
        student = build_model(n_features, n_classes,
                              hidden=cfg["hidden"], dropout=cfg["dropout"], l2=cfg["l2"], lr=cfg["lr"])

        # decide se terá professor (distillation) nesta tentativa
        use_teacher = (
            args.distill and
            (teacher_bundle is not None) and
            (teacher_bundle.get("model") is not None) and
            (teacher_reorder_idx is not None)
        )

        if use_teacher:
            # preparar entradas do professor para treino/val (mesmos índices do aluno) usando df_labeled + iloc
            feats = teacher_bundle["features"]
            if (feats is not None) and (teacher_bundle.get("scaler") is not None):
                # treino
                X_train_teacher_df = df_labeled.iloc[train_idx][feats].copy()
                for c in feats:
                    X_train_teacher_df[c] = pd.to_numeric(X_train_teacher_df[c], errors="coerce").fillna(X_train_teacher_df[c].median())
                X_train_teacher = teacher_bundle["scaler"].transform(X_train_teacher_df.to_numpy())
                # val
                if not use_internal_val:
                    X_val_teacher_df = df_labeled.iloc[val_idx][feats].copy()
                    for c in feats:
                        X_val_teacher_df[c] = pd.to_numeric(X_val_teacher_df[c], errors="coerce").fillna(X_val_teacher_df[c].median())
                    X_val_teacher = teacher_bundle["scaler"].transform(X_val_teacher_df.to_numpy())
                else:
                    X_val_teacher = None
                # construir distiller (aluno recebe X_student; teacher recebe X_teacher)
                distiller = Distiller(student=student,
                                      teacher=teacher_bundle["model"],
                                      temperature=args.temperature,
                                      alpha=args.alpha,
                                      teacher_reorder_idx=teacher_reorder_idx)
                distiller.compile(
                    optimizer=keras.optimizers.Adam(cfg["lr"]),
                    metrics=["accuracy", keras.metrics.TopKCategoricalAccuracy(k=3, name="top3")],
                    student_loss_fn=keras.losses.CategoricalCrossentropy(),
                    distillation_loss_fn=keras.losses.KLDivergence(),
                )
                model = distiller
                train_inputs = (X_train_student, X_train_teacher)
                if not use_internal_val:
                    val_inputs = (X_val_student, X_val_teacher)
                else:
                    val_inputs = None
            else:
                print("[WARN] best-init não tem scaler/features — distillation desativada nesta tentativa.")
                model = student
                train_inputs = X_train_student
                val_inputs = X_val_student if not use_internal_val else None
        else:
            model = student
            train_inputs = X_train_student
            val_inputs = X_val_student if not use_internal_val else None

        # class weights
        cw_vals = compute_class_weight("balanced", classes=np.arange(n_classes), y=y_train_idx)
        class_weight = {i: float(cw_vals[i]) for i in range(n_classes)}

        callbacks = [
            keras.callbacks.EarlyStopping(monitor="val_top3", mode="max", patience=20, restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(monitor="val_top3", mode="max", patience=8, factor=0.5, min_lr=1e-5, verbose=1),
            QuitOnQCallback(),
            BestSoFarPrinter(get_best)
        ]

        # treino
        if not use_internal_val:
            history = model.fit(
                train_inputs, tf.one_hot(y_train_idx, depth=n_classes),
                validation_data=(val_inputs, tf.one_hot(y_val_idx, depth=n_classes)),
                epochs=300, batch_size=cfg["batch"],
                class_weight=class_weight, callbacks=callbacks, verbose=2
            )
        else:
            # validação interna (funciona para múltiplas entradas se forem arrays numpy alinhados)
            history = model.fit(
                train_inputs, tf.one_hot(y_train_idx, depth=n_classes),
                validation_split=0.15,
                epochs=300, batch_size=cfg["batch"],
                class_weight=class_weight, callbacks=callbacks, verbose=2
            )

        # avaliar
        train_top3, val_top3 = evaluate_history(history)
        print(f"[RESUMO] tentativa {trials}: train_top3={train_top3:.4f} | val_top3={val_top3:.4f} | best_so_far={best_val_top3:.4f}")

        # pegar student se for distiller
        trained_model = model.student if isinstance(model, Distiller) else model

        # salvar se melhorou
        if val_top3 > best_val_top3:
            best_val_top3 = val_top3
            best_cfg = cfg.copy()
            meta_extra = {
                "tdados": tdados,
                "pont": pont if isinstance(pont,str) and (pont in xls.sheet_names) else None,
                "target_resolved": y_series.name,
                "features_count": len(feature_cols)
            }
            best_dir = save_best(trained_model, scaler, classes_unique, feature_cols, OUT_DIR, best_val_top3, best_cfg, meta_extra)
            print(f"[MELHOR] Novo melhor salvo: {best_dir}")

        # parar por critério
        if best_val_top3 >= args.top3_threshold:
            print(f"[OK] Critério atingido: best_val_top3={best_val_top3:.4f} >= {args.top3_threshold:.4f}")
            break

        if is_quit_pressed():
            print("[INFO] 'q' pressionada — encerrando tentativas.")
            break

        # decidir próxima config (simples)
        gap = train_top3 - val_top3
        if train_top3 < 0.6 and val_top3 < 0.6:
            verdict = "underfit"
        elif gap > 0.10:
            verdict = "overfit"
        else:
            verdict = "ok"

        def next_config(cfg, verdict):
            h, d, l2, lr, batch = cfg["hidden"], cfg["dropout"], cfg["l2"], cfg["lr"], cfg["batch"]
            if verdict == "underfit":
                cands = [
                    (h, d, l2, min(2e-3, lr*1.5), batch),
                    ((256,128), d, l2, lr, batch),
                    ((256,), d, l2, lr, batch),
                    ((128,64,32), d, l2, lr, batch),
                ]
            elif verdict == "overfit":
                cands = [
                    (h, min(0.6, d+0.10), max(l2, 1e-4), max(2e-4, lr/2), batch),
                    ((max(h[0]//2,64),) if len(h)==1 else (max(h[0]//2,64), max(h[1]//2,32)),
                     min(0.6, d+0.15), max(l2, 5e-4), lr, batch),
                ]
            else:  # ok
                cands = [
                    (h, d, l2, min(2e-3, lr*1.2), batch),
                    (h, min(0.5, d+0.05), l2, lr, batch),
                ]
            for hh,dd,ll,lrn,bb in cands:
                yield {"hidden": tuple(hh), "dropout": float(dd), "l2": float(ll), "lr": float(lrn), "batch": int(bb)}

        for cand in next_config(cfg, verdict):
            base_cfg = cand
            break  # pega a primeira sugestão

    # ========== Inferência com melhor ==========
    if best_dir:
        best_model = keras.models.load_model(Path(best_dir) / "model.keras")
        import pickle
        with open(Path(best_dir) / "scaler.pkl", "rb") as f:
            best_scaler = pickle.load(f)
        with open(Path(best_dir) / "features.json", "r", encoding="utf-8") as f:
            best_feats = json.load(f)
        with open(Path(best_dir) / "classes.json", "r", encoding="utf-8") as f:
            classes_best = np.array(json.load(f))

        X_all_best = df_feat[best_feats].copy()
        for c in best_feats:
            col = pd.to_numeric(X_all_best[c], errors="coerce")
            X_all_best[c] = col.fillna(col.median())
        X_all_best = best_scaler.transform(X_all_best.to_numpy())

        proba_all = best_model.predict(X_all_best, verbose=0)
        idx = np.argsort(-proba_all, axis=1)[:, :3]
        top3_lbl = classes_best[idx]
        top3_scr = np.take_along_axis(proba_all, idx, axis=1)

        result = df_feat.copy()
        for i in range(3):
            result[f"Top{i+1}_Classe"] = top3_lbl[:, i]
            result[f"Top{i+1}_Prob"]   = np.round(top3_scr[:, i], 6)

        csv_path = Path(OUT_DIR) / "classificacao_top3.csv"
        result.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[FINAL] CSV salvo em: {csv_path}")
        print(f"[FINAL] Melhor dir: {best_dir} | best_val_top3={best_val_top3:.4f}")
    else:
        print("[WARN] Nenhum modelo salvo como melhor.")
        

if __name__ == "__main__":
    main()
