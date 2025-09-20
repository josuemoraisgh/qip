# -*- coding: utf-8 -*-
"""
07_tf_autotrain_by_class.py
Autor: QIP
Descrição:
  Loop automático de treino → validação → ajuste de hiperparâmetros.
  - Busca automática de hiperparâmetros (LR, Dropout, Hidden Units, L2 da mutação, Focal Gamma, Label Smoothing)
  - Critério de parada por validação (Top-3 >= TARGET_TOP3) OU interrupção do usuário (Ctrl+C)
  - Sempre salva o melhor modelo encontrado até o momento
  - (Novo) --init_best: aceita um modelo pronto como referência inicial (avalia, usa parâmetros e pode warm-start)

Uso típico:
  py -3.12 07_tf_autotrain_by_class.py --input "c:/SourceCode/qip/python/banco_dados.xlsx" --output "c:/SourceCode/qip/python/banco_dados.xlsx"
  (opcional) --init_best "c:/SourceCode/qip/python/banco_dados_auto_model_export/best_overall.keras"

Defaults:
  target_top3 = 0.75
  max_trials  = 100
"""

import argparse, sys, math, json, os, time, random, shutil
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from pathlib import Path

# TensorFlow / Keras
import tensorflow as tf
import keras
from keras import layers

# ===================== CONFIG BASE =====================
ABA_DADOS     = "TDados_clean"
ABA_PONTOS    = "Pontuação"
COL_ALVO      = "Alvo"
ROW_START, ROW_END = 3, 13

MIN_COUNT_FOR_TRAIN = 4   # manter somente classes com >=4 amostras
TOPK = 3
THETA_MAXPROB = 0.40
ST_MIN_N_UNK = 10
ST_LOW_PERC  = 5.0
ST_USE_PSEUDO   = True
ST_ALPHA_PSEUDO = 0.35

VAL_SPLIT_SEED = 42
BATCH_SIZE = 32
PATIENCE_EARLY = 12

# ===================== FUNÇÕES AUXILIARES =====================
def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    rep = {"ã":"a","á":"a","â":"a","à":"a",
           "é":"e","ê":"e",
           "í":"i",
           "ó":"o","ô":"o","õ":"o",
           "ú":"u","ü":"u",
           "ç":"c"}
    for k,v in rep.items():
        s = s.replace(k,v)
    return s

def read_valid_classes_and_W0(path: str, aba_pont: str, feature_names: List[str]) -> Tuple[List[str], np.ndarray]:
    dfp_all = pd.read_excel(path, sheet_name=aba_pont, header=0)
    colA = pd.read_excel(path, sheet_name=aba_pont, usecols="A", header=None)
    vals = colA.iloc[ROW_START-1:ROW_END, 0].astype(object).tolist()
    classes = [str(x).strip() for x in vals if pd.notna(x) and str(x).strip() != ""]
    dfp_all = dfp_all.copy()
    if str(dfp_all.columns[0]).strip().lower() not in {"classe","class","nome","rótulo","rotulo","alvo","a"}:
        dfA = pd.read_excel(path, sheet_name=aba_pont, header=None)
        dfp_all.insert(0, "Classe", dfA.iloc[:,0])
        dfp_all.columns = [str(c) for c in dfp_all.columns]
    name_col = dfp_all.columns[0]
    dfp = dfp_all[dfp_all[name_col].astype(str).str.strip().isin(classes)].copy()

    feat_map = {c: i for i, c in enumerate(feature_names)}
    W0 = np.zeros((len(classes), len(feature_names)), dtype=float)
    for r, cname in enumerate(classes):
        row = dfp[dfp[name_col].astype(str).str.strip() == cname]
        if row.empty:
            continue
        row = row.iloc[0]
        for col in dfp_all.columns[1:]:
            if col in feat_map:
                j = feat_map[col]
                try:
                    W0[r, j] = float(row[col])
                except Exception:
                    W0[r, j] = 0.0
    return classes, W0

def make_class_weights(y: np.ndarray, classes: List[str]) -> Dict[int, float]:
    counts = Counter(y.tolist())
    w = {}
    for i, _ in enumerate(classes):
        f = max(1, counts.get(i, 0))
        wi = 1.0 / math.sqrt(f)
        w[i] = wi
    mean_w = np.mean(list(w.values()))
    w = {k: v/mean_w for k, v in w.items()}
    return w

