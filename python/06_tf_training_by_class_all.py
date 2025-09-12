
# -*- coding: utf-8 -*-
"""
06_tf_training_by_class.py
Autor: Jayne + ChatGPT (QIP)
Data: 2025-09-12

Treino não linear em TensorFlow ancorado na aba "Pontuação" (W0) + mutação controlada.
Fluxo em 3 etapas:
  (1) Treino por classe (inclui "Sem Transtorno" se rotulado; cria critério ST a partir de baixa ativação dos "nao")
  (2) Validação por classe (split estratificado por classe, obedecendo regras size=1 e size=2)
  (3) Predição dos DESCONHECIDOS ("nao"/vazio) com rankeamento Top-3 e decisão ST quando baixa ativação.

Requisitos:
  - Python 3.10+
  - pandas, numpy, openpyxl
  - tensorflow>=2.11

Execução:
  py -3.12 06_tf_training_by_class.py --input "c:/SourceCode/qip/python/banco_dados.xlsx" --output "c:/SourceCode/qip/python/banco_dados.xlsx"

Observações importantes:
  - Usa a aba TDados_clean (NÃO usa TDados).
  - Coluna "Alvo" contém as classes. "nao"/"não"/vazio => DESCONHECIDO (fora do treino/validação).
  - Classes válidas = Pontuação!A3:A13 (nomes canônicos).
  - W0 = pesos base extraídos da aba "Pontuação" (linhas A3:A13 x features das colunas que casam por nome com TDados_clean).
  - Colunas de X cuja SÚMULA (no conjunto completo) seja zero: ficam CONGELADAS (sem mutação).

Saídas (novas abas no Excel):
  - Split_Stats                : distribuição por classe (treino/validação/fora)
  - TF_Metrics_Treino          : métricas por classe (Top-1 / Top-3 micro/macro)
  - TF_Metrics_Valid           : idem para validação
  - TF_Pred_Desconhecidos      : predições nas linhas desconhecidas com Top-3
  - TF_Config                  : parâmetros/limiares usados
"""

import argparse, sys, math, json
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from collections import Counter, defaultdict

# TensorFlow / Keras
import tensorflow as tf
import keras
from keras import layers

# Excel
import openpyxl
from datetime import datetime

# ===================== CONFIG =====================
DEFAULT_INPUT  = r"c:\SourceCode\qip\python\banco_dados.xlsx"
DEFAULT_OUTPUT = r"c:\SourceCode\qip\python\banco_dados.xlsx"

ABA_DADOS     = "TDados_clean"
ABA_PONTOS    = "Pontuação"
COL_ALVO      = "Alvo"

# Leitura das classes válidas (linhas 3..13 em A)
ROW_START, ROW_END = 3, 13    # inclusivo no Excel (usaremos iloc[2:13])

# Modelo / treino
EPOCHS            = 120
BATCH_SIZE        = 32
LEARNING_RATE     = 1e-3
PATIENCE_EARLY    = 12
VAL_SPLIT_SEED    = 42

# Mutação controlada (ancoragem em W0)
L2_DELTA          = 1e-3      # força p/ manter ΔW pequeno
L2_BIAS           = 1e-4
HIDDEN_UNITS      = 64        # parte não linear
DROPOUT_RATE      = 0.10

# Critério "Sem Transtorno" (ST) via baixa ativação dos DESCONHECIDOS
ST_MIN_N_UNK      = 10        # mínimo de "nao" p/ estimar limiar
ST_LOW_PERC       = 5.0       # percentil inferior de energia (soma das features) p/ pseudo-rótulo ST
ST_USE_PSEUDO     = True      # usa amostras pseudo-rotuladas (desconhecidos de baixa energia) no treino da classe ST
ST_ALPHA_PSEUDO   = 0.35      # peso relativo das perdas dos pseudo-rótulos ST

# Decisão final nos desconhecidos
THETA_MAXPROB     = 0.40      # se a prob máx < theta => tende a ST
TOPK              = 3

