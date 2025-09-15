
# -*- coding: utf-8 -*-
"""
05_tuna_heuristica_TreinoValid.py (v2.9.3 - gamma-in-softmax)
Mudanças principais (v2.9.2 -> v2.9.3):
- Remove COMPLETAMENTE a pós-regra. Agora "Sem Transtorno" (ST) é uma classe EXTRA no próprio softmax.
- "Gamma" passa a ser um PARÂMETRO treinável dentro do softmax:
    * Implementado como um viés (bias) escalar b_g na coluna da classe ST.
    * Opcionalmente pode treinar pesos por feature para ST (flag --train-st-weights).
- Otimização conjunta: W_core, (W_st se habilitado) e b_g são otimizados por gradiente proximal (L1/L2) via perda de entropia cruzada no TRAIN.
- Métricas de validação idênticas (macro_topk e ST_top1). Snapshots e abas preservados.
"""

import os, sys, argparse, shutil, tempfile, json
from datetime import datetime

# ---------- Pré-parse para threads de BLAS ----------
def _preparse_threads(argv):
    n_jobs = None; blas_threads = None
    for i, a in enumerate(argv):
        if a == "--n-jobs" and i+1 < len(argv):
            try: n_jobs = int(argv[i+1])
            except: pass
        if a == "--blas-threads" and i+1 < len(argv):
            try: blas_threads = int(argv[i+1])
            except: pass
    if blas_threads is None and n_jobs is not None:
        blas_threads = max(1, n_jobs)
    if blas_threads is not None:
        for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
            os.environ[k] = str(blas_threads)
        os.environ.setdefault("MKL_DYNAMIC","FALSE")
        os.environ.setdefault("OMP_WAIT_POLICY","PASSIVE")
        os.environ.setdefault("KMP_BLOCKTIME","0")
    os.environ.setdefault("PYTHONUTF8","1")
    os.environ.setdefault("PYTHONIOENCODING","utf-8")

_preparse_threads(sys.argv)

import numpy as np
import pandas as pd

# --- Hotkey 'q' para interromper no Windows console ---
try:
    import msvcrt
    def _user_requested_quit():
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch in ('q','Q')
        return False
except Exception:
    def _user_requested_quit():
        return False

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl  # garante engine
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)

    tmpdir = tempfile.mkdtemp(); tmpfile = os.path.join(tmpdir, "tmp.xlsx")
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile); base_existed = True
    except Exception:
        base_existed = False

    mode = "a" if base_existed else "w"
    writer_args = dict(engine="openpyxl", mode=mode)
    if mode == "a":
        writer_args["if_sheet_exists"] = "replace"

    with pd.ExcelWriter(tmpfile, **writer_args) as w:
        wrote_any = False
        for df, sheet in dfs_and_sheets:
            dfx = pd.DataFrame(df)
            if dfx.shape[0] == 0 and dfx.shape[1] == 0:
                dfx = pd.DataFrame({"_": []})
            dfx.to_excel(w, sheet_name=sheet, index=False)
            wrote_any = True
        if not wrote_any:
            pd.DataFrame({"_": []}).to_excel(w, sheet_name="Sheet1", index=False)

    try:
        os.replace(tmpfile, target_path); saved = target_path
    except PermissionError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
        shutil.copyfile(tmpfile, alt); saved = alt
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return saved

def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i")
             .replace("ó","o").replace("ô","o")
             .replace("ú","u"))

def parse_multilabel(series, core_classes, normal_label="Sem Transtorno"):
    CORE = set(core_classes); KNOWN = CORE | {normal_label}
    DELIMS = ["|",";",","]; out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS: s = s.replace(d,"|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não"): continue
            if lab in KNOWN: labs.append(lab)
        out.append(labs)
    return out