def balance_by_upsampling(X: np.ndarray, y: np.ndarray, sw: np.ndarray, n_classes: int):
    idxs_by_c = {c: np.where(y==c)[0] for c in range(n_classes)}
    sizes = {c: idxs_by_c[c].size for c in range(n_classes) if idxs_by_c[c].size>0}
    if not sizes:
        return X, y, sw
    n_max = max(sizes.values())
    new_idx = []
    rng = np.random.default_rng(12345)
    for c, idxs in idxs_by_c.items():
        if idxs.size == 0:
            continue
        if idxs.size < n_max:
            extra = rng.choice(idxs, size=n_max - idxs.size, replace=True)
            sel = np.concatenate([idxs, extra])
        else:
            sel = idxs
        new_idx.append(sel)
    new_idx = np.concatenate(new_idx)
    rng.shuffle(new_idx)
    return X[new_idx], y[new_idx], (sw[new_idx] if sw is not None else None)

class SparseFocalLoss(keras.losses.Loss):
    """Focal loss esparsa com label smoothing manual (compatível com Keras antigos)."""
    def __init__(self, n_classes: int, alpha_per_class: np.ndarray, gamma: float = 2.0, label_smoothing: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.n_classes = int(n_classes)
        self.alpha = tf.constant(alpha_per_class.reshape((-1,)), dtype=tf.float32)
        self.gamma = float(gamma)
        self.label_smoothing = float(label_smoothing)

    def call(self, y_true, y_pred):
        y_true = tf.cast(y_true, tf.int32)
        probs = tf.nn.softmax(y_pred)
        batch_idx = tf.range(tf.shape(probs)[0])
        p_true = tf.gather_nd(probs, tf.stack([batch_idx, y_true], axis=1))
        eps = 1e-7
        if self.label_smoothing > 0.0:
            onehot = tf.one_hot(y_true, depth=self.n_classes, dtype=tf.float32)
            smooth = self.label_smoothing / float(self.n_classes)
            y_smooth = onehot * (1.0 - self.label_smoothing) + smooth
            ce = -tf.reduce_sum(y_smooth * tf.math.log(tf.clip_by_value(probs, eps, 1.0)), axis=1)
        else:
            ce = -tf.math.log(tf.clip_by_value(p_true, eps, 1.0))
        modulating = tf.pow(1.0 - tf.clip_by_value(p_true, eps, 1.0), self.gamma)
        alpha_t = tf.gather(self.alpha, y_true)
        return alpha_t * modulating * ce

class AnchoredLogits(layers.Layer):
    """Camada com logits ancorados em W0 + termo não-linear."""
    def __init__(self, W0: np.ndarray, mask_free: np.ndarray,
                 hidden_units: int = 96, dropout: float = 0.15,
                 l2_delta: float = 5e-4, l2_bias: float = 1e-4, **kwargs):
        super().__init__(**kwargs)
        self._W0_np = np.array(W0, dtype=np.float32)
        self._mask_np = np.array(mask_free, dtype=np.float32)
        self.W0 = tf.constant(self._W0_np)
        self.mask = tf.constant(self._mask_np)
        C, D = W0.shape
        self.Delta = self.add_weight(
            name="Delta", shape=(C, D),
            initializer=tf.keras.initializers.Zeros(), trainable=True,
            regularizer=keras.regularizers.l2(l2_delta)
        )
        self.bias = self.add_weight(
            name="bias", shape=(C,), initializer="zeros",
            trainable=True, regularizer=keras.regularizers.l2(l2_bias)
        )
        self.ln = layers.LayerNormalization(epsilon=1e-6)
        self.dense_h = layers.Dense(hidden_units, activation="relu")
        self.drop = layers.Dropout(dropout)
        self.V = self.add_weight(
            name="V", shape=(hidden_units, C),
            initializer=tf.keras.initializers.GlorotUniform(),
            regularizer=keras.regularizers.l2(1e-5),
            trainable=True
        )

    def call(self, inputs, training=None):
        x = inputs
        Delta_eff = self.Delta * self.mask[tf.newaxis, :]
        W_eff = self.W0 + Delta_eff
        logits_lin = tf.linalg.matmul(x, tf.transpose(W_eff)) + self.bias
        h = self.ln(x)
        h = self.dense_h(h)
        h = self.drop(h, training=training)
        logits_nl = tf.linalg.matmul(h, self.V)
        logits = logits_lin + logits_nl
        logits = tf.where(tf.math.is_finite(logits), logits, tf.zeros_like(logits))
        return logits

# ===================== SPLIT =====================
def split_by_class(y_labels: List[str], classes: List[str], allowed_toks: set, seed: int=42):
    rng = np.random.default_rng(seed)
    idx_by_c = defaultdict(list)
    out = []

    allowed_norm = set(allowed_toks)
    valid_norm = {normalize_token(c) for c in classes}

    for i, lab in enumerate(y_labels):
        tok = normalize_token(lab)
        if lab is None or lab == "" or tok in {"nao","não"} or tok not in valid_norm or tok not in allowed_norm:
            out.append(i)
            continue
        idx_by_c[tok].append(i)

    train, valid = [], []
    for tok, idxs in idx_by_c.items():
        n = len(idxs)
        idxs = np.array(idxs)
        rng.shuffle(idxs)
        cut = int(round(n * (2/3)))
        train.append(idxs[:cut])
        valid.append(idxs[cut:])

    train_idx = np.concatenate(train) if len(train)>0 else np.array([], dtype=int)
    valid_idx = np.concatenate(valid) if len(valid)>0 else np.array([], dtype=int)
    out_idx   = np.array(sorted(set(out)), dtype=int)
    return train_idx, valid_idx, out_idx

def build_export_dir(path_out: str):
    outp = Path(path_out)
    export_dir = outp.with_suffix('').as_posix() + "_auto_model_export"
    os.makedirs(export_dir, exist_ok=True)
    return export_dir

# ===================== TRIAL PARAMS =====================
@dataclass
class TrialParams:
    lr: float
    dropout: float
    hidden_units: int
    l2_delta: float
    focal_gamma: float
    label_smooth: float

# ===================== TRIAL (UMA RODADA) =====================
def build_model(W0, mask_free, D, C, params: TrialParams):
    inp = keras.Input(shape=(D,), dtype=tf.float32, name="x")
    logits = AnchoredLogits(W0=W0, mask_free=mask_free,
                            hidden_units=params.hidden_units,
                            dropout=params.dropout,
                            l2_delta=params.l2_delta, l2_bias=1e-4, name="anchored")(inp)
    model = keras.Model(inputs=inp, outputs=logits, name="AnchoredNL")
    return model

def run_trial(X, y_raw, feature_cols, classes, W0, mask_free, export_dir,
              params: TrialParams, seed=42,
              prior_weights: Optional[list]=None):
    # Map classes
    norm_to_idx = {normalize_token(c): i for i, c in enumerate(classes)}
    # Split allowed by count
    counts = {}
    for s in y_raw:
        tok = normalize_token(s)
        if s and tok not in {"nao","não"} and tok in {normalize_token(c) for c in classes}:
            counts[tok] = counts.get(tok, 0) + 1
    allowed_toks = {t for t, n in counts.items() if n >= MIN_COUNT_FOR_TRAIN}
    train_idx, valid_idx, out_idx = split_by_class(y_raw, classes, allowed_toks, seed=seed)

    def label_to_index(s: str) -> int:
        return norm_to_idx[normalize_token(s)]

    y_train = np.array([label_to_index(y_raw[i]) for i in train_idx], dtype=np.int32)
    y_valid = np.array([label_to_index(y_raw[i]) for i in valid_idx], dtype=np.int32)
    X_train = X[train_idx]; X_valid = X[valid_idx]

    # Pseudo ST
    pseudo_ST_X = np.empty((0, X.shape[1]), dtype=np.float32)
    pseudo_ST_y = np.empty((0,), dtype=np.int32)
    if ST_USE_PSEUDO and len(out_idx) >= ST_MIN_N_UNK and ("Sem Transtorno" in classes):
        sums_out = X[out_idx].sum(axis=1)
        st_thr = float(np.percentile(sums_out, ST_LOW_PERC))
        st_idx = norm_to_idx[normalize_token("Sem Transtorno")]
        pick = np.where(sums_out <= st_thr)[0]
        if pick.size > 0:
            pseudo_ST_X = X[out_idx[pick]]
            pseudo_ST_y = np.full((pick.size,), st_idx, dtype=np.int32)

    X_tr = X_train; y_tr = y_train
    if pseudo_ST_X.shape[0] > 0:
        X_tr = np.vstack([X_train, pseudo_ST_X])
        y_tr = np.concatenate([y_train, pseudo_ST_y])
        sw   = np.concatenate([np.ones(y_train.shape[0], dtype=np.float32),
                               np.full(pseudo_ST_y.shape[0], ST_ALPHA_PSEUDO, dtype=np.float32)])
    else:
        sw = np.ones(y_train.shape[0], dtype=np.float32)

    # class weights → sw_eff
    class_weight = make_class_weights(y_tr, classes)
    cw_vec = np.vectorize(lambda c: class_weight.get(int(c), 1.0))(y_tr).astype("float32")
    sw_eff = sw * cw_vec

    # upsampling balance
    X_tr, y_tr, sw_eff = balance_by_upsampling(X_tr, y_tr, sw_eff, len(classes))

    # Build model
    D = X.shape[1]; C = len(classes)
    model = build_model(W0, mask_free, D, C, params)
    opt = keras.optimizers.Adam(learning_rate=params.lr, clipnorm=1.0)

    alpha_vec = np.vectorize(lambda i: class_weight.get(int(i), 1.0))(np.arange(C)).astype("float32")
    alpha_vec = alpha_vec / float(alpha_vec.mean() if alpha_vec.mean()!=0 else 1.0)
    loss_fn = SparseFocalLoss(n_classes=C, alpha_per_class=alpha_vec, gamma=params.focal_gamma, label_smoothing=params.label_smooth)

    metrics = [
        keras.metrics.SparseCategoricalAccuracy(name="top1_acc"),
        keras.metrics.SparseTopKCategoricalAccuracy(k=TOPK, name="top3_acc")
    ]
    model.compile(optimizer=opt, loss=loss_fn, metrics=metrics)

    # (Novo) Warm-start se os pesos anteriores forem compatíveis
    if prior_weights is not None:
        try:
            model.set_weights(prior_weights)
            print("[INFO] Warm-start: pesos carregados no modelo do trial (arquitetura compatível).")
        except Exception as e:
            print("[WARN] Warm-start falhou (arquitetura/shape incompatível):", e)

    # callbacks
    ckpt_path = os.path.join(export_dir, "best_model_trial.keras")
    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_top3_acc", mode="max", patience=PATIENCE_EARLY, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_top3_acc", mode="max", factor=0.5, patience=4, min_lr=1e-5, verbose=1),
        keras.callbacks.ModelCheckpoint(filepath=ckpt_path, monitor="val_top3_acc", mode="max", save_best_only=True, save_weights_only=False)
    ]

    # train
    hist = model.fit(
        X_tr, y_tr,
        sample_weight=sw_eff,
        validation_data=(X_valid, y_valid),
        epochs=120, batch_size=BATCH_SIZE,
        callbacks=callbacks, verbose=2
    )

    # evaluate
    logits_v = model.predict(X_valid, batch_size=256, verbose=0) if X_valid.shape[0]>0 else np.empty((0, C))
    prob_v = tf.nn.softmax(logits_v).numpy() if X_valid.shape[0]>0 else np.empty((0, C))
    if prob_v.shape[0] == 0:
        val_top3 = 0.0
        val_top1 = 0.0
    else:
        top1 = prob_v.argmax(axis=1)
        top3_pred = np.argpartition(prob_v, -TOPK, axis=1)[:, -TOPK:]
        in_top3 = np.array([y_valid[i] in top3_pred[i] for i in range(y_valid.shape[0])])
        val_top1 = float(np.mean(top1 == y_valid))
        val_top3 = float(np.mean(in_top3))

    return {
        "val_top1": val_top1,
        "val_top3": val_top3,
        "ckpt_path": ckpt_path,
        "history": hist.history,
        "params": params.__dict__,
        "weights": model.get_weights(),  # para possível reaproveitamento em próximos trials
    }

