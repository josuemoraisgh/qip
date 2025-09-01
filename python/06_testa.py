# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
from datetime import datetime
from typing import List, Tuple
import numpy as np
import pandas as pd

from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline

# tentar estratificação multilabel (opcional)
try:
    from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
    HAS_MSKF = True
except Exception:
    HAS_MSKF = False

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_PONTOS = "Pontuação"

# abas de SAÍDA (9 no total)
ABA_SAIDA_LOG   = "Resultado_Logistica"         # OOF
ABA_SAIDA_RF    = "Resultado_Florestas"         # OOF
ABA_SAIDA_ENS   = "Resultado_Ensemble"          # OOF
ABA_SAIDA_HEUR  = "Resultado_Heuristica"        # baseline
ABA_MET_LOG     = "Metricas_Logistica"          # OOF médio
ABA_MET_RF      = "Metricas_Florestas"          # OOF médio
ABA_MET_ENS     = "Metricas_Ensemble"           # OOF
ABA_MET_HEUR    = "Metricas_Heuristica"         # baseline
ABA_EXPLICAO    = "Explicacao_Resultados"       # texto

COLUNA_TAM = 11           # número de classes/linhas usadas em Pontuação
LINHA_INICIO_PONTOS = 3   # linhas 3..13 no Excel
COL_ALVO = "Alvo"         # coluna de rótulos em TDados
DELIMS = ["|", ";", ","]  # separadores para multirrótulo

ALPHA_ENSEMBLE = 0.30     # peso da heurística na mistura final (0..1)
RANDOM_STATE = 42
TOPK = 3                  # quantas classes mostrar no ranking
# ============================================


# ------------------ Utilidades ------------------
def softmax_rows(mat: np.ndarray, axis: int = 1, eps: float = 1e-12) -> np.ndarray:
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    s = e / (np.sum(e, axis=axis, keepdims=True) + eps)
    return s

def topk_names_and_probs(proba: np.ndarray, class_names: List[str], k: int = 3) -> Tuple[List[str], List[float]]:
    idx = np.argsort(-proba)[:k]
    return [class_names[i] for i in idx], [float(proba[i]) for i in idx]

def save_preserving_sheets(target_path, dfs_and_sheets):
    """
    Preserva TODAS as abas existentes e substitui apenas as listadas.
    - Se o arquivo estiver aberto/bloqueado, salva uma cópia com timestamp.
    Retorna o caminho final salvo.
    """
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.xlsx")

    # 1) copiar o arquivo-base (para manter abas não alteradas)
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile)
        base_existed = True
    except Exception:
        # cria um workbook vazio
        with pd.ExcelWriter(tmpfile, engine="openpyxl", mode="w") as writer:
            pass

    # 2) escrever/replace apenas as abas desejadas
    mode = "a" if base_existed else "w"
    with pd.ExcelWriter(tmpfile, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
        for df, sheet in dfs_and_sheets:
            df.to_excel(writer, sheet_name=sheet, index=False)

    # 3) substituir o original
    try:
        os.replace(tmpfile, target_path)
        saved = target_path
    except PermissionError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt_path = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
        shutil.copyfile(tmpfile, alt_path)
        saved = alt_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return saved

def compute_metrics(y_true_bin: np.ndarray,
                    y_pred_bin: np.ndarray,
                    y_proba: np.ndarray,
                    class_names: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # por classe
    prec, rec, f1, support = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, average=None, zero_division=0
    )
    aucs = []
    for j in range(y_true_bin.shape[1]):
        try:
            aucs.append(roc_auc_score(y_true_bin[:, j], y_proba[:, j]))
        except ValueError:
            aucs.append(np.nan)

    df_cls = pd.DataFrame({
        "classe": class_names,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "auc": aucs,
        "suporte": support
    })

    # agregados
    prec_w, rec_w, f1_w, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, average="weighted", zero_division=0
    )
    prec_m, rec_m, f1_m, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, average="macro", zero_division=0
    )

    def auc_ovr(y_true_bin, y_proba, average="macro"):
        try:
            return roc_auc_score(y_true_bin, y_proba, average=average)
        except ValueError:
            return np.nan

    auc_macro = auc_ovr(y_true_bin, y_proba, average="macro")
    auc_weighted = auc_ovr(y_true_bin, y_proba, average="weighted")

    df_sum = pd.DataFrame([{
        "precision_macro": prec_m, "recall_macro": rec_m, "f1_macro": f1_m,
        "precision_weighted": prec_w, "recall_weighted": rec_w, "f1_weighted": f1_w,
        "auc_macro": auc_macro, "auc_weighted": auc_weighted
    }])
    return df_cls, df_sum