# ==================================================

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
    """Lê classes válidas em Pontuação!A3:A13 e extrai matriz W0 para estas classes.
       A matriz W0 é construída casando colunas por NOME com feature_names.
       Se alguma feature não existir na "Pontuação", recebe 0.
    """
    dfp_all = pd.read_excel(path, sheet_name=aba_pont, header=0)
    # Coluna A tem classes; garantir que linhas 3..13 existem
    colA = pd.read_excel(path, sheet_name=aba_pont, usecols="A", header=None)
    vals = colA.iloc[ROW_START-1:ROW_END, 0].astype(object).tolist()
    classes = [str(x).strip() for x in vals if pd.notna(x) and str(x).strip() != ""]
    # Subconjunto do dfp_all para linhas dessas classes (caso haja cabeçalhos na primeira linha)
    # Buscamos por uma coluna que contenha "Classe" ou similar; se não houver, assumimos que a linha do nome está na própria A.
    # Faremos merge pelo nome canônico existente em A.
    dfp_all = dfp_all.copy()
    # Garantir que a primeira coluna seja o nome
    if dfp_all.columns[0].strip().lower() not in {"classe","class","nome","rótulo","rotulo","alvo","a"}:
        # insere com base na coluna A lida separadamente (mesma ordem do sheet)
        dfA = pd.read_excel(path, sheet_name=aba_pont, header=None)
        dfp_all.insert(0, "Classe", dfA.iloc[:,0])
        dfp_all.columns = [str(c) for c in dfp_all.columns]
    name_col = dfp_all.columns[0]
    # Filtrar e reindexar
    dfp = dfp_all[dfp_all[name_col].astype(str).str.strip().isin(classes)].copy()
    # Construir W0 [n_classes x n_features] alinhando por nome
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
    """Pesa mais as classes minoritárias: class_weight[i] = (1/sqrt(freq_i)) normalizado para média=1."""
    counts = Counter(y.tolist())
    w = {}
    vals = []
    for i, _ in enumerate(classes):
        f = max(1, counts.get(i, 0))
        wi = 1.0 / math.sqrt(f)
        w[i] = wi
        vals.append(wi)
    mean_w = np.mean(list(w.values()))
    w = {k: v/mean_w for k, v in w.items()}
    return w

class AnchoredLogits(layers.Layer):
    """
    Camada de logits ancorada:
      logits = x @ (W0 + M*Delta) + b  +  ReLU(BN(x)) @ V
    Onde:
      - W0 (constante, não-treinável) vem da aba "Pontuação"
      - Delta é treinável com L2 regularização (mutação controlada)
      - M é uma máscara (1 = livre, 0 = congelada) para congelar features com soma==0
      - Termo não-linear: uma projeção V de uma base ReLU(BN(x)) (HIDDEN_UNITS) + dropout
    """
    def __init__(self, W0: np.ndarray, mask_free: np.ndarray,
                 hidden_units: int = 64, dropout: float = 0.1,
                 l2_delta: float = 1e-3, l2_bias: float = 1e-4, **kwargs):
        super().__init__(**kwargs)
        self.W0 = tf.constant(W0.astype(np.float32))               # [C, D]
        self.mask = tf.constant(mask_free.astype(np.float32))      # [D]
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
        x = inputs  # [B, D]
        # termo linear ancorado (congela colunas com máscara=0)
        Delta_eff = self.Delta * self.mask[tf.newaxis, :]  # broadcasting [C,D]*[1,D]
        W_eff = self.W0 + Delta_eff                        # [C, D]
        logits_lin = tf.linalg.matmul(x, tf.transpose(W_eff)) + self.bias  # [B, C]

        # termo não-linear
        h = self.ln(x)
        h = self.dense_h(h)
        h = self.drop(h, training=training)                # [B, H]
        logits_nl = tf.linalg.matmul(h, self.V)            # [B, C]

        logits = logits_lin + logits_nl
        logits = tf.where(tf.math.is_finite(logits), logits, tf.zeros_like(logits))
        return logits