# ===================== AUTO-SEARCH =====================
def suggest_params(best=None, trial_idx=0):
    # Espaços de busca com leve exploração/exploração
    lr_choices = [1e-3, 7.5e-4, 5e-4, 3e-4]
    dropout_choices = [0.10, 0.15, 0.20, 0.25]
    hu_choices = [64, 96, 128]
    l2_choices = [1e-3, 7.5e-4, 5e-4, 3e-4]
    gamma_choices = [1.5, 2.0, 2.5, 3.0]
    smooth_choices = [0.0, 0.05, 0.10]

    if (best is None) or (trial_idx < 3):
        # Exploração aleatória nas primeiras tentativas
        return TrialParams(
            lr=random.choice(lr_choices),
            dropout=random.choice(dropout_choices),
            hidden_units=random.choice(hu_choices),
            l2_delta=random.choice(l2_choices),
            focal_gamma=random.choice(gamma_choices),
            label_smooth=random.choice(smooth_choices),
        )
    # Exploração local: perturba ao redor do melhor
    b = best["params"]
    def nudge(v, choices):
        i = min(range(len(choices)), key=lambda k: abs(choices[k]-v))
        j = max(0, min(len(choices)-1, i + random.choice([-1,0,1])))
        return choices[j]
    return TrialParams(
        lr=nudge(b["lr"], lr_choices),
        dropout=nudge(b["dropout"], dropout_choices),
        hidden_units=nudge(b["hidden_units"], hu_choices),
        l2_delta=nudge(b["l2_delta"], l2_choices),
        focal_gamma=nudge(b["focal_gamma"], gamma_choices),
        label_smooth=nudge(b["label_smooth"], smooth_choices),
    )

