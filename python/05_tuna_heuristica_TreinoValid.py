"""
05_tuna_heuristica_TreinoValid.py (v2.3)
- Checkpoint: reotimiza (T1,T2,γ) no TREINO e aplica TREINO/VALID.
- Objetivo do grid configurável: st_top1 (padrão), macro, weighted (α·macro + (1-α)·st_top1).
- Resultado_Heuristica_Tunada: adiciona colunas de auditoria (split, p1, p2, margin, st_rule_on).
- Metricas_Heuristica_Tunada: inclui 'acertos_topk' por classe.
- Regras_Normal: grava taxas de acionamento ST em TRAIN/VALID/ALL do último checkpoint.
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
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

def _init_env_for_worker():
    for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(k, "1")
    os.environ.setdefault("MKL_DYNAMIC","FALSE")
    os.environ.setdefault("OMP_WAIT_POLICY","PASSIVE")
    os.environ.setdefault("KMP_BLOCKTIME","0")
    os.environ.setdefault("PYTHONUTF8","1")
    os.environ.setdefault("PYTHONIOENCODING","utf-8")

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl
    tmpdir = tempfile.mkdtemp(); tmpfile = os.path.join(tmpdir, "tmp.xlsx")
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile); base_existed = True
    except Exception:
        with pd.ExcelWriter(tmpfile, engine="openpyxl", mode="w"): pass
    mode = "a" if base_existed else "w"
    with pd.ExcelWriter(tmpfile, engine="openpyxl", mode=mode, if_sheet_exists="replace") as w:
        for df, sheet in dfs_and_sheets: df.to_excel(w, sheet_name=sheet, index=False)
    try:
        os.replace(tmpfile, target_path); saved = target_path
    except PermissionError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S"); alt = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
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

def project_bounds(W, adjustable_mask, W0, eps=1e-6):
    Wp = W.copy()
    Wp[~adjustable_mask,:] = W0[~adjustable_mask,:]
    if np.any(adjustable_mask):
        Wp[adjustable_mask,:] = np.clip(Wp[adjustable_mask,:], eps, 1.0)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask, eps):
    G = grad.copy(); G[~adjustable_mask,:] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    thr = lr*l1
    Delta = np.sign(Delta)*np.maximum(np.abs(Delta)-thr, 0.0)
    W_new = W0 + Delta
    return project_bounds(W_new, adjustable_mask, W0, eps)

def add_normal_by_rule(P_core, T1, T2, gamma, st_name="Sem Transtorno"):
    n, K0 = P_core.shape
    order = np.argsort(-P_core, axis=1)
    top1 = P_core[np.arange(n), order[:,0]]
    top2 = P_core[np.arange(n), order[:,1] if K0>1 else np.zeros(n,int)]
    hits = (top1 < T1) & ((top1 - top2) < T2)
    p_norm = np.where(hits, gamma, 0.0)
    P_scaled = P_core * (1.0 - p_norm)[:,None]
    P_aug = np.concatenate([P_scaled, p_norm[:,None]], axis=1)
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), 1e-12)
    return P_aug, hits, top1, top2

def st_truth_mask(y_lists, st_label, mode="exclusive"):
    mask = []
    for labs in y_lists:
        has_st = (st_label in labs)
        if mode == "contains":
            mask.append(has_st)
        else:
            mask.append(has_st and all(c == st_label for c in labs))
    return np.array(mask, bool)

def st_top1_metric(y_lists, P_aug, st_label, mode="exclusive"):
    st_mask = st_truth_mask(y_lists, st_label, mode=mode)
    sup = int(st_mask.sum())
    if sup == 0: return float("nan"), 0, 0
    st_idx = P_aug.shape[1]-1
    top1 = np.argmax(P_aug, axis=1)
    hits = int((top1[st_mask] == st_idx).sum())
    return (hits / sup), hits, sup

def save_diag_sheet(path, sheet_name, rows):
    if not rows: return
    df = pd.DataFrame(rows)
    saved = save_preserving_sheets(path, [(df, sheet_name)])
    return saved

def _score_tuple(macro_tr, st1_tr, objective, alpha):
    if objective == "macro": return macro_tr
    if objective == "st_top1": return st1_tr
    # weighted
    return alpha*macro_tr + (1.0-alpha)*st1_tr

def _eval_combo(P_tr_core, y_train_aug, class_to_idx_aug, idx_to_class_aug, topk, st_label,
                T1, T2, g, st_truth_mode, objective, alpha):
    P_tr_aug, hits_tr, _, _ = add_normal_by_rule(P_tr_core, T1, T2, g, st_name=st_label)
    macro_tr = macro_topk(y_train_aug, P_tr_aug, class_to_idx_aug, idx_to_class_aug, k=topk,
                          st_truth_mode=st_truth_mode, st_label=st_label)
    st_tr, _, _ = st_top1_metric(y_train_aug, P_tr_aug, st_label, mode=st_truth_mode)
    score = _score_tuple(macro_tr, 0 if np.isnan(st_tr) else st_tr, objective, alpha)
    return (score, macro_tr, st_tr, T1, T2, g, float(hits_tr.mean()))

def grid_search_postrule_threads(P_tr_core, y_train_aug, class_names_aug, topk,
                                 T1s, T2s, Gs, n_jobs, st_label, st_truth_mode,
                                 objective, alpha):
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for i,c in enumerate(class_names_aug)}
    combos = [(t1,t2,g) for t1 in T1s for t2 in T2s for g in Gs]
    best = (-1.0, None, None, None, None, None, None)  # score, macro_tr, st_tr, T1, T2, g, hit
    workers = max(1, int(n_jobs))
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_eval_combo, P_tr_core, y_train_aug, class_to_idx_aug, idx_to_class_aug, topk,
                          st_label, *c, st_truth_mode, objective, alpha) for c in combos]
        for fut in as_completed(futs):
            res = fut.result()
            if res[0] > best[0] + 1e-9: best = res
    return best  # (score, macro_tr, st_tr, T1, T2, g, hit_tr)

def _ga_worker_eval(Wm, X_train_grid, X_val_grid, y_train_aug, y_val_aug,
                    class_names_aug, class_to_idx_aug, idx_to_class_aug, TOPK,
                    GRID_T1, GRID_T2, GRID_G, ST_LABEL, ST_MODE, OBJECTIVE, ALPHA):
    def grid_eval_local(W_current):
        P_tr_core = softmax_rows(X_train_grid @ W_current)
        score, macro_tr, st_tr, T1b, T2b, Gb, hit_tr = grid_search_postrule_threads(
            P_tr_core, y_train_aug, class_names_aug, TOPK, GRID_T1, GRID_T2, GRID_G,
            n_jobs=1, st_label=ST_LABEL, st_truth_mode=ST_MODE, objective=OBJECTIVE, alpha=ALPHA
        )
        P_v_core = softmax_rows(X_val_grid @ W_current)
        P_v_aug, hits_v, _, _ = add_normal_by_rule(P_v_core, T1b, T2b, Gb, st_name=ST_LABEL)
        macro_val = macro_topk(y_val_aug, P_v_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK,
                               st_truth_mode=ST_MODE, st_label=ST_LABEL)
        st_v, st_hits_v, st_sup_v = st_top1_metric(y_val_aug, P_v_aug, ST_LABEL, mode=ST_MODE)
        return (macro_val, T1b, T2b, Gb, st_v, st_hits_v, st_sup_v, float(hits_v.mean()))
    return grid_eval_local(Wm)

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

    LAMBDA_L1 = args.l1; LAMBDA_L2 = args.l2; LR = args.lr; MAX_ITERS = args.max_iters; CHECK_EVERY = args.check_every
    TARGET_MACRO_TOPK = args.target_macro_topk; EPS_W = args.eps_w; RANDOM_STATE = args.seed

    ST_LABEL = args.normal_label; TRAIN_FRAC = args.train_frac; MIN_SUPPORT_VAL = args.min_support_val
    ST_MODE = args.st_truth_mode
    OBJECTIVE = args.grid_objective; ALPHA = args.grid_alpha

    GRID_T1 = np.linspace(args.grid_t1_min, args.grid_t1_max, args.grid_t1_steps)
    GRID_T2 = np.linspace(args.grid_t2_min, args.grid_t2_max, args.grid_t2_steps)
    GRID_G  = np.linspace(args.grid_g_min,  args.grid_g_max,  args.grid_g_steps)

    GA_NUM = args.ga_num_mutants; GA_COLS = args.ga_mutate_cols; GA_SCALE = args.ga_mutation_scale

    REPORT_JSON = args.report_json; N_JOBS = max(1, args.n_jobs); N_PROCS = max(0, args.procs)

    print("[INFO] Configuração:")
    print(f"  INPUT={INPUT} | OUTPUT={OUTPUT}")
    print(f"  Dados={ABA_DADOS} | Pontuação preferida Tunada? {args.prefer_tunada}")
    print(f"  TOPK={TOPK} | TRAIN_FRAC={TRAIN_FRAC:.4f} | MIN_SUPPORT_VAL={MIN_SUPPORT_VAL}")
    print(f"  seed={RANDOM_STATE} | max_iters={MAX_ITERS} | check_every={CHECK_EVERY} | n_jobs={N_JOBS} | procs={N_PROCS}")
    print(f"  grid T1=[{args.grid_t1_min},{args.grid_t1_max}]x{args.grid_t1_steps}  "
          f"T2=[{args.grid_t2_min},{args.grid_t2_max}]x{args.grid_t2_steps}  "
          f"gamma=[{args.grid_g_min},{args.grid_g_max}]x{args.grid_g_steps}")
    print(f"  GA: num_mutants={GA_NUM} mutate_cols={GA_COLS} scale={GA_SCALE}")
    print(f"  REPORT_JSON={REPORT_JSON} | ST_MODE={ST_MODE} | OBJECTIVE={OBJECTIVE} α={ALPHA}")

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
    W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
    K0 = W0.shape[1]; 
    if K0 != COLUNA_TAM: raise ValueError(f"Dimensão inesperada de W core: {W0.shape}, esperado K0={COLUNA_TAM}.")
    class_core = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist() if "Tipo de Transtorno" in df_pont.columns else [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    X_all = np.clip(np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)
    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core, normal_label=ST_LABEL)

    keep_nonempty = [len(l)>0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]; df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]
    n_all = X_all.shape[0]

    CORE = set(class_core)
    y_core_all = [[c for c in labs if c in CORE] for labs in y_lists_all]
    class_names_aug = class_core + [ST_LABEL]

    suportes_aug = {c: sum(c in labs for labs in y_lists_all) for c in class_names_aug}
    eligible_labels_aug = {c for c,s in suportes_aug.items() if s >= args.min_support_val}
    minor_labels_aug = set(class_names_aug) - eligible_labels_aug

    has_eligible_aug = np.array([any(c in eligible_labels_aug for c in l) for l in y_lists_all], bool)
    has_only_minor_aug= np.array([all(c in minor_labels_aug for c in l) for l in y_lists_all], bool)

    idx_tv_pool = np.where(has_eligible_aug)[0]
    idx_minor_train_for_grid = np.where(has_only_minor_aug)[0]

    rng = np.random.default_rng(RANDOM_STATE)
    y_tv_aug = [y_lists_all[i] for i in idx_tv_pool]

    targets_train = {c: int(np.floor(args.train_frac * sum(c in labs for labs in y_tv_aug))) for c in eligible_labels_aug}
    counts_train = {c: 0 for c in eligible_labels_aug}

    n_tv = len(y_tv_aug)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)
    assign_train_local = np.zeros(n_tv, bool); assign_val_local = np.zeros(n_tv, bool)

    for i in order_idx:
        labs = [c for c in y_tv_aug[i] if c in eligible_labels_aug]
        if not labs: assign_train_local[i] = True; continue
        needs = any(counts_train[c] < targets_train[c] for c in labs)
        if needs:
            assign_train_local[i] = True
            for c in labs:
                if counts_train[c] < targets_train[c]: counts_train[c] += 1
        else:
            assign_val_local[i] = True

    idx_train_grid = np.unique(np.concatenate([idx_tv_pool[np.where(assign_train_local)[0]], idx_minor_train_for_grid]))
    idx_val_grid   = np.setdiff1d(np.unique(idx_tv_pool[np.where(assign_val_local)[0]]), idx_train_grid)

    # Split tag: train/valid/minor_train
    split = np.array(["other"]*n_all, dtype=object)
    split[idx_train_grid] = "train"
    split[idx_val_grid] = "valid"
    split[idx_minor_train_for_grid] = "minor_train"

    has_core_label = np.array([len([c for c in labs if c in CORE])>0 for labs in y_lists_all], bool)
    idx_train_grad = idx_train_grid[has_core_label[idx_train_grid]]

    adjustable_mask = (X_all.max(axis=0) > 0)
    print(f"[INFO] Colunas congeladas (X coluna toda = 0): {int((~adjustable_mask).sum())}")
    print(f"[INFO] Colunas ajustáveis (X tem algum valor >0): {int(adjustable_mask.sum())}")

    class_to_idx_core = {c:i for i,c in enumerate(class_core)}
    idx_to_class_core = {i:c for i,c in enumerate(class_core)}
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for i,c in enumerate(class_names_aug)}

    X_train_grad = X_all[idx_train_grad]; X_train_grid = X_all[idx_train_grid]; X_val_grid = X_all[idx_val_grid]
    y_train_core = [y_core_all[i] for i in idx_train_grad]
    y_train_aug  = [y_lists_all[i] for i in idx_train_grid]
    y_val_aug    = [y_lists_all[i] for i in idx_val_grid]

    K0 = len(class_core)
    Ydist_train = y_distribution(y_train_core, class_to_idx_core, K0)

    W0 = np.clip(W0, args.eps_w, 1.0)
    W = W0.copy()
    diag_rows = []

    def grid_eval(W_current):
        P_tr_core = softmax_rows(X_train_grid @ W_current)
        score, macro_tr, st_tr, T1_b, T2_b, G_b, hit_tr = grid_search_postrule_threads(
            P_tr_core, y_train_aug, class_names_aug, args.topk, GRID_T1, GRID_T2, GRID_G, N_JOBS,
            st_label=ST_LABEL, st_truth_mode=ST_MODE, objective=OBJECTIVE, alpha=ALPHA
        )
        P_tr_aug, hits_tr_mask, p1_tr, p2_tr = add_normal_by_rule(P_tr_core, T1_b, T2_b, G_b, st_name=ST_LABEL)
        P_v_core  = softmax_rows(X_val_grid @ W_current)
        P_v_aug, hits_v_mask, p1_v, p2_v = add_normal_by_rule(P_v_core,  T1_b, T2_b, G_b, st_name=ST_LABEL)
        macro_val = macro_topk(y_val_aug, P_v_aug, class_to_idx_aug, idx_to_class_aug, k=args.topk,
                               st_truth_mode=ST_MODE, st_label=ST_LABEL)
        st_v, st_hits_v, st_sup_v = st_top1_metric(y_val_aug, P_v_aug, ST_LABEL, mode=ST_MODE)
        return (macro_tr, macro_val, (T1_b, T2_b, G_b), float(hits_tr_mask.mean()), float(hits_v_mask.mean()),
                st_tr, st_v, st_hits_v, st_sup_v)

    # baseline
    macro_tr0, macro_val0, (best_T1, best_T2, best_G), hit_tr0, hit_v0, st_tr0, st_v0, _, _ = grid_eval(W)
    best_macro_val = macro_val0; best_W = W.copy()
    print(f"[INFO] Baseline: VALID macro top-{args.topk}={best_macro_val:.3%} | "
          f"T1={best_T1:.3f} T2={best_T2:.3f} γ={best_G:.3f} | "
          f"ST_top1(TR/VL)={st_tr0:.3%}/{st_v0:.3%} | acionamento(TR/VL)={hit_tr0:.1%}/{hit_v0:.1%}")

    no_improve = 0; total_checks = 0
    for it in range(1, args.max_iters+1):
        if X_train_grad.shape[0] > 0:
            P_tr = softmax_rows(X_train_grad @ W)
            n_tr = max(X_train_grad.shape[0], 1)
            Gs   = (P_tr - Ydist_train) / n_tr
            Gw   = X_train_grad.T @ Gs
            W = proximal_step(W, Gw, W0, args.lr, args.l1, args.l2, adjustable_mask, args.eps_w)

        if it % args.check_every == 0 or it == 1 or it == args.max_iters:
            total_checks += 1
            macro_tr, macro_val, (T1_c,T2_c,G_c), hit_tr, hit_v, st_tr, st_v, st_hits_v, st_sup_v = grid_eval(W)

            improved = False
            if macro_val > best_macro_val + 1e-6:
                best_macro_val = macro_val; best_W = W.copy()
                best_T1, best_T2, best_G = T1_c, T2_c, G_c
                improved = True

            diag_rows.append({
                "iter": it, "T1": T1_c, "T2": T2_c, "gamma": G_c,
                "macro_top{}_TRAIN".format(args.topk): macro_tr,
                "macro_top{}_VALID".format(args.topk): macro_val,
                "ST_top1_TRAIN": st_tr, "ST_top1_VALID": st_v,
                "ST_aciona_rate_TRAIN": hit_tr, "ST_aciona_rate_VALID": hit_v,
                "ST_hits_VALID": st_hits_v, "ST_sup_VALID": st_sup_v,
                "improved": improved
            })

            print(f"[IT {it:03d}] macro(TR/VA)={macro_tr:.3%}/{macro_val:.3%}  "
                  f"T1={T1_c:.3f} T2={T2_c:.3f} γ={G_c:.3f}  "
                  f"ST_top1(TR/VA)={st_tr:.3%}/{st_v:.3%}  "
                  f"aciona(TR/VA)={hit_tr:.1%}/{hit_v:.1%}  bestVA={best_macro_val:.3%}")

            if best_macro_val >= args.target_macro_topk: print("[PARAR] Atingiu meta."); break
            if not improved:
                no_improve += 1
                if no_improve >= args.early_stop_patience:
                    print("[PARAR] Early stop (sem melhora)."); break
            else:
                no_improve = 0

    # --- Final: aplica melhor trio em TODOS ---
    W_tuned = project_bounds(best_W, adjustable_mask, W0, args.eps_w)
    P_all_core = softmax_rows(X_all @ W_tuned)
    P_all_aug, hits_all, p1_all, p2_all = add_normal_by_rule(P_all_core, best_T1, best_T2, best_G, st_name=ST_LABEL)

    # VAL para relatório final (com mesmo trio)
    P_val_core = softmax_rows(X_val_grid @ W_tuned)
    P_val_aug, hits_val, p1_val, p2_val = add_normal_by_rule(P_val_core, best_T1, best_T2, best_G, st_name=ST_LABEL)
    macro_final_valid = macro_topk(y_val_aug, P_val_aug, class_to_idx_aug, idx_to_class_aug, k=args.topk,
                                   st_truth_mode=ST_MODE, st_label=ST_LABEL)
    st_top1_final_valid, st_hits_valid, st_sup_valid = st_top1_metric(y_val_aug, P_val_aug, ST_LABEL, mode=ST_MODE)

    print(f"[RESULTADO] VALID macro top-{args.topk} = {macro_final_valid:.3%}  | ST_top1_VALID={st_top1_final_valid:.3%}  (hits={st_hits_valid}/{st_sup_valid})")

    # ---- Abas de saída ----
    df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
    df_pont_tun.insert(0, "Tipo de Transtorno", class_core)

    df_res = df_all[[df_all.columns[0]]].copy()
    if COL_ALVO in df_all.columns: df_res[COL_ALVO] = df_all[COL_ALVO]
    for j, name in enumerate(class_names_aug): df_res[f"p_{name}"] = P_all_aug[:, j]

    # Auditoria por linha
    order_all = np.argsort(-P_all_core, axis=1)
    p1 = P_all_core[np.arange(n_all), order_all[:,0]]
    p2 = P_all_core[np.arange(n_all), order_all[:,1] if K0>1 else np.zeros(n_all,int)]
    margin = p1 - p2
    df_res["split"] = split
    df_res["p1_core"] = p1
    df_res["p2_core"] = p2
    df_res["margin_core"] = margin
    df_res["st_rule_on"] = hits_all.astype(int)

    tops_rec = []
    order_all_aug = np.argsort(-P_all_aug, axis=1)
    for i in range(P_all_aug.shape[0]):
        rec = {}
        for t in range(min(args.topk, P_all_aug.shape[1])):
            c = order_all_aug[i, t]; rec[f"top{t+1}_classe"] = class_names_aug[c]; rec[f"top{t+1}_prob"] = float(P_all_aug[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    # Métricas VALID por classe (inclui ST) + acertos
    rows = []
    for c_idx, c_name in enumerate(class_names_aug):
        # máscara com regra especial para ST (exclusive/contains)
        if c_name == ST_LABEL:
            mask = st_truth_mask(y_val_aug, ST_LABEL, mode=ST_MODE)
        else:
            mask = np.array([c_name in labs for labs in y_val_aug], bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, f"top{args.topk}_rate": np.nan, "acertos_topk": 0, "suporte": 0})
            continue
        ord_c = np.argsort(-P_val_aug[mask], axis=1)[:, :args.topk]
        hits = sum(c_idx in ord_c[r] for r in range(ord_c.shape[0]))
        rows.append({"classe": c_name, f"top{args.topk}_rate": hits / sup, "acertos_topk": hits, "suporte": sup})
    df_met_cls = pd.DataFrame(rows)
    df_met_sum = pd.DataFrame([{f"macro_top{args.topk}_VALID": df_met_cls[f"top{args.topk}_rate"].mean(skipna=True),
                                "observacao": ("Macro top-k na VALID com pós-regra ST ajustada no TREINO.")}])
    df_metricas_tun = pd.concat([pd.DataFrame([{"secao":"agregado_VALID", **df_met_sum.iloc[0].to_dict()}]),
                                 df_met_cls.assign(secao="por_classe_VALID")], ignore_index=True)

    # Regras / resumo final
    df_regras = pd.DataFrame([
        {"param": "T1", "value": best_T1},
        {"param": "T2", "value": best_T2},
        {"param": "gamma", "value": best_G},
        {"param": "taxa_acionamento_regra_no_TREINO", "value": float(np.nan if not diag_rows else diag_rows[-1]["ST_aciona_rate_TRAIN"])},
        {"param": "taxa_acionamento_regra_na_VALID", "value": float(np.nan if not diag_rows else diag_rows[-1]["ST_aciona_rate_VALID"])},
        {"param": "taxa_acionamento_regra_no_ALL", "value": float(hits_all.mean())},
        {"param": "aba_pesos_utilizada", "value": aba_pontos_usada},
        {"param": "ST_top1_VALID_final", "value": st_top1_final_valid},
    ])

    df_expl_add = pd.DataFrame([{"Aba": ABA_RES_HEUR_TUN, "Descricao": "ST na pós-regra; métricas por checkpoint em Diagnostico_ST_SUM; objetivo de grid configurável."}])
    df_comp_tudo = df_res.copy()
    saved_path = save_preserving_sheets(OUTPUT,
        [(df_pont_tun, ABA_PONTOS_TUNADA),
         (df_res, ABA_RES_HEUR_TUN),
         (df_metricas_tun, ABA_MET_HEUR_TUN),
         (df_regras, ABA_REGRAS_NORMAL),
         (df_expl_add, ABA_EXPLICAO),
         (pd.DataFrame(diag_rows), ABA_DIAG),
         (df_comp_tudo, ABA_COMPARATIVO_TUDO)])

    report = {"status":"ok","converged": bool(best_macro_val >= args.target_macro_topk - 1e-12),
              "macro_valid": float(macro_final_valid), "target_macro": float(args.target_macro_topk),
              "best_T1": float(best_T1), "best_T2": float(best_T2), "best_gamma": float(best_G),
              "hit_rate_train": float(np.nan if not diag_rows else diag_rows[-1]["ST_aciona_rate_TRAIN"]),
              "seed": int(RANDOM_STATE),
              "grid": {"t1_min": float(GRID_T1.min()), "t1_max": float(GRID_T1.max()), "t1_steps": int(len(GRID_T1)),
                       "t2_min": float(GRID_T2.min()), "t2_max": float(GRID_T2.max()), "t2_steps": int(len(GRID_T2)),
                       "g_min": float(GRID_G.min()), "g_max": float(GRID_G.max()), "g_steps": int(len(GRID_G))},
              "lr": float(args.lr), "l1": float(args.l1), "l2": float(args.l2),
              "ga": {"num_mutants": int(GA_NUM), "mutate_cols": int(GA_COLS), "mutation_scale": float(GA_SCALE)},
              "checks": int(total_checks), "used_sheet": aba_pontos_usada, "output_file": saved_path,
              "postrule_on": True, "st_in_W": False, "n_jobs": int(N_JOBS), "procs": int(N_PROCS),
              "st_top1_train": float(np.nan if not diag_rows else diag_rows[-1]["ST_top1_TRAIN"]),
              "st_top1_valid": float(np.nan if not diag_rows else diag_rows[-1]["ST_top1_VALID"]),
              "st_hit_valid": float(np.nan if not diag_rows else diag_rows[-1]["ST_aciona_rate_VALID"]),
              "st_mode": ST_MODE, "grid_objective": OBJECTIVE, "grid_alpha": ALPHA}
    try:
        base = os.path.splitext(OUTPUT or INPUT)[0]
        rep_path = args.report_json or base + "_report.json"
        with open(rep_path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas criadas/atualizadas:", ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_EXPLICAO, ABA_DIAG, ABA_COMPARATIVO_TUDO)
    print(f"💾 Arquivo salvo em: {saved_path}")
    print(f"➡️ VALID macro top-{args.topk} final: {macro_final_valid:.3%} | ST_top1_VALID={st_top1_final_valid:.3%}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Heurística com ST na pós-regra; grid/GA paralelos + diagnóstico por checkpoint + objetivo configurável.")
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
    p.add_argument("--l1", type=float, default=1e-3)
    p.add_argument("--l2", type=float, default=1e-2)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--max-iters", type=int, default=10000)
    p.add_argument("--check-every", type=int, default=10)
    p.add_argument("--early-stop-patience", type=int, default=100)
    p.add_argument("--target-macro-topk", type=float, default=0.99)
    p.add_argument("--eps-w", type=float, default=1e-6)
    p.add_argument("--normal-label", default="Sem Transtorno")
    p.add_argument("--grid-t1-min", type=float, default=0.18)
    p.add_argument("--grid-t1-max", type=float, default=0.90)
    p.add_argument("--grid-t1-steps", type=int, default=100)
    p.add_argument("--grid-t2-min", type=float, default=0.02)
    p.add_argument("--grid-t2-max", type=float, default=0.50)
    p.add_argument("--grid-t2-steps", type=int, default=100)
    p.add_argument("--grid-g-min", type=float, default=0.10)
    p.add_argument("--grid-g-max", type=float, default=0.95)
    p.add_argument("--grid-g-steps", type=int, default=100)
    p.add_argument("--ga-num-mutants", type=int, default=50)
    p.add_argument("--ga-mutate-cols", type=int, default=2)
    p.add_argument("--ga-mutation-scale", type=float, default=0.05)
    p.add_argument("--report-json", default=None)
    p.add_argument("--n-jobs", type=int, default=os.cpu_count() or 4, help="Threads para grid/GA.")
    p.add_argument("--blas-threads", type=int, default=None, help="Threads de BLAS (MKL/OMP).")
    p.add_argument("--procs", type=int, default=0, help="Processos para GA (0=threads).")
    p.add_argument("--st-truth-mode", dest="st_truth_mode", choices=["exclusive","contains"], default="exclusive",
                   help="Como considerar rótulo verdadeiro de ST: 'exclusive' (padrão) ou 'contains'.")
    p.add_argument("--grid-objective", choices=["st_top1","macro","weighted"], default="weighted",
                   help="Critério para escolher (T1,T2,γ) no grid (padrão: st_top1).")
    p.add_argument("--grid-alpha", type=float, default=0.5, help="α do objetivo 'weighted'.")
    args = p.parse_args(); main(args)