def parse_multilabel(series: pd.Series, known_classes: List[str]) -> List[List[str]]:
    KNOWN = set(known_classes)
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        labs = [p.strip() for p in s.split("|") if p.strip()]
        out.append([l for l in labs if l in KNOWN])
    return out

def make_cv(y_bin: np.ndarray):
    """MSKF (se disponível) ou KFold adaptativo (2..5 splits)."""
    pos_per_class = y_bin.sum(axis=0)
    min_pos = int(pos_per_class.min()) if len(pos_per_class) else 0
    n_splits = max(2, min(5, min_pos)) if min_pos > 0 else 2
    if HAS_MSKF:
        return MultilabelStratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    return KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

def oof_predict(model, X: np.ndarray, y_bin: np.ndarray, class_names: List[str]) -> Tuple[np.ndarray, np.ndarray, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Gera predições OOF (out-of-fold) multilabel.
    Retorna:
      - proba_oof: (n, K) com probabilidades fora do treino
      - y_pred_oof: (n, K) binário com threshold 0.5
      - (df_cls_mean, df_agg_mean): métricas por classe e agregadas (média dos folds)
    """
    n, K = y_bin.shape
    proba_oof = np.zeros((n, K), dtype=float)
    pred_oof  = np.zeros((n, K), dtype=int)

    cv = make_cv(y_bin)
    cls_list, sum_list = [], []

    if HAS_MSKF:
        splits = cv.split(X, y_bin)
    else:
        splits = cv.split(X)

    for fold_id, (tr_idx, te_idx) in enumerate(splits, start=1):
        Xtr, Xte = X[tr_idx], X[te_idx]
        ytr, yte = y_bin[tr_idx], y_bin[te_idx]

        model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)
        if isinstance(proba, list):
            proba = np.column_stack(proba)

        ypred = (proba >= 0.5).astype(int)

        proba_oof[te_idx] = proba
        pred_oof[te_idx]  = ypred

        df_cls, df_sum = compute_metrics(yte, ypred, proba, class_names)
        df_cls.insert(0, "fold", fold_id)
        df_sum.insert(0, "fold", fold_id)
        cls_list.append(df_cls)
        sum_list.append(df_sum)

    cls_cat = pd.concat(cls_list, ignore_index=True)
    sum_cat = pd.concat(sum_list, ignore_index=True)

    cls_mean = cls_cat.groupby("classe", as_index=False)[["precision","recall","f1","auc","suporte"]].mean()
    agg_mean = sum_cat.drop(columns=["fold"]).mean(numeric_only=True).to_frame().T
    agg_mean.insert(0, "fold", "mean")

    return proba_oof, pred_oof, (cls_mean, agg_mean)

def build_result_df(df_base: pd.DataFrame, proba: np.ndarray, class_names: List[str], topk: int = 3) -> pd.DataFrame:
    # ID + um único 'Alvo' (sem duplicidade)
    cols = [df_base.columns[0]]
    if COL_ALVO in df_base.columns:
        cols.append(COL_ALVO)  # ground truth apenas como referência clínica
    out = df_base[cols].copy()

    # probabilidades por classe
    for j, name in enumerate(class_names):
        out[f"p_{name}"] = proba[:, j]

    # ranking top-k
    tops = []
    for i in range(proba.shape[0]):
        names, probs = topk_names_and_probs(proba[i], class_names, k=min(topk, len(class_names)))
        rec = {}
        for t, (nm, pr) in enumerate(zip(names, probs), start=1):
            rec[f"top{t}_classe"] = nm
            rec[f"top{t}_prob"] = pr
        tops.append(rec)
    tops_df = pd.DataFrame(tops)
    return pd.concat([out, tops_df], axis=1)

# ------------------ Leitura e preparação ------------------
df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

# X (TDados: colunas da B em diante)
cols_dados = df_dados.columns[1:]
if len(cols_dados) == 0:
    raise ValueError("TDados não possui colunas a partir da coluna B.")
X = df_dados[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
n, m = X.shape

# Classes a partir das linhas horizontais da aba Pontuação
r0 = LINHA_INICIO_PONTOS - 2
linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(f"Colunas de TDados ausentes em 'Pontuação': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

# W heurístico (m x K)
W_block = df_pont.loc[linhas_modelos, cols_dados]
W = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
if W.shape != (m, COLUNA_TAM):
    raise ValueError(f"Dimensão inesperada de W: {W.shape}, esperado ({m}, {COLUNA_TAM}).")

# Nomes de classes
if "Tipo de Transtorno" in df_pont.columns:
    class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]
K = len(class_names)

# Alvo obrigatório
if COL_ALVO not in df_dados.columns:
    raise ValueError(f"A coluna de alvo '{COL_ALVO}' não foi encontrada em TDados.")

# -------- saneamento X (0..1 esperado) --------
neg_mask = X < 0
if np.any(neg_mask):
    neg_cols_idx = np.where((X.min(axis=0) < 0))[0]
    print("[ALERTA] Colunas com valores negativos (clipping 0..1 será aplicado):")
    for j in neg_cols_idx[:10]:
        print(f"  - {df_dados.columns[1:][j]}: min={X[:,j].min()} max={X[:,j].max()}")

X = np.nan_to_num(X, nan=0.0, neginf=0.0, posinf=1.0)
X = np.clip(X, 0.0, 1.0)

# -------- alvo multilabel, sem descartar linhas --------
y_list = parse_multilabel(df_dados[COL_ALVO], class_names)
keep = [len(l) > 0 for l in y_list]  # exige ao menos 1 rótulo conhecido
if not any(keep):
    raise ValueError("Nenhuma linha possui rótulo em 'Alvo' que pertença ao conjunto de classes conhecidas.")
X = X[keep]
df_dados = df_dados.loc[keep].reset_index(drop=True)
y_list = [l for l, k in zip(y_list, keep) if k]

mlb = MultiLabelBinarizer(classes=class_names)
y_bin = mlb.fit_transform(y_list)

print(f"[INFO] Conjunto para CV/OOF: {X.shape[0]} linhas, {X.shape[1]} variáveis, {len(class_names)} classes.")
if HAS_MSKF:
    print("[INFO] Split: MultilabelStratifiedKFold")
else:
    print("[INFO] Split: KFold adaptativo (2..5)")

# ------------------ Heurística (baseline) ------------------
heur_scores = X @ W              # (n, K)
heur_probs  = softmax_rows(heur_scores)
heur_pred   = (heur_probs >= 0.5).astype(int)
heur_cls, heur_agg = compute_metrics(y_bin, heur_pred, heur_probs, class_names)

# ------------------ Modelos ------------------
log_clf = OneVsRestClassifier(
    LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
)
log_pipeline = make_pipeline(StandardScaler(with_mean=False), log_clf)

rf_base = RandomForestClassifier(
    n_estimators=600,
    max_depth=None,
    class_weight="balanced_subsample",
    random_state=RANDOM_STATE,
    n_jobs=-1
)
rf_clf = OneVsRestClassifier(rf_base)

# ------------------ OOF (sem usar a coluna Alvo no teste) ------------------
log_proba_oof, log_pred_oof, (log_cls_mean, log_agg_mean) = oof_predict(log_pipeline, X, y_bin, class_names)
rf_proba_oof,  rf_pred_oof,  (rf_cls_mean,  rf_agg_mean)  = oof_predict(rf_clf,       X, y_bin, class_names)

# escolher melhor por recall_macro (OOF)
try:
    log_rec = float(log_agg_mean["recall_macro"].iloc[0])
    rf_rec  = float(rf_agg_mean["recall_macro"].iloc[0])
    best_model_name = "log" if log_rec >= rf_rec else "rf"
except Exception:
    best_model_name = "log"

best_oof = log_proba_oof if best_model_name == "log" else rf_proba_oof

# Ensemble (OOF) = alpha*heur + (1-alpha)*best_oof
ens_proba_oof = (ALPHA_ENSEMBLE * heur_probs) + ((1.0 - ALPHA_ENSEMBLE) * best_oof)
ens_pred_oof  = (ens_proba_oof >= 0.5).astype(int)
ens_cls, ens_agg = compute_metrics(y_bin, ens_pred_oof, ens_proba_oof, class_names)

# ------------------ DataFrames de saída (OOF) ------------------
def build_all_results():
    out_log  = build_result_df(df_dados, log_proba_oof, class_names, topk=TOPK)
    out_rf   = build_result_df(df_dados, rf_proba_oof,  class_names, topk=TOPK)
    out_ens  = build_result_df(df_dados, ens_proba_oof, class_names, topk=TOPK)
    out_heur = build_result_df(df_dados, heur_probs,     class_names, topk=TOPK)
    return out_log, out_rf, out_ens, out_heur

df_log_out, df_rf_out, df_ens_out, df_heur_out = build_all_results()

# ------------------ Métricas para salvar ------------------
def pack_metrics(per_class: pd.DataFrame, agg: pd.DataFrame, titulo: str, secao_pc: str, secao_ag: str) -> pd.DataFrame:
    a = per_class.copy()
    a.insert(0, "secao", secao_pc)
    b = agg.copy()
    b.insert(0, "secao", secao_ag)
    b.insert(1, "titulo", titulo)
    return pd.concat([a, b], ignore_index=True)

met_log  = pack_metrics(log_cls_mean, log_agg_mean, "CV OOF (Logística OVR)", "por_classe (OOF médio)", "agregados (OOF médio)")
met_rf   = pack_metrics(rf_cls_mean,  rf_agg_mean,  "CV OOF (Random Forest OVR)", "por_classe (OOF médio)", "agregados (OOF médio)")
met_ens  = pack_metrics(ens_cls,      ens_agg,      f"Ensemble OOF = {ALPHA_ENSEMBLE:.2f}*Heur + {(1-ALPHA_ENSEMBLE):.2f}*{('LOG' if best_model_name=='log' else 'RF')}", "por_classe (OOF)", "agregados (OOF)")
met_heur = pack_metrics(heur_cls,     heur_agg,     "Heurística (X@W→softmax)", "por_classe", "agregados")

# ------------------ Aba de explicação ------------------
exp_rows = [
    ("Resultado_Logistica",  "Probabilidades (OOF) por classe via Regressão Logística One-vs-Rest; mostra ID, Alvo (verdadeiro), p_<classe> e ranking top1/top2/top3."),
    ("Resultado_Florestas",  "Probabilidades (OOF) por classe via Random Forest One-vs-Rest; mesma estrutura."),
    ("Resultado_Ensemble",   f"Combinação OOF: {ALPHA_ENSEMBLE:.0%} heurística + {100-ALPHA_ENSEMBLE*100:.0f}% {('Logística' if best_model_name=='log' else 'Random Forest')} (escolhida por maior recall_macro OOF)."),
    ("Resultado_Heuristica", "Saída da heurística pura (X@W) calibrada com softmax; baseline para comparação."),
    ("Metricas_Logistica",   "Métricas OOF (média dos folds): precisão, recall, F1, AUC por classe e agregados macro/weighted."),
    ("Metricas_Florestas",   "Idem para Random Forest OVR."),
    ("Metricas_Ensemble",    "Métricas OOF do Ensemble final."),
    ("Metricas_Heuristica",  "Métricas da heurística (comparando com o Alvo)."),
    ("Observacoes",          "Use RECALL por classe se quer minimizar falsos negativos; AUC pode ficar NaN quando um fold não tem positivos para aquela classe; dataset pequeno → variância maior."),
]
df_explicacao = pd.DataFrame(exp_rows, columns=["Aba", "Descricao"])

# ------------------ Salvar (preservando abas antigas) ------------------
saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_log_out,  ABA_SAIDA_LOG),
        (df_rf_out,   ABA_SAIDA_RF),
        (df_ens_out,  ABA_SAIDA_ENS),
        (df_heur_out, ABA_SAIDA_HEUR),
        (met_log,     ABA_MET_LOG),
        (met_rf,      ABA_MET_RF),
        (met_ens,     ABA_MET_ENS),
        (met_heur,    ABA_MET_HEUR),
        (df_explicacao, ABA_EXPLICAO),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_SAIDA_LOG, ABA_SAIDA_RF, ABA_SAIDA_ENS, ABA_SAIDA_HEUR,
      ABA_MET_LOG, ABA_MET_RF, ABA_MET_ENS, ABA_MET_HEUR, ABA_EXPLICAO)
print(f"↳ Ensemble (OOF): {ALPHA_ENSEMBLE:.2f}*Heur + {(1-ALPHA_ENSEMBLE):.2f}*{('LOG' if best_model_name=='log' else 'RF')}")
print(f"💾 Arquivo salvo em: {saved_path}")