def extract_params_from_model(model) -> Optional[TrialParams]:
    """Extrai parâmetros relevantes do modelo carregado (se possível)."""
    try:
        anch = model.get_layer("anchored")
        hidden_units = anch.dense_h.units
        dropout = float(anch.drop.rate)
        # l2_delta está no regularizer do peso Delta
        l2_delta = float(anch.Delta.regularizer.l2) if hasattr(anch.Delta, "regularizer") else 5e-4
        # Não temos info confiável de lr, gamma e smoothing no arquivo .keras → usar defaults “centrais”
        return TrialParams(lr=5e-4, dropout=dropout, hidden_units=hidden_units,
                           l2_delta=l2_delta, focal_gamma=2.0, label_smooth=0.05)
    except Exception as e:
        print("[WARN] Não foi possível extrair params do modelo inicial:", e)
        return None

def evaluate_model_on_split(model, X, y_raw, classes, seed) -> Tuple[float,float]:
    """Avalia (Top1/Top3) o modelo carregado na validação do seed especificado."""
    # Constrói split com allowed_toks
    norm_to_idx = {normalize_token(c): i for i, c in enumerate(classes)}
    counts = {}
    for s in y_raw:
        tok = normalize_token(s)
        if s and tok not in {"nao","não"} and tok in {normalize_token(c) for c in classes}:
            counts[tok] = counts.get(tok, 0) + 1
    allowed_toks = {t for t, n in counts.items() if n >= MIN_COUNT_FOR_TRAIN}
    _, valid_idx, _ = split_by_class(y_raw, classes, allowed_toks, seed=seed)

    if valid_idx.size == 0:
        return 0.0, 0.0

    y_valid = np.array([norm_to_idx[normalize_token(y_raw[i])] for i in valid_idx], dtype=np.int32)
    X_valid = X[valid_idx]
    logits_v = model.predict(X_valid, batch_size=256, verbose=0)
    prob_v = tf.nn.softmax(logits_v).numpy()
    top1 = prob_v.argmax(axis=1)
    top3_pred = np.argpartition(prob_v, -TOPK, axis=1)[:, -TOPK:]
    in_top3 = np.array([y_valid[i] in top3_pred[i] for i in range(y_valid.shape[0])])
    val_top1 = float(np.mean(top1 == y_valid))
    val_top3 = float(np.mean(in_top3))
    return val_top1, val_top3