def topk_accuracy(y_true, y_pred, k=3):
    topk = tf.math.in_top_k(tf.nn.softmax(y_pred), tf.cast(y_true, tf.int32), k=k)
    return tf.reduce_mean(tf.cast(topk, tf.float32))

def split_by_class(y_labels: List[str], classes: List[str], seed: int=42) -> Tuple[np.ndarray,np.ndarray,np.ndarray]:
    """
    Retorna índices train_idx, valid_idx, out_idx obedecendo:
      - por classe: 2/3 treino, 1/3 validação
      - tamanho 1 => fora
      - tamanho 2 => 1/1
      - desconhecidos ('nao'/'não'/None/'') => fora (serão usados na etapa 3)
    """
    rng = np.random.default_rng(seed)
    idx_by_c = defaultdict(list)
    out = []

    for i, lab in enumerate(y_labels):
        tok = normalize_token(lab)
        if lab is None or lab == "" or tok in {"nao", "não"}:
            out.append(i)
            continue
        if tok not in {normalize_token(c) for c in classes}:
            # fora das classes válidas => também fora (não entra treino/valid)
            out.append(i)
            continue
        idx_by_c[tok].append(i)

    train, valid = [], []
    for tok, idxs in idx_by_c.items():
        n = len(idxs)
        idxs = np.array(idxs)
        rng.shuffle(idxs)
        if n == 1:
            out.extend(idxs.tolist())
        elif n == 2:
            train.append(idxs[0:1])
            valid.append(idxs[1:2])
        else:
            cut = int(round(n * (2/3)))
            train.append(idxs[:cut])
            valid.append(idxs[cut:])

    train_idx = np.concatenate(train) if len(train)>0 else np.array([], dtype=int)
    valid_idx = np.concatenate(valid) if len(valid)>0 else np.array([], dtype=int)
    out_idx   = np.array(sorted(set(out)), dtype=int)
    return train_idx, valid_idx, out_idx