def y_distribution(y_lists, class_to_idx, K):
    n = len(y_lists); Y = np.zeros((n,K), dtype=float)
    for i,labs in enumerate(y_lists):
        pos = [class_to_idx[c] for c in labs if c in class_to_idx]
        if pos:
            w = 1.0/len(pos)
            Y[i,pos] = w
    return Y

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3, st_truth_mode=None, st_label=None):
    order = np.argsort(-proba, axis=1)
    topk = order[:,:k]
    accs = []
    for c in range(proba.shape[1]):
        c_name = idx_to_class[c]
        if st_truth_mode and st_label and c_name == st_label:
            mask = st_truth_mask(y_lists, st_label, mode=st_truth_mode)
        else:
            mask = np.array([c_name in labs for labs in y_lists], bool)
        sup = int(mask.sum())
        if sup == 0: continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits/sup)
    return float(np.mean(accs)) if accs else 0.0

def st_truth_mask(y_lists, st_label, mode="exclusive"):
    mask = []
    for labs in y_lists:
        has_st = (st_label in labs)
        if mode == "contains":
            mask.append(has_st)
        else:
            mask.append(has_st and all(c == st_label for c in labs))
    return np.array(mask, bool)

def st_top1_metric(y_lists, P, st_label, mode="exclusive"):
    st_mask = st_truth_mask(y_lists, st_label, mode=mode)
    sup = int(st_mask.sum())
    if sup == 0: return float("nan"), 0, 0
    st_idx = P.shape[1]-1
    top1 = np.argmax(P, axis=1)
    hits = int((top1[st_mask] == st_idx).sum())
    return (hits / sup), hits, sup

def project_bounds(W, adjustable_mask, W0, eps=1e-6):
    Wp = W.copy()
    Wp[~adjustable_mask] = W0[~adjustable_mask]
    Wp[adjustable_mask] = np.clip(Wp[adjustable_mask], -1e6, 1e6)  # amplo; clipping numérico
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask):
    G = grad.copy(); G[~adjustable_mask] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    thr = lr*l1
    Delta = np.sign(Delta)*np.maximum(np.abs(Delta)-thr, 0.0)
    W_new = W0 + Delta
    return project_bounds(W_new, adjustable_mask, W0, 1e-6)

def logit(p, eps=1e-9):
    p = np.clip(p, eps, 1-eps)
    return np.log(p/(1-p))