# ===================== MAIN LOOP =====================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, default="C:/SourceCode/qip/python/banco_dados.xlsx")
    ap.add_argument("--output", type=str, default="C:/SourceCode/qip/python/banco_dados.xlsx")
    ap.add_argument("--target_top3", type=float, default=0.95,
                    help="Critério de parada: validação Top-3 >= alvo")
    ap.add_argument("--max_trials", type=int, default=300,
                    help="Número máximo de tentativas")
    ap.add_argument("--init_best", type=str, default="C:/SourceCode/qip/python/saida_modelo",
                    help="(Opcional) Caminho para um modelo .keras inicial (referência de melhor)")
    args = ap.parse_args()

    path_in  = args.input
    path_out = args.output

    print(f"[INFO] target_top3 = {args.target_top3} | max_trials = {args.max_trials}")
    if args.init_best:
        print(f"[INFO] init_best = {args.init_best}")

    # Read data
    df = pd.read_excel(path_in, sheet_name=ABA_DADOS)
    if COL_ALVO not in df.columns:
        raise ValueError(f"Coluna de rótulo '{COL_ALVO}' não encontrada em '{ABA_DADOS}'.")
    feature_cols = list(df.columns[1:])
    if not feature_cols:
        raise ValueError("Nenhuma feature encontrada (esperado: colunas a partir de B em TDados_clean).")

    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(0,1).values.astype(np.float32)
    y_raw = df[COL_ALVO].astype(object).fillna("").astype(str).tolist()
    sum_by_col = np.sum(X, axis=0)
    mask_free  = (sum_by_col > 0.0).astype(np.float32)

    classes, W0 = read_valid_classes_and_W0(path_in, ABA_PONTOS, feature_cols)
    W0 = np.nan_to_num(W0, nan=0.0, posinf=0.0, neginf=0.0)

    # ST presente? (classe real)
    has_ST_label = any(normalize_token(s)=="sem transtorno" for s in y_raw if s)
    if has_ST_label and "Sem Transtorno" not in classes:
        classes.append("Sem Transtorno")
        W0 = np.vstack([W0, np.zeros((1, W0.shape[1]), dtype=float)])

    export_dir = build_export_dir(path_out)
    best = None
    best_weights = None  # pesos do melhor (para warm-start quando compatível)
    history_trials = []

    # ---------- (Novo) Carrega melhor modelo inicial, se fornecido ----------
    if args.init_best and os.path.isfile(args.init_best):
        try:
            init_dir = os.path.dirname(args.init_best)
            # Carregar metadados próximos ao modelo
            classes_path = os.path.join(init_dir, "classes.json")
            feats_path   = os.path.join(init_dir, "feature_cols.json")
            ok_meta = True
            if not (os.path.isfile(classes_path) and os.path.isfile(feats_path)):
                print("[WARN] classes.json/feature_cols.json não encontrados ao lado do modelo. Ignorando init_best.")
                ok_meta = False
            else:
                classes_init = json.load(open(classes_path, "r", encoding="utf-8"))
                feats_init   = json.load(open(feats_path,   "r", encoding="utf-8"))
                if classes_init != classes:
                    print("[WARN] Conjunto/ordem de classes do modelo inicial difere do atual. Ignorando init_best.")
                    ok_meta = False
                if feats_init != feature_cols:
                    print("[WARN] Conjunto/ordem de features do modelo inicial difere do atual. Ignorando init_best.")
                    ok_meta = False

            if ok_meta:
                # Carrega o modelo
                model0 = keras.models.load_model(args.init_best, custom_objects={"AnchoredLogits": AnchoredLogits, "SparseFocalLoss": SparseFocalLoss})
                # Extrai parâmetros
                init_params = extract_params_from_model(model0)
                # Avalia no split do primeiro trial (para comparação justa)
                seed_first = VAL_SPLIT_SEED + 1
                val_top1_0, val_top3_0 = evaluate_model_on_split(model0, X, y_raw, classes, seed_first)
                best = {"val_top3": val_top3_0, "val_top1": val_top1_0,
                        "params": (init_params.__dict__ if init_params else {
                            "lr":5e-4,"dropout":0.15,"hidden_units":96,"l2_delta":5e-4,"focal_gamma":2.0,"label_smooth":0.05
                        })}
                best_weights = model0.get_weights()
                print(f"🏁 Modelo inicial avaliado: val_top1={val_top1_0:.3f}  val_top3={val_top3_0:.3f}")
                print(f"   Params extraídos: {best['params']}")
                # Se já atingir o alvo, salvar como best_overall imediatamente
                if best["val_top3"] >= args.target_top3:
                    best_path = os.path.join(export_dir, "best_overall.keras")
                    # Re-salva o modelo inicial como melhor
                    try:
                        model0.save(best_path)
                        json.dump(best, open(os.path.join(export_dir, "best_overall.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                        json.dump(classes, open(os.path.join(export_dir, "classes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                        json.dump(feature_cols, open(os.path.join(export_dir, "feature_cols.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                        np.savez(os.path.join(export_dir, "anchors_w0_mask.npz"), W0=W0.astype("float32"), mask_free=mask_free.astype("float32"))
                        print(f"🎯 Critério já atingido pelo modelo inicial! val_top3={best['val_top3']:.3f} ≥ {args.target_top3:.2f}.")
                        print(f"💾 Copiado para: {best_path}")
                        return
                    except Exception as e:
                        print("[WARN] Falha ao salvar o modelo inicial como best_overall:", e)
            # se não ok_meta, seguimos sem init_best
        except Exception as e:
            print("[WARN] Falha ao carregar/avaliar init_best:", e)

    print(f"🔁 Iniciando Auto-Search. Alvo: val_top3 >= {args.target_top3:.2f}. Ctrl+C para parar mantendo o melhor modelo.")

    try:
        for t in range(1, args.max_trials+1):
            params = suggest_params(best, trial_idx=t-1)

            # Se temos best vindo do init_best, usar seus params exatamente no 1º trial
            if (best is not None) and (t == 1):
                try:
                    bp = best["params"]
                    params = TrialParams(**bp)  # força trial 1 começar do modelo inicial
                    print("[INFO] Trial 1 vai partir dos parâmetros do modelo inicial.")
                except Exception:
                    pass

            print(f"\n=== Trial {t}/{args.max_trials} ===")
            print("Parâmetros:", params)

            # Warm-start: se os params do trial coincidirem com os do best atual e temos pesos, usa-os
            prior_w = None
            if (best is not None) and (best_weights is not None):
                same = True
                for k in ["dropout","hidden_units","l2_delta"]:
                    if abs(best["params"].get(k, None) - getattr(params, k)) > 1e-12:
                        same = False
                        break
                if same:
                    prior_w = best_weights

            res = run_trial(X, y_raw, feature_cols, classes, W0, mask_free, export_dir,
                            params, seed=VAL_SPLIT_SEED+t, prior_weights=prior_w)

            history_trials.append({"trial": t, **res["params"], "val_top1": res["val_top1"], "val_top3": res["val_top3"]})
            print(f"Resultado: val_top1={res['val_top1']:.3f}  val_top3={res['val_top3']:.3f}")

            # Atualiza melhor
            if (best is None) or (res["val_top3"] > best["val_top3"]):
                best = {"val_top3": res["val_top3"], "val_top1": res["val_top1"], "params": res["params"]}
                best_weights = res["weights"]
                try:
                    best_path = os.path.join(export_dir, "best_overall.keras")
                    shutil.copyfile(res["ckpt_path"], best_path)
                    json.dump(best, open(os.path.join(export_dir, "best_overall.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                    json.dump(classes, open(os.path.join(export_dir, "classes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                    json.dump(feature_cols, open(os.path.join(export_dir, "feature_cols.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                    np.savez(os.path.join(export_dir, "anchors_w0_mask.npz"), W0=W0.astype("float32"), mask_free=mask_free.astype("float32"))
                    print(f"💾 Novo melhor modelo! val_top3={best['val_top3']:.3f}  → salvo em: {best_path}")
                except Exception as e:
                    print("[WARN] Falha ao promover melhor modelo:", e)

            # Checagem de parada
            if best and best["val_top3"] >= args.target_top3:
                print(f"🎯 Critério atingido: val_top3={best['val_top3']:.3f} ≥ {args.target_top3:.2f}. Encerrando.")
                break
    except KeyboardInterrupt:
        print("\n⏹ Interrompido pelo usuário. Mantendo melhor modelo salvo.")
    finally:
        # salvar histórico dos trials
        try:
            df_hist = pd.DataFrame(history_trials)
            hist_path = os.path.join(export_dir, "trials_history.csv")
            df_hist.to_csv(hist_path, index=False, encoding="utf-8-sig")
            print(f"📄 Histórico de trials salvo em {hist_path}")
            if best:
                print(f"🏆 Melhor até agora: val_top3={best['val_top3']:.3f}  params={best['params']}")
                print(f"➡️  Modelo: {os.path.join(export_dir, 'best_overall.keras')}")
        except Exception as e:
            print("[WARN] Falha ao salvar histórico:", e)

if __name__ == "__main__":
    main()