def save_preserving_sheets(target_path, dfs_and_sheets):
    import os, shutil, tempfile
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.xlsx")
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile)
        base_existed = True
    except Exception:
        pass  # arquivo destino não existe ainda
    mode = "a" if base_existed else "w"
    # Se o arquivo ainda não existe, escrevemos direto no target_path
    write_path = tmpfile if base_existed else target_path
    with pd.ExcelWriter(write_path, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
        for df, sheet in dfs_and_sheets:
            df.to_excel(writer, sheet_name=sheet, index=False)
    if base_existed:
        try:
            os.replace(tmpfile, target_path)
            saved = target_path
        except PermissionError:
            from datetime import datetime
            carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
            alt_path = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
            shutil.copyfile(tmpfile, alt_path)
            saved = alt_path
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        saved = target_path
    return saved

def main(args):
    # --------------- Ler planilha ---------------
    path_in  = args.input
    path_out = args.output or path_in

    df = pd.read_excel(path_in, sheet_name=ABA_DADOS)
    if df.shape[1] < 2:
        raise ValueError("TDados_clean precisa ter ID em A e features a partir de B.")
    feature_cols = list(df.columns[1:])
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32)
    X = np.clip(X, 0.0, 1.0)
    y_raw = df[COL_ALVO].astype(object).fillna("").astype(str).tolist()

    # congelar features com somatório == 0
    sum_by_col = np.sum(X, axis=0)
    mask_free  = (sum_by_col > 0.0).astype(np.float32)   # 1=livre, 0=congelada

    # --------------- Ler classes + W0 ---------------
    classes, W0 = read_valid_classes_and_W0(path_in, ABA_PONTOS, feature_cols)
    W0 = np.nan_to_num(W0, nan=0.0, posinf=0.0, neginf=0.0)
    norm_to_idx = {normalize_token(c): i for i, c in enumerate(classes)}
    # Adicionar ST se existir no y_raw explicitamente (classe real)
    has_ST_label = any(normalize_token(s)=="sem transtorno" for s in y_raw if s)
    if has_ST_label and "Sem Transtorno" not in classes:
        classes.append("Sem Transtorno")
        # ST não existe na Pontuação: adiciona linha zero
        W0 = np.vstack([W0, np.zeros((1, W0.shape[1]), dtype=float)])
        norm_to_idx[normalize_token("Sem Transtorno")] = len(classes)-1

    C, D = W0.shape[0], W0.shape[1]
    assert D == X.shape[1], "Número de colunas de W0 difere do número de features de TDados_clean."

    # --------------- SPLIT por classe ---------------
    train_idx, valid_idx, out_idx = split_by_class(y_raw, classes, seed=VAL_SPLIT_SEED)

    def label_to_index(s: str) -> int:
        tok = normalize_token(s)
        return norm_to_idx[tok]

    y_train = np.array([label_to_index(y_raw[i]) for i in train_idx], dtype=np.int32)
    y_valid = np.array([label_to_index(y_raw[i]) for i in valid_idx], dtype=np.int32)
    X_train = X[train_idx]; X_valid = X[valid_idx]

    # --------------- Pseudo-rótulos ST ---------------
    # Critério: em "out_idx" (desconhecidos), pega os de baixa energia (percentil ST_LOW_PERC) caso N>=ST_MIN_N_UNK
    pseudo_ST_X = np.empty((0, D), dtype=np.float32)
    pseudo_ST_y = np.empty((0,), dtype=np.int32)
    st_thr = np.nan
    if ST_USE_PSEUDO and len(out_idx) >= ST_MIN_N_UNK:
        sums_out = X[out_idx].sum(axis=1)
        st_thr = float(np.percentile(sums_out, ST_LOW_PERC))
        # Somente se classe ST existir no espaço
        if "Sem Transtorno" not in classes:
            classes.append("Sem Transtorno")
            W0 = np.vstack([W0, np.zeros((1, D), dtype=float)])
            norm_to_idx[normalize_token("Sem Transtorno")] = len(classes)-1
            C = len(classes)
        st_idx = norm_to_idx[normalize_token("Sem Transtorno")]
        pick = np.where(sums_out <= st_thr)[0]
        if pick.size > 0:
            pseudo_ST_X = X[out_idx[pick]]
            pseudo_ST_y = np.full((pick.size,), st_idx, dtype=np.int32)

    # --------------- Dataset Keras ---------------
    X_tr = X_train; y_tr = y_train
    if pseudo_ST_X.shape[0] > 0:
        # concatena pseudo-rótulos com peso menor (via sample_weight)
        X_tr = np.vstack([X_train, pseudo_ST_X])
        y_tr = np.concatenate([y_train, pseudo_ST_y])
        sw   = np.concatenate([np.ones(y_train.shape[0], dtype=np.float32),
                               np.full(pseudo_ST_y.shape[0], ST_ALPHA_PSEUDO, dtype=np.float32)])
    else:
        sw = np.ones(y_train.shape[0], dtype=np.float32)

    # Class weights para minoritárias
    class_weight = make_class_weights(y_tr, classes)

    # ---- Fold class_weight into sample_weight (so we do NOT pass both) ----
    import numpy as _np
    cw_vec = _np.vectorize(lambda c: class_weight.get(int(c), 1.0))(y_tr).astype("float32")
    sw_eff = (sw.astype("float32") if sw is not None else _np.ones_like(cw_vec)) * cw_vec

    # --------------- Modelo ---------------
    assert np.isfinite(W0).all(), "W0 contém valores não-finitos."
    assert np.isfinite(mask_free).all(), "mask_free contém valores não-finitos."
    inp = keras.Input(shape=(D,), dtype=tf.float32, name="x")
    logits = AnchoredLogits(W0=W0, mask_free=mask_free, hidden_units=HIDDEN_UNITS,
                            dropout=DROPOUT_RATE, l2_delta=L2_DELTA, l2_bias=L2_BIAS, name="anchored")(inp)
    model = keras.Model(inputs=inp, outputs=logits, name="AnchoredNL")
    opt = keras.optimizers.Adam(learning_rate=LEARNING_RATE, clipnorm=1.0)
    loss_fn = keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    metrics = [
        keras.metrics.SparseCategoricalAccuracy(name="top1_acc"),
        keras.metrics.SparseTopKCategoricalAccuracy(k=3, name="top3_acc")
    ]

    model.compile(optimizer=opt, loss=loss_fn, metrics=metrics)

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_top3_acc", mode="max",
                                      patience=PATIENCE_EARLY, restore_best_weights=True)
    ]

    # --------------- Treinar ---------------

    # ---- Sanitize inputs & labels ----
    X_tr = np.nan_to_num(X_tr, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
    X_valid = np.nan_to_num(X_valid, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
    assert y_tr.size == 0 or (y_tr.min() >= 0 and y_tr.max() < len(classes)), "y_tr fora do intervalo [0,C)."
    assert y_valid.size == 0 or (y_valid.min() >= 0 and y_valid.max() < len(classes)), "y_valid fora do intervalo [0,C)."

    hist = model.fit(
        X_tr, y_tr,
        sample_weight=sw_eff,
        validation_data=(X_valid, y_valid),
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        callbacks=callbacks, verbose=2
    )

    # --------------- Avaliar: treino e validação (Top1/Top3 micro/macro) ---------------
    def eval_block(Xb, yb, split_name: str):
        logits_b = model.predict(Xb, batch_size=256, verbose=0)
        prob_b = tf.nn.softmax(logits_b).numpy()
        top1 = prob_b.argmax(axis=1)
        # micro
        micro_top1 = float(np.mean(top1 == yb)) if yb.size>0 else np.nan
        # top3
        top3_pred = np.argpartition(prob_b, -TOPK, axis=1)[:, -TOPK:]
        in_top3 = np.array([yb[i] in top3_pred[i] for i in range(yb.shape[0])]) if yb.size>0 else np.array([])
        micro_top3 = float(np.mean(in_top3)) if yb.size>0 else np.nan
        # macro por classe (apenas classes presentes)
        per_class = []
        for c in range(len(classes)):
            mask = (yb == c)
            if mask.sum()==0:
                continue
            pc_top1 = float(np.mean(top1[mask] == yb[mask]))
            pc_top3 = float(np.mean(in_top3[mask]))
            per_class.append((pc_top1, pc_top3, c, int(mask.sum())))
        if per_class:
            macro_top1 = float(np.mean([x[0] for x in per_class]))
            macro_top3 = float(np.mean([x[1] for x in per_class]))
        else:
            macro_top1 = np.nan
            macro_top3 = np.nan
        # tabela por classe
        rows = []
        for (pc1, pc3, c, n) in per_class:
            rows.append({"split": split_name, "classe": classes[c],
                         "n": n, "Top1": pc1, "Top3": pc3})
        df_split = pd.DataFrame(rows)
        sums = {"split": split_name, "classe": "__MICRO__", "n": int(yb.shape[0]),
                "Top1": micro_top1, "Top3": micro_top3}
        avgs = {"split": split_name, "classe": "__MACRO__", "n": int(np.sum([r['n'] for r in rows])) if rows else 0,
                "Top1": macro_top1, "Top3": macro_top3}
        df_split = pd.concat([df_split, pd.DataFrame([sums, avgs])], ignore_index=True)
        return df_split, prob_b

    df_train_metrics, prob_train = eval_block(X_train, y_train, "TREINO")
    df_valid_metrics, prob_valid = eval_block(X_valid, y_valid, "VALID")

    # --------------- Predição dos DESCONHECIDOS ---------------
    X_unk = X[out_idx]; idx_unk = out_idx
    logits_unk = model.predict(X_unk, batch_size=256, verbose=0) if X_unk.shape[0]>0 else np.empty((0, C))
    prob_unk = tf.nn.softmax(logits_unk).numpy() if X_unk.shape[0]>0 else np.empty((0, C))
    sums_unk = X_unk.sum(axis=1) if X_unk.shape[0]>0 else np.array([])

    # decisão final: ST se prob_max<threshold OU (soma <= st_thr)
    st_idx = norm_to_idx.get(normalize_token("Sem Transtorno"), None)
    preds_final = []
    rows_pred = []
    for i in range(X_unk.shape[0]):
        p = prob_unk[i]
        order = np.argsort(-p)[:TOPK]
        labels_topk = [classes[j] for j in order]
        scores_topk = [float(p[j]) for j in order]
        jmax = int(order[0]) if order.size>0 else None
        pmax = float(p[jmax]) if jmax is not None else 0.0

        is_ST = False
        if st_idx is not None:
            if not np.isnan(st_thr) and sums_unk[i] <= st_thr:
                is_ST = True
            if pmax < THETA_MAXPROB:
                # baixa confiança → ST
                is_ST = True
        final_label = "Sem Transtorno" if (is_ST and st_idx is not None) else (classes[jmax] if jmax is not None else "")
        preds_final.append(final_label)

        rows_pred.append({
            "linha_excel": int(idx_unk[i]) + 2,
            "Top1_Label": labels_topk[0] if labels_topk else "",
            "Top1_Prob": scores_topk[0] if scores_topk else np.nan,
            "Top2_Label": labels_topk[1] if len(labels_topk)>1 else "",
            "Top2_Prob": scores_topk[1] if len(scores_topk)>1 else np.nan,
            "Top3_Label": labels_topk[2] if len(labels_topk)>2 else "",
            "Top3_Prob": scores_topk[2] if len(scores_topk)>2 else np.nan,
            "Soma_Features": float(sums_unk[i]) if X_unk.shape[0]>0 else np.nan,
            "ST_Threshold": st_thr,
            "Final_Label": final_label
        })

    df_pred_unk = pd.DataFrame(rows_pred)

    # --------------- Relatórios / Saídas ---------------
    # Split stats
    stats_rows = []
    cnt_all = Counter([normalize_token(s) if s else "" for s in y_raw])
    cnt_tr  = Counter([classes[i] for i in y_train]) if y_train.size>0 else Counter()
    cnt_va  = Counter([classes[i] for i in y_valid]) if y_valid.size>0 else Counter()
    for c in classes:
        stats_rows.append({
            "classe": c,
            "total_em_TDados_clean": int(cnt_all.get(normalize_token(c), 0)),
            "treino": int(cnt_tr.get(c, 0)),
            "validacao": int(cnt_va.get(c, 0)),
        })
    stats_rows.append({"classe": "__FORA__", "total_em_TDados_clean": len(out_idx), "treino": 0, "validacao": 0})
    df_split = pd.DataFrame(stats_rows)

    # Config
    cfg = {
        "EPOCHS": EPOCHS, "BATCH_SIZE": BATCH_SIZE, "LEARNING_RATE": LEARNING_RATE,
        "PATIENCE_EARLY": PATIENCE_EARLY, "HIDDEN_UNITS": HIDDEN_UNITS, "DROPOUT_RATE": DROPOUT_RATE,
        "L2_DELTA": L2_DELTA, "L2_BIAS": L2_BIAS, "THETA_MAXPROB": THETA_MAXPROB,
        "ST": {"ST_MIN_N_UNK": ST_MIN_N_UNK, "ST_LOW_PERC": ST_LOW_PERC, "ST_USE_PSEUDO": ST_USE_PSEUDO,
               "ST_ALPHA_PSEUDO": ST_ALPHA_PSEUDO, "st_thr_used": st_thr}
    }
    df_cfg = pd.DataFrame([{"param": k, "valor": json.dumps(v) if isinstance(v, (dict, list)) else v}
                           for k, v in cfg.items()])

    saved = save_preserving_sheets(
        path_out,
        [
            (df_split,          "Split_Stats"),
            (df_train_metrics,  "TF_Metrics_Treino"),
            (df_valid_metrics,  "TF_Metrics_Valid"),
            (df_pred_unk,       "TF_Pred_Desconhecidos"),
            (df_cfg,            "TF_Config"),
        ]
    )
    print("✅ Abas criadas/atualizadas: Split_Stats, TF_Metrics_Treino, TF_Metrics_Valid, TF_Pred_Desconhecidos, TF_Config")
    print("💾 Arquivo salvo em:", saved)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    main(args)