def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception: pass

    INPUT = args.input; OUTPUT = args.output or INPUT
    ABA_DADOS = args.sheet_dados; ABA_PONTOS_TUNADA = args.sheet_pontos_tunada; ABA_PONTOS = args.sheet_pontos
    ABA_RES_HEUR_TUN = args.sheet_resultado_tun; ABA_MET_HEUR_TUN = args.sheet_metricas_tun
    ABA_EXPLICAO = args.sheet_explicacao; ABA_REGRAS_NORMAL = args.sheet_regras_normal; ABA_COMPARATIVO_TUDO = args.sheet_comparativo
    ABA_DIAG = args.sheet_diag

    COLUNA_TAM = args.n_classes; LINHA_INICIO_PONTOS = args.linha_inicio_pontos; COL_ALVO = args.col_alvo; TOPK = args.topk

    L1 = args.l1; L2 = args.l2; LR = args.lr; MAX_ITERS = args.max_iters; CHECK_EVERY = args.check_every
    TARGET_MACRO_TOPK = args.target_macro_topk; RANDOM_STATE = args.seed

    ST_LABEL = args.normal_label; TRAIN_FRAC = args.train_frac; MIN_SUPPORT_VAL = args.min_support_val
    ST_MODE = args.st_truth_mode

    REPORT_JSON = args.report_json; N_JOBS = max(1, args.n_jobs)

    print("[INFO] Configuração:")
    print(f"  INPUT={INPUT} | OUTPUT={OUTPUT}")
    print(f"  Dados={ABA_DADOS} | Pontuação preferida Tunada? {args.prefer_tunada}")
    print(f"  TOPK={TOPK} | TRAIN_FRAC={TRAIN_FRAC:.4f} | MIN_SUPPORT_VAL={MIN_SUPPORT_VAL}")
    print(f"  seed={RANDOM_STATE} | max_iters={MAX_ITERS} | check_every={CHECK_EVERY} | n_jobs={N_JOBS}")
    print(f"  ST no softmax | g_init={args.g_init} (como prior -> bias) | train_st_weights={args.train_st_weights}")
    print(f"  REPORT_JSON={REPORT_JSON} | ST_MODE={ST_MODE}")

    # ----- Entrada principal -----
    df_all = pd.read_excel(INPUT, sheet_name=ABA_DADOS)
    xl = pd.ExcelFile(INPUT)
    usar_tunada = args.prefer_tunada and (ABA_PONTOS_TUNADA in xl.sheet_names)
    aba_pontos_usada = ABA_PONTOS_TUNADA if usar_tunada else ABA_PONTOS
    df_pont = pd.read_excel(INPUT, sheet_name=aba_pontos_usada)

    cols_dados = df_all.columns[1:]
    if len(cols_dados) == 0: raise ValueError(f"{ABA_DADOS} não possui colunas a partir da coluna B.")
    X_all = df_all[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    n_all, m = X_all.shape

    r0 = LINHA_INICIO_PONTOS - 2
    linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM: raise ValueError(f"Aba '{aba_pontos_usada}' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

    faltantes = [c for c in cols_dados if c not in df_pont.columns]
    if faltantes: raise ValueError(f"Colunas de {ABA_DADOS} ausentes em '{aba_pontos_usada}': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

    W_block = df_pont.loc[linhas_modelos, cols_dados]
    W0_sheet = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T  # (features x K0)
    K0 = W0_sheet.shape[1]
    if K0 != COLUNA_TAM: raise ValueError(f"Dimensão inesperada de W core: {W0_sheet.shape}, esperado K0={COLUNA_TAM}.")
    class_core = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist() if "Tipo de Transtorno" in df_pont.columns else [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    X_all = np.clip(np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)
    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core, normal_label=ST_LABEL)

    keep_nonempty = [len(l)>0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]; df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]
    n_all = X_all.shape[0]

    class_names_aug = class_core + [ST_LABEL]
    CORE = set(class_core)

    # split estratificado por suporte mínimo (com ST incluso)
    suportes_aug = {c: sum((c in labs) for labs in y_lists_all) for c in class_names_aug}
    eligible_labels_aug = {c for c,s in suportes_aug.items() if s >= MIN_SUPPORT_VAL}
    minor_labels_aug = set(class_names_aug) - eligible_labels_aug

    has_eligible_aug = np.array([any(c in eligible_labels_aug for c in l) for l in y_lists_all], bool)
    has_only_minor_aug= np.array([all(c in minor_labels_aug for c in l) for l in y_lists_all], bool)

    idx_tv_pool = np.where(has_eligible_aug)[0]
    idx_minor_train_for_grid = np.where(has_only_minor_aug)[0]

    rng = np.random.default_rng(RANDOM_STATE)
    y_tv_aug = [y_lists_all[i] for i in idx_tv_pool]
    targets_train = {c: int(np.floor(TRAIN_FRAC * sum(c in labs for labs in y_tv_aug))) for c in eligible_labels_aug}
    counts_train = {c: 0 for c in eligible_labels_aug}

    n_tv = len(y_tv_aug)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)
    assign_train_local = np.zeros(n_tv, bool); assign_val_local = np.zeros(n_tv, bool)

    for i in order_idx:
        labs = [c for c in y_tv_aug[i] if c in eligible_labels_aug]
        if not labs:
            assign_train_local[i] = True; continue
        needs = any(counts_train[c] < targets_train[c] for c in labs)
        if needs:
            assign_train_local[i] = True
            for c in labs:
                if counts_train[c] < targets_train[c]: counts_train[c] += 1
        else:
            assign_val_local[i] = True

    idx_train = np.unique(np.concatenate([idx_tv_pool[np.where(assign_train_local)[0]], idx_minor_train_for_grid]))
    idx_val   = np.setdiff1d(np.unique(idx_tv_pool[np.where(assign_val_local)[0]]), idx_train)

    split = np.array(["other"]*n_all, dtype=object)
    split[idx_train] = "train"
    split[idx_val] = "valid"
    split[idx_minor_train_for_grid] = "minor_train"

    # Construir alvos de treino com ST incluído
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for i,c in enumerate(class_names_aug)}

    y_train_aug = [y_lists_all[i] for i in idx_train]
    y_val_aug   = [y_lists_all[i] for i in idx_val]

    K_aug = len(class_names_aug)
    Y_train = y_distribution(y_train_aug, class_to_idx_aug, K_aug)

    # ---------- REGRA DE OURO ----------
    mask_w_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)  # (features,)
    W0_eff_core = W0_sheet.copy()
    W0_eff_core[~mask_w_all_zero, :] = np.clip(W0_eff_core[~mask_w_all_zero, :], 1e-6, 1.0)  # só para core

    # Montar W_aug com bias: shape (m+1, K_aug). Última linha = bias
    W0_aug = np.zeros((m+1, K_aug), dtype=float)
    W0_aug[:m, :K0] = W0_eff_core  # pesos core
    # bias inicial para ST a partir de g_init como prior vs. média dos outros (heurística simples)
    b_g0 = logit(args.g_init) - logit(1.0/(K_aug-1))  # desloca em relação ao "uniforme entre classes core"
    W0_aug[m, :K0] = 0.0
    W0_aug[m, K0]  = b_g0  # bias ST

    # Máscara de ajustáveis: 
    # - Core: todas features NÃO-congeladas e bias calibrável (permite shift comum)
    # - ST: se --train-st-weights False, só o bias (linha m, col K0) é ajustável; senão, todas as linhas da col K0.
    adjustable = np.zeros_like(W0_aug, dtype=bool)
    adjustable[:m, :K0] = ~mask_w_all_zero[:, None]
    adjustable[m, :K0]  = True  # permitir bias para core
    if args.train_st_weights:
        adjustable[:, K0] = True
    else:
        adjustable[m, K0] = True  # apenas viés ST

    # Estado treinável
    W = W0_aug.copy()

    X_train = X_all[idx_train]; X_val = X_all[idx_val]
    # Adiciona 1 para bias
    def with_bias(X):
        return np.concatenate([X, np.ones((X.shape[0],1), dtype=float)], axis=1)

    Xb_train = with_bias(X_train); Xb_val = with_bias(X_val); Xb_all = with_bias(X_all)

    def forward(Wmat, Xb):
        return softmax_rows(Xb @ Wmat)

    # Baseline
    P_val0 = forward(W, Xb_val)
    macro_val0 = macro_topk(y_val_aug, P_val0, class_to_idx_aug, idx_to_class_aug, k=TOPK,
                            st_truth_mode=ST_MODE, st_label=ST_LABEL)
    macro_val0_k3 = macro_topk(y_val_aug, P_val0, class_to_idx_aug, idx_to_class_aug, k=3,
                               st_truth_mode=ST_MODE, st_label=ST_LABEL)
    st_v0, st_hits_v0, st_sup_v0 = st_top1_metric(y_val_aug, P_val0, ST_LABEL, mode=ST_MODE)
    print(f"[BASE] OBJ_VALID={macro_val0:.3%}  VA1/VA2/VA3=?/?/{macro_val0_k3:.3%}  ST_top1={0 if np.isnan(st_v0) else st_v0:.3%}")

    best_score = macro_val0; best_W = W.copy()
    diag_rows = []
    no_improve = 0; total_checks = 0
    snapshot_count = 0; last_va3_saved = None

    for it in range(1, MAX_ITERS+1):
        if _user_requested_quit():
            print("[PARAR] Interrompido pelo usuário (tecla 'q')."); break

        # Gradiente (cross-entropy): dL/dlogits = (P - Y)/n
        P_tr = forward(W, Xb_train)
        n_tr = max(Xb_train.shape[0], 1)
        Gs   = (P_tr - Y_train) / n_tr
        Gw   = Xb_train.T @ Gs  # (m+1, K_aug)

        # Proximal step conjunto
        W = proximal_step(W, Gw, W0_aug, LR, L1, L2, adjustable)

        # Checagem
        if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
            total_checks += 1
            P_val = forward(W, Xb_val)
            macro_val_k1 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=1,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
            macro_val_k2 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=2,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
            macro_val_k3 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=3,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
            st_v, st_hits_v, st_sup_v = st_top1_metric(y_val_aug, P_val, ST_LABEL, mode=ST_MODE)

            obj_val = macro_val_k1 if TOPK==1 else (macro_val_k2 if TOPK==2 else macro_val_k3)

            improved = False
            if obj_val > best_score + 1e-6:
                best_score = obj_val; best_W = W.copy(); improved = True

            # extrai "gamma efetivo" médio (probabilidade média de ST na validação)
            gamma_eff = float(P_val[:, -1].mean())

            diag_rows.append({
                "iter": it,
                "obj_VALID": obj_val,
                "macro_top1_VALID": macro_val_k1, "macro_top2_VALID": macro_val_k2, "macro_top3_VALID": macro_val_k3,
                "ST_top1_VALID": 0 if np.isnan(st_v) else st_v,
                "bias_ST": float(W[m, K0]),
                "gamma_eff_VALID_mean": gamma_eff,
                "improved": improved
            })

            print(f"[IT {it:05d}] OBJ_VA={obj_val:.3%}  VA1/VA2/VA3={macro_val_k1:.3%}/{macro_val_k2:.3%}/{macro_val_k3:.3%}  "
                  f"ST_top1={0 if np.isnan(st_v) else st_v:.3%}  bias_ST={W[m,K0]:+.3f}  gamma_eff≈{gamma_eff:.3f}  best={best_score:.3%}")

            if improved:
                # Snapshot
                carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_dir = os.path.dirname(OUTPUT) if (OUTPUT and os.path.dirname(OUTPUT)) else os.path.dirname(INPUT)
                base_dir = base_dir or "."
                os.makedirs(base_dir, exist_ok=True)
                snap_name = f"best_softmaxST_{int(round(macro_val_k3*10000)):04d}_{carimbo}.xlsx"
                snap_path = os.path.join(base_dir, snap_name)

                saved_snap, va3_saved = _snapshot_save(INPUT, snap_path, best_W,
                                                       df_all, cols_dados, class_core, class_names_aug, split,
                                                       Xb_all, Xb_val, y_val_aug, class_to_idx_aug, idx_to_class_aug,
                                                       ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL,
                                                       ABA_EXPLICAO, ABA_DIAG, ABA_COMPARATIVO_TUDO, diag_rows, K0, args, mask_w_all_zero, W0_aug)
                snapshot_count += 1; last_va3_saved = va3_saved
                print(f"[SNAPSHOT] '{snap_name}' salvo (VA3={va3_saved:.3%})")

            if best_score >= TARGET_MACRO_TOPK:
                print("[PARAR] Atingiu meta."); break

            if not improved:
                no_improve += 1
                if no_improve >= args.early_stop_patience:
                    print("[PARAR] Early stop (sem melhora)."); break
            else:
                no_improve = 0

    # ---------- Final ----------
    W_tuned = project_bounds(best_W, adjustable, W0_aug, 1e-6)
    P_all = forward(W_tuned, Xb_all)

    P_val = forward(W_tuned, Xb_val)
    macro_final_valid_k1 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=1,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
    macro_final_valid_k2 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=2,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
    macro_final_valid_k3 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=3,
                                      st_truth_mode=ST_MODE, st_label=ST_LABEL)
    st_top1_final_valid, st_hits_valid, st_sup_valid = st_top1_metric(y_val_aug, P_val, ST_LABEL, mode=ST_MODE)
    print(f"[RESULTADO] VALID macro top-1/2/3 = {macro_final_valid_k1:.3%}/{macro_final_valid_k2:.3%}/{macro_final_valid_k3:.3%}  | ST_top1_VALID={0 if np.isnan(st_top1_final_valid) else st_top1_final_valid:.3%} (hits={st_hits_valid}/{st_sup_valid})")

    # ----- planilhas -----
    # Regrava Pontuação_Tunada com pesos core (sem bias) para manter compatibilidade visual
    df_pont_tun = pd.DataFrame(W_tuned[:m, :K0].T, columns=cols_dados)
    df_pont_tun.insert(0, "Tipo de Transtorno", class_core)

    df_res = df_all[[df_all.columns[0]]].copy()
    if COL_ALVO in df_all.columns: df_res[COL_ALVO] = df_all[COL_ALVO]
    for j, name in enumerate(class_names_aug): df_res[f"p_{name}"] = P_all[:, j]

    order_all = np.argsort(-P_all[:,:K0], axis=1)
    p1 = P_all[np.arange(n_all), order_all[:,0]]
    p2 = P_all[np.arange(n_all), order_all[:,1] if K0>1 else np.zeros(n_all,int)]
    margin = p1 - p2
    df_res["split"] = split
    df_res["p1_core"] = p1
    df_res["p2_core"] = p2
    df_res["margin_core"] = margin

    order_all_aug = np.argsort(-P_all, axis=1)
    tops_rec = []
    for i in range(P_all.shape[0]):
        rec = {}
        for t in range(min(3, P_all.shape[1])):
            c = order_all_aug[i, t]
            rec[f"top{t+1}_classe"] = class_names_aug[c]
            rec[f"top{t+1}_prob"]   = float(P_all[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    # Métricas por classe no VALID (topk escolhido)
    rows = []
    for c_idx, c_name in enumerate(class_names_aug):
        if c_name == ST_LABEL:
            mask = st_truth_mask(y_val_aug, ST_LABEL, mode=ST_MODE)
        else:
            mask = np.array([c_name in labs for labs in y_val_aug], bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, f"top{TOPK}_rate": np.nan, "acertos_topk": 0, "suporte": 0}); continue
        ord_c = np.argsort(-P_val[mask], axis=1)[:, :TOPK]
        hits = sum(c_idx in ord_c[r] for r in range(ord_c.shape[0]))
        rows.append({"classe": c_name, f"top{TOPK}_rate": hits / sup, "acertos_topk": hits, "suporte": sup})
    df_met_cls = pd.DataFrame(rows)

    df_met_sum = pd.DataFrame([{
        "macro_top1_VALID": float(macro_final_valid_k1),
        "macro_top2_VALID": float(macro_final_valid_k2),
        "macro_top3_VALID": float(macro_final_valid_k3),
        f"macro_top{TOPK}_VALID": df_met_cls[f"top{TOPK}_rate"].mean(skipna=True),
        "observacao": "Macro VALID com ST no próprio softmax (sem pós-regra)."
    }])

    df_metricas_tun = pd.concat([pd.DataFrame([{"secao":"agregado_VALID", **df_met_sum.iloc[0].to_dict()}]),
                                 df_met_cls.assign(secao="por_classe_VALID")], ignore_index=True)

    df_regras = pd.DataFrame([
        {"param": "bias_ST", "value": float(W_tuned[m, K0])},
        {"param": "gamma_eff_VALID_mean", "value": float(P_val[:, -1].mean())},
        {"param": "colunas_congeladas_pontuacao_zero", "value": int(mask_w_all_zero.sum())},
        {"param": "train_st_weights", "value": bool(args.train_st_weights)}
    ])

    df_expl_add = pd.DataFrame([{"Aba": ABA_RES_HEUR_TUN, "Descricao": "ST dentro do softmax (bias treinável); sem pós-regra; snapshots; top1..top3."}])
    df_comp_tudo = df_res.copy()
    saved_path = save_preserving_sheets(OUTPUT,
        [(df_pont_tun, ABA_PONTOS_TUNADA),
         (df_res, ABA_RES_HEUR_TUN),
         (df_metricas_tun, ABA_MET_HEUR_TUN),
         (df_regras, ABA_REGRAS_NORMAL),
         (df_expl_add, ABA_EXPLICAO),
         (pd.DataFrame(diag_rows), ABA_DIAG),
         (df_comp_tudo, ABA_COMPARATIVO_TUDO)])

    report = {"status":"ok",
              "macro_valid_top1": float(macro_final_valid_k1),
              "macro_valid_top2": float(macro_final_valid_k2),
              "macro_valid_top3": float(macro_final_valid_k3),
              "bias_ST": float(W_tuned[m, K0]),
              "gamma_eff_VALID_mean": float(P_val[:, -1].mean()),
              "seed": int(RANDOM_STATE),
              "lr": float(LR), "l1": float(L1), "l2": float(L2),
              "checks": int(total_checks), "used_sheet": aba_pontos_usada, "output_file": saved_path,
              "postrule": "none_softmax_ST", "n_jobs": int(N_JOBS)}
    try:
        base = os.path.splitext(OUTPUT or INPUT)[0]
        rep_path = args.report_json or base + "_report.json"
        with open(rep_path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas criadas/atualizadas:", ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_EXPLICAO, ABA_DIAG, ABA_COMPARATIVO_TUDO)
    print(f"💾 Arquivo salvo em: {saved_path}")
    print(f"➡️ VALID macro top-1/2/3 final: {macro_final_valid_k1:.3%}/{macro_final_valid_k2:.3%}/{macro_final_valid_k3:.3%} | ST_top1_VALID={0 if np.isnan(st_top1_final_valid) else st_top1_final_valid:.3%}")

# ---------- Snapshot helper ----------
def _snapshot_save(base_input_path, output_path, W_best,
                   ST_DF_ALL, cols_dados, class_core, class_names_aug, split,
                   Xb_all, Xb_val, y_val_aug, class_to_idx_aug, idx_to_class_aug,
                   ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL,
                   ABA_EXPLICAO, ABA_DIAG, ABA_COMPARATIVO_TUDO, diag_rows, K0, args, mask_w_all_zero, W0_aug):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    P_all = softmax_rows(Xb_all @ W_best)
    P_val = softmax_rows(Xb_val @ W_best)

    macro_val_top1 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=1,
                                st_truth_mode=args.st_truth_mode, st_label=args.normal_label)
    macro_val_top2 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=2,
                                st_truth_mode=args.st_truth_mode, st_label=args.normal_label)
    macro_val_top3 = macro_topk(y_val_aug, P_val, class_to_idx_aug, idx_to_class_aug, k=3,
                                st_truth_mode=args.st_truth_mode, st_label=args.normal_label)

    m = Xb_all.shape[1]-1  # features (sem bias)
    df_pont_tun = pd.DataFrame(W_best[:m, :K0].T, columns=cols_dados)
    df_pont_tun.insert(0, "Tipo de Transtorno", class_core)

    df_all = ST_DF_ALL.copy()
    df_res = df_all[[df_all.columns[0]]].copy()
    if args.col_alvo in df_all.columns: df_res[args.col_alvo] = df_all[args.col_alvo]
    for j, name in enumerate(class_names_aug): df_res[f"p_{name}"] = P_all[:, j]

    order_all = np.argsort(-P_all[:,:K0], axis=1)
    p1 = P_all[np.arange(P_all.shape[0]), order_all[:,0]]
    p2 = P_all[np.arange(P_all.shape[0]), order_all[:,1] if K0>1 else np.zeros(P_all.shape[0],int)]
    margin = p1 - p2
    df_res["split"] = split
    df_res["p1_core"] = p1
    df_res["p2_core"] = p2
    df_res["margin_core"] = margin

    order_all_aug = np.argsort(-P_all, axis=1)
    tops_rec = []
    for i in range(P_all.shape[0]):
        rec = {}
        for t in range(min(3, P_all.shape[1])):
            c = order_all_aug[i, t]
            rec[f"top{t+1}_classe"] = class_names_aug[c]
            rec[f"top{t+1}_prob"]   = float(P_all[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    rows = []
    for c_idx, c_name in enumerate(class_names_aug):
        if c_name == args.normal_label:
            mask = st_truth_mask(y_val_aug, args.normal_label, mode=args.st_truth_mode)
        else:
            mask = np.array([c_name in labs for labs in y_val_aug], bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, f"top{args.topk}_rate": np.nan, "acertos_topk": 0, "suporte": 0}); continue
        ord_c = np.argsort(-P_val[mask], axis=1)[:, :args.topk]
        hits = sum(c_idx in ord_c[r] for r in range(ord_c.shape[0]))
        rows.append({"classe": c_name, f"top{args.topk}_rate": hits / sup, "acertos_topk": hits, "suporte": sup})
    df_met_cls = pd.DataFrame(rows)

    df_met_sum = pd.DataFrame([{
        "macro_top1_VALID": macro_val_top1,
        "macro_top2_VALID": macro_val_top2,
        "macro_top3_VALID": macro_val_top3,
        f"macro_top{args.topk}_VALID": df_met_cls[f"top{args.topk}_rate"].mean(skipna=True),
        "observacao": "Macro VALID com ST no próprio softmax."
    }])

    df_metricas_tun = pd.concat([pd.DataFrame([{"secao":"agregado_VALID", **df_met_sum.iloc[0].to_dict()}]),
                                 df_met_cls.assign(secao="por_classe_VALID")], ignore_index=True)

    df_regras = pd.DataFrame([
        {"param": "bias_ST", "value": float(W_best[m, K0])},
        {"param": "gamma_eff_VALID_mean", "value": float(P_val[:, -1].mean())},
        {"param": "colunas_congeladas_pontuacao_zero", "value": int(mask_w_all_zero.sum())},
        {"param": "train_st_weights", "value": bool(args.train_st_weights)}
    ])

    df_expl_add = pd.DataFrame([{"Aba": ABA_RES_HEUR_TUN, "Descricao": "Snapshot (ST no softmax)."}])
    df_comp_tudo = df_res.copy()

    saved_path = save_preserving_sheets(output_path,
        [(df_pont_tun, ABA_PONTOS_TUNADA),
         (df_res, ABA_RES_HEUR_TUN),
         (df_metricas_tun, ABA_MET_HEUR_TUN),
         (df_regras, ABA_REGRAS_NORMAL),
         (df_expl_add, ABA_EXPLICAO),
         (pd.DataFrame(diag_rows), ABA_DIAG),
         (df_comp_tudo, ABA_COMPARATIVO_TUDO)])
    return saved_path, float(macro_val_top3)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ST como classe no softmax (sem pós-regra); gradiente proximal conjunto; snapshots; regra de ouro; top1..3 no output.")
    p.add_argument("--input", default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx")
    p.add_argument("--output", default=None)
    p.add_argument("--sheet-dados", default="TDados_clean")
    p.add_argument("--sheet-pontos", default="Pontuação")
    p.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    p.add_argument("--sheet-resultado-tun", default="Resultado_Heuristica_Tunada")
    p.add_argument("--sheet-metricas-tun", default="Metricas_Heuristica_Tunada")
    p.add_argument("--sheet-explicacao", default="Explicacao_Resultados")
    p.add_argument("--sheet-regras-normal", default="Regras_Normal")
    p.add_argument("--sheet-comparativo", default="Comparativo_TopK_Tudo")
    p.add_argument("--sheet-diag", dest="sheet_diag", default="Diagnostico_ST_SUM")
    p.add_argument("--prefer-tunada", action="store_true", default=True)
    p.add_argument("--n-classes", type=int, default=11)
    p.add_argument("--linha-inicio-pontos", type=int, default=3)
    p.add_argument("--col-alvo", default="Alvo")
    p.add_argument("--train-frac", type=float, default=2.0/3.0)
    p.add_argument("--min-support-val", type=int, default=2)
    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--l1", type=float, default=0.0025)
    p.add_argument("--l2", type=float, default=0.02)
    p.add_argument("--lr", type=float, default=0.02)
    p.add_argument("--max-iters", type=int, default=10000)
    p.add_argument("--check-every", type=int, default=10)
    p.add_argument("--early-stop-patience", type=int, default=1000)
    p.add_argument("--target-macro-topk", type=float, default=0.99)
    p.add_argument("--normal-label", default="Sem Transtorno")
    p.add_argument("--g-init", type=float, default=0.30, help="Prior inicial para ST (convertido em bias).")
    p.add_argument("--train-st-weights", action="store_true", help="Se ligado, treina pesos por feature para a classe ST (não só o bias).")
    p.add_argument("--report-json", default="report.json")
    p.add_argument("--n-jobs", type=int, default=os.cpu_count())
    p.add_argument("--blas-threads", type=int, default=1)
    p.add_argument("--st-truth-mode", dest="st_truth_mode", choices=["exclusive","contains"], default="contains",
                   help="Como considerar rótulo verdadeiro de ST: 'exclusive' ou 'contains'.")
    args = p.parse_args(); np.random.seed(args.seed); main(args)
