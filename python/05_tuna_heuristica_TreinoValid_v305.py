"""
05_tuna_heuristica_TreinoValid_vGA_checkpoint.py (v4.3.0)
Pedido do usuário:
- **Tudo que decide passo-a-passo** (gradiente no SGD, aceitação de mutação no SGD,
  refinamento memético no GA, e fitness do GA para seleção/reprodução) usa **APENAS TR (treino)**.
- **COMBO(TR, SEC)** (onde SEC ∈ {EARLY, TR, CV}) é calculado **somente em checkpoints**:
  - SGD: a cada `--check-every` iterações
  - GA:  a cada `--ga-check-every` gerações (default=1)
  Esses checkpoints são usados para:
    * atualizar o **best_W**,
    * imprimir logs e
    * fazer **early stop** (paciência em nº de checkpoints sem melhora).
- Pesos sempre projetados para [-1, 1].
- GA: crossovers (uniforme, por-coluna, BLX-α), mutação auto-adaptativa e refinamento memético (aceita se TR não piorar).
"""

import os, sys, argparse, shutil, tempfile, json
from datetime import datetime
import numpy as np
import pandas as pd

# ---------- Infra de threads ----------
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

# ---------- Quit por teclado (Windows) ----------
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

# ---------- Utils ----------
def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl
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

def parse_multilabel(series, core_classes):
    CORE = set(core_classes); DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS: s = s.replace(d,"|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não"): continue
            if lab in CORE: labs.append(lab)
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

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    order = np.argsort(-proba, axis=1)
    topk = order[:,:k]
    accs = []
    for c in range(proba.shape[1]):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], bool)
        sup = int(mask.sum())
        if sup == 0: continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits/sup)
    return float(np.mean(accs)) if accs else 0.0

# ---------- Projeção dura em [-1, 1] ----------
def project_bounds(W, adjustable_mask, W0, maxabs=1.0):
    Wp = W.copy()
    Wp[~adjustable_mask] = W0[~adjustable_mask]
    Wp[adjustable_mask] = np.clip(Wp[adjustable_mask], -maxabs, maxabs)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask, maxabs=1.0):
    G = grad.copy(); G[~adjustable_mask] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    thr = lr*l1
    Delta = np.sign(Delta)*np.maximum(np.abs(Delta)-thr, 0.0)
    W_new = W0 + Delta
    return project_bounds(W_new, adjustable_mask, W0, maxabs=maxabs)

def with_bias(X):
    return np.concatenate([X, np.ones((X.shape[0],1), dtype=float)], axis=1)

def forward(Wmat, Xb):
    return softmax_rows(Xb @ Wmat)

# ========================== MAIN ==========================
def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception: pass

    # --- combo helper para checkpoints ---
    wtr = max(0.0, args.sel_w_tr); wsec = max(0.0, args.sel_w_sec)
    if (wtr + wsec) <= 0:
        wtr = 1.0; wsec = 0.0
    def combo(tr, sec):
        return (wtr*tr + wsec*sec) / (wtr + wsec)

    # --- IO / planilhas ---
    INPUT = args.input
    OUTPUT = args.output or INPUT
    ABA_DADOS = args.sheet_dados
    ABA_PONTOS_TUNADA = args.sheet_pontos_tunada
    ABA_PONTOS = args.sheet_pontos
    ABA_RES_HEUR_TUN = args.sheet_resultado_tun
    ABA_MET_HEUR_TUN = args.sheet_metricas_tun
    ABA_REGRAS_NORMAL = args.sheet_regras_normal
    ABA_COMPARATIVO_TUDO = args.sheet_comparativo
    ABA_DIAG = args.sheet_diag

    COLUNA_TAM = args.n_classes; LINHA_INICIO_PONTOS = args.linha_inicio_pontos; COL_ALVO = args.col_alvo; TOPK = args.topk

    L1 = args.l1; L2 = args.l2; LR = args.lr; MAX_STEPS = args.max_steps; CHECK_EVERY = args.check_every
    RANDOM_STATE = args.seed
    REPORT_JSON = args.report_json; N_JOBS = max(1, args.n_jobs)
    SEL_MODE = args.selection_mode.lower()
    GA_CHECK_EVERY = args.ga_check_every if args.ga_check_every is not None else 1

    # --- Carrega e prepara dados ---
    df_all_full = pd.read_excel(INPUT, sheet_name=ABA_DADOS)
    df_all = df_all_full.copy()
    xl = pd.ExcelFile(INPUT)
    usar_tunada = args.prefer_tunada and (ABA_PONTOS_TUNADA in xl.sheet_names)
    aba_pontos_usada = ABA_PONTOS_TUNADA if usar_tunada else ABA_PONTOS
    df_pont = pd.read_excel(INPUT, sheet_name=aba_pontos_usada)

    cols_dados = df_all.columns[1:]
    if len(cols_dados) == 0: raise ValueError(f"{ABA_DADOS} não possui colunas a partir da coluna B.")
    X_all = df_all[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    X_all_full = df_all_full[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    n_all, m = X_all.shape

    r0 = LINHA_INICIO_PONTOS - 2
    linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM: raise ValueError(f"Aba '{aba_pontos_usada}' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

    faltantes = [c for c in cols_dados if c not in df_pont.columns]
    if faltantes: raise ValueError(f"Colunas de {ABA_DADOS} ausentes em '{aba_pontos_usada}': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

    W_block = df_pont.loc[linhas_modelos, cols_dados]
    W0_sheet = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T  # (features x K)
    K = W0_sheet.shape[1]
    if K != COLUNA_TAM: raise ValueError(f"Dimensão inesperada de W core: {W0_sheet.shape}, esperado K={COLUNA_TAM}.")
    class_core = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist() if "Tipo de Transtorno" in df_pont.columns else [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    # Normalizações de X (0..1)
    X_all = np.clip(np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)
    X_all_full = np.clip(np.nan_to_num(X_all_full, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)

    # Rotulagem (mantém apenas classes do core)
    def normalize_token(s: str) -> str:
        s = (s or "").strip().lower()
        return (s.replace("ã","a").replace("á","a").replace("â","a")
                 .replace("é","e").replace("ê","e")
                 .replace("í","i")
                 .replace("ó","o").replace("ô","o")
                 .replace("ú","u"))
    def parse_multilabel(series, core_classes):
        CORE = set(core_classes); DELIMS = ["|",";",","]
        out = []
        for val in series.astype(str).tolist():
            s = val
            for d in DELIMS: s = s.replace(d,"|")
            labs_raw = [p.strip() for p in s.split("|") if p.strip()]
            labs = []
            for lab in labs_raw:
                tok = normalize_token(lab)
                if tok in ("nao","não"): continue
                if lab in CORE: labs.append(lab)
            out.append(labs)
        return out

    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core)

    keep_nonempty = [len(l)>0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]; df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]

    class_names = class_core
    class_to_idx = {c:i for i,c in enumerate(class_names)}
    idx_to_class = {i:c for i,c in enumerate(class_names)}

    # Elegibilidade
    suportes = {c: sum((c in labs) for labs in y_lists_all) for c in class_names}
    eligible_labels = {c for c,s in suportes.items() if s >= args.min_support_val}
    minor_labels = set(class_names) - eligible_labels

    has_eligible = np.array([any(c in eligible_labels for c in l) for l in y_lists_all], bool)
    has_only_minor= np.array([all(c in minor_labels for c in l) for l in y_lists_all], bool)

    idx_tv_pool = np.where(has_eligible)[0]
    idx_minor_train_for_grid = np.where(has_only_minor)[0]

    # ====== SPLIT 1/3 - 1/3 - 1/3: TRAIN / EARLY / TEST ======
    rng = np.random.default_rng(RANDOM_STATE)
    y_tv = [y_lists_all[i] for i in idx_tv_pool]

    def count_by_label(arr_lists, c):
        return sum(c in labs for labs in arr_lists)

    targets_train = {c: int(np.floor(args.train_frac * count_by_label(y_tv, c))) for c in eligible_labels}
    targets_early = {c: int(np.floor(args.early_frac * count_by_label(y_tv, c))) for c in eligible_labels}
    counts_train  = {c: 0 for c in eligible_labels}
    counts_early  = {c: 0 for c in eligible_labels}

    n_tv = len(y_tv)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)

    assign_train_local = np.zeros(n_tv, bool)
    assign_early_local = np.zeros(n_tv, bool)
    assign_test_local  = np.zeros(n_tv, bool)

    for i in order_idx:
        labs = [c for c in y_tv[i] if c in eligible_labels]
        if not labs:
            assign_train_local[i] = True
            continue
        need_train = any(counts_train[c] < targets_train[c] for c in labs)
        need_early = any(counts_early[c] < targets_early[c] for c in labs)
        if need_train:
            assign_train_local[i] = True
            for c in labs:
                if counts_train[c] < targets_train[c]:
                    counts_train[c] += 1
        elif need_early:
            assign_early_local[i] = True
            for c in labs:
                if counts_early[c] < targets_early[c]:
                    counts_early[c] += 1
        else:
            assign_test_local[i] = True

    idx_train = np.unique(np.concatenate([idx_tv_pool[np.where(assign_train_local)[0]], idx_minor_train_for_grid]))
    idx_early = np.unique(idx_tv_pool[np.where(assign_early_local)[0]])
    idx_test  = np.unique(idx_tv_pool[np.where(assign_test_local)[0]])

    # Matrizes com bias
    def with_bias(X):
        return np.concatenate([X, np.ones((X.shape[0],1), dtype=float)], axis=1)
    X_all = np.asarray(X_all); X_all_full = np.asarray(X_all_full)
    Xb_all   = with_bias(X_all)
    Xb_train = with_bias(X_all[idx_train])
    Xb_early = with_bias(X_all[idx_early])
    Xb_test  = with_bias(X_all[idx_test])
    Xb_all_full = with_bias(X_all_full)

    # Alvos e suavização
    Kc = len(class_names)
    def y_distribution(y_lists, class_to_idx, K):
        n = len(y_lists); Y = np.zeros((n,K), dtype=float)
        for i,labs in enumerate(y_lists):
            pos = [class_to_idx[c] for c in labs if c in class_to_idx]
            if pos:
                w = 1.0/len(pos)
                Y[i,pos] = w
        return Y
    y_train = [y_lists_all[i] for i in idx_train]
    y_early = [y_lists_all[i] for i in idx_early]
    y_test  = [y_lists_all[i] for i in idx_test]
    Y_train = y_distribution(y_train, class_to_idx, Kc)
    eps = args.label_smoothing
    if eps > 0:
        Y_train = (1 - eps) * Y_train + eps * (1.0 / Y_train.shape[1])

    # W inicial e máscara
    mask_w_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)
    W0_eff_core = W0_sheet.copy()
    W0_eff_core[~mask_w_all_zero, :] = np.clip(W0_eff_core[~mask_w_all_zero, :], -1.0, 1.0)

    W0 = np.zeros((m+1, Kc), dtype=float)
    W0[:m, :Kc] = W0_eff_core
    W0[m, :Kc]  = 0.0

    adjustable = np.zeros_like(W0, dtype=bool)
    adjustable[:m, :Kc] = ~mask_w_all_zero[:, None]
    adjustable[m, :Kc]  = True

    # ====== Métricas ======
    def forward(Wmat, Xb):
        return softmax_rows(Xb @ Wmat)

    def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
        order = np.argsort(-proba, axis=1)
        topk = order[:,:k]
        accs = []
        for c in range(proba.shape[1]):
            c_name = idx_to_class[c]
            mask = np.array([c_name in labs for labs in y_lists], bool)
            sup = int(mask.sum())
            if sup == 0: continue
            idxs = np.where(mask)[0]
            hits = sum(c in topk[i] for i in idxs)
            accs.append(hits/sup)
        return float(np.mean(accs)) if accs else 0.0

    def tr_metric(W):
        P_tr = forward(W, Xb_train)
        return macro_topk(y_train, P_tr, class_to_idx, idx_to_class, k=TOPK)

    def sec_metric(W, rng_eval):
        if SEL_MODE == "early":
            if len(y_early) == 0: return tr_metric(W)
            P_ea = forward(W, Xb_early)
            return macro_topk(y_early, P_ea, class_to_idx, idx_to_class, k=TOPK)
        elif SEL_MODE == "cv":
            folds = args.cv_folds
            if Xb_train.shape[0] == 0 or folds <= 1: return 0.0
            # simples CV particionando índices; usamos proba do treino "full" só para acelerar slicing
            P_tr_all = forward(W, Xb_train)
            n = Xb_train.shape[0]
            idx = np.arange(n); rng_eval.shuffle(idx)
            fold_sizes = [(n // folds) + (1 if i < n % folds else 0) for i in range(folds)]
            starts = np.cumsum([0] + fold_sizes[:-1])
            scores = []
            for st, sz in zip(starts, fold_sizes):
                val_idx = idx[st:st+sz]
                if val_idx.size == 0: continue
                y_val = [y_train[j] for j in val_idx]
                P_val = P_tr_all[val_idx]
                sc = macro_topk(y_val, P_val, class_to_idx, idx_to_class, k=TOPK)
                scores.append(sc)
            return float(np.mean(scores)) if scores else 0.0
        else:  # "train"
            return tr_metric(W)

    # ====== Data augmentation (apenas para gradiente em TR) ======
    def make_Xb_for_grad(it_seed):
        Xb_noise = Xb_train.copy()
        if args.input_noise_sigma > 0:
            g = np.random.default_rng(RANDOM_STATE + it_seed).normal(0.0, args.input_noise_sigma, size=Xb_noise[:, :-1].shape)
            Xb_noise[:, :-1] = np.clip(Xb_noise[:, :-1] + g, 0.0, 1.0)
        if args.feature_dropout > 0:
            rng_fd = np.random.default_rng(RANDOM_STATE + 1234 + it_seed)
            mask = (rng_fd.random(Xb_noise[:, :-1].shape[1]) >= args.feature_dropout).astype(float)
            Xb_noise[:, :-1] *= mask  # broadcasting por coluna
        return Xb_noise

    # ====== SGD (TREINO-only nas decisões locais) ======
    def sgd_train():
        W = W0.copy()
        rng_eval = np.random.default_rng(RANDOM_STATE + 2025)

        best_W = W.copy()
        best_combo = -1.0
        checks_without_improve = 0
        diag_rows = []
        total_checks = 0

        for it in range(1, MAX_STEPS+1):
            if _user_requested_quit():
                print("[PARAR] Interrompido pelo usuário."); break

            # gradiente em TR
            Xb_noise = make_Xb_for_grad(it)
            P_tr = forward(W, Xb_noise)
            n_tr = max(Xb_noise.shape[0], 1)
            Gs   = (P_tr - Y_train) / n_tr
            Gw   = Xb_noise.T @ Gs
            W = proximal_step(W, Gw, W0, LR, L1, L2, adjustable, maxabs=1.0)

            # mutação (aceita se TR melhorar)
            if args.mutations and (it % args.mutation_every == 0):
                base_tr = tr_metric(W)
                rng_mut = np.random.default_rng(RANDOM_STATE+7+it)
                improved = False
                for _ in range(args.mutation_max_tries):
                    W_mut = W + rng_mut.normal(0.0, args.mutation_sigma, size=W.shape)
                    W_mut[~adjustable] = W0[~adjustable]
                    W_mut = project_bounds(W_mut, adjustable, W0, 1.0)
                    tr_mut = tr_metric(W_mut)
                    if tr_mut > base_tr + 1e-9:
                        W = W_mut; base_tr = tr_mut; improved = True
                if improved:
                    print(f"[MUT][it={it}] TR melhorou para {base_tr:.3%}")

            # checkpoint para COMBO(TR, SEC)
            if it % CHECK_EVERY == 0 or it == MAX_STEPS or it == 1:
                total_checks += 1
                TR = tr_metric(W)
                SEC = sec_metric(W, rng_eval)
                C = combo(TR, SEC)
                improved = C > best_combo + 1e-6
                if improved:
                    best_combo = C; best_W = W.copy(); checks_without_improve = 0
                else:
                    checks_without_improve += 1

                diag_rows.append({"iter": it, "TR": TR, f"SEC({SEL_MODE})": SEC, "COMBO": C, "improved": improved})
                print(f"[CHK it={it:05d}] TR={TR:.3%}  SEC({SEL_MODE})={SEC:.3%}  COMBO={C:.3%}  best={best_combo:.3%}")

                if checks_without_improve >= args.patience:
                    print("[PARAR] Early stop por COMBO (paciência esgotada).")
                    break

        return best_W, diag_rows, total_checks

    # ====== GA (fitness = TR only; COMBO só em checkpoints) ======
    def crossover_uniform(WA, WB, rng, p=0.5):
        mask = rng.random(WA.shape) < p
        return np.where(mask, WA, WB)

    def crossover_columnwise(WA, WB, rng):
        m1,k1 = WA.shape
        chooseA = rng.random(k1) < 0.5
        child = WB.copy()
        child[:, chooseA] = WA[:, chooseA]
        return child

    def crossover_blx_alpha(WA, WB, rng, alpha=0.2):
        lam = rng.uniform(-alpha, 1.0+alpha, size=WA.shape)
        return lam*WA + (1.0 - lam)*WB

    def mutate_self_adaptive(W, sigma, rng, sigma_min, sigma_max, tau):
        sigma_prime = float(np.clip(sigma * np.exp(tau * rng.normal()), sigma_min, sigma_max))
        noise = rng.normal(0.0, sigma_prime, size=W.shape)
        return W + noise, sigma_prime

    def ga_train():
        rng = np.random.default_rng(RANDOM_STATE+777)
        rng_eval = np.random.default_rng(RANDOM_STATE + 2025)

        P = args.ga_pop
        elite = max(1, int(np.round(args.ga_elite_frac * P)))
        tournament_k = args.ga_tournament_k
        blx_alpha = args.ga_blx_alpha

        cx_probs = np.array([args.ga_cx_prob_uniform, args.ga_cx_prob_column, args.ga_cx_prob_blx], dtype=float)
        if cx_probs.sum() <= 0: cx_probs[:] = 1.0
        cx_probs = cx_probs / cx_probs.sum()

        # população inicial
        pop_W = []
        pop_sigma = []
        base_sigma = args.ga_mut_sigma_init
        pop_W.append(W0.copy()); pop_sigma.append(base_sigma)
        for _ in range(4):
            noise = rng.normal(0.0, base_sigma, size=W0.shape)
            noise[~adjustable] = 0.0
            Wi = project_bounds(W0 + noise, adjustable, W0, 1.0)
            pop_W.append(Wi); pop_sigma.append(base_sigma)
        while len(pop_W) < P:
            Wi = rng.uniform(-1.0, 1.0, size=W0.shape)
            Wi[~adjustable] = W0[~adjustable]
            pop_W.append(Wi); pop_sigma.append(base_sigma)
        pop_W = np.array(pop_W); pop_sigma = np.array(pop_sigma, dtype=float)

        # fitness (para ordenação e seleção) = TR - penalidades
        def penalties(W):
            pen = 0.0
            if args.ga_penalty_l2w0 > 0:
                pen += args.ga_penalty_l2w0 * np.sum((W - W0)**2) / W.size
            return pen

        def eval_tr_fitness(Ws):
            n = Ws.shape[0]
            fits = np.zeros(n); TRs = np.zeros(n)
            for i in range(n):
                TRs[i] = tr_metric(Ws[i])
                fits[i] = TRs[i] - penalties(Ws[i])
            return fits, TRs

        fits, TRs = eval_tr_fitness(pop_W)

        # checkpoint state
        best_W = pop_W[np.argmax(fits)].copy()
        best_combo = -1.0
        checks_without_improve = 0
        diag_rows = []
        total_checks = 0

        # função de checkpoint: avalia COMBO na população inteira e decide best/early stop
        def checkpoint(gen, pop_W, TRs):
            nonlocal best_W, best_combo, checks_without_improve, total_checks
            if gen % GA_CHECK_EVERY != 0 and gen != 1:
                return
            # calcula SEC e COMBO para todos
            SECs = np.zeros(pop_W.shape[0])
            rng_eval_local = np.random.default_rng(RANDOM_STATE + 2025 + gen)
            for i in range(pop_W.shape[0]):
                SECs[i] = sec_metric(pop_W[i], rng_eval_local)
            COMBOs = (wtr*TRs + wsec*SECs) / (wtr + wsec) if (wtr+wsec)>0 else TRs
            i_best = int(np.argmax(COMBOs))
            C_best = float(COMBOs[i_best])
            improved = C_best > best_combo + 1e-6
            if improved:
                best_combo = C_best; best_W = pop_W[i_best].copy(); checks_without_improve = 0
            else:
                checks_without_improve += 1
            total_checks += 1
            diag_rows.append({"gen": gen, "TR_best": float(TRs[i_best]), f"SEC_best({SEL_MODE})": float(SECs[i_best]), "COMBO_best": C_best, "improved": improved})
            print(f"[GA-CHK gen={gen:03d}] COMBO_best={C_best:.3%}  TR_best={TRs[i_best]:.3%}  SEC_best({SEL_MODE})={SECs[i_best]:.3%}  best_COMBO={best_combo:.3%}")
            if checks_without_improve >= args.patience:
                print("[PARAR] GA early stop por COMBO (paciência esgotada).")
                return True
            return False

        # checkpoint inicial
        stop_now = checkpoint(gen=1, pop_W=pop_W, TRs=TRs)
        if stop_now: return best_W, diag_rows, total_checks

        for gen in range(1, args.max_steps+1):
            if _user_requested_quit():
                print("[PARAR] GA interrompido pelo usuário."); break

            # ordena por fitness (TR - penalidades)
            order = np.argsort(-fits)
            pop_W = pop_W[order]; pop_sigma = pop_sigma[order]
            fits = fits[order]; TRs = TRs[order]

            print(f"[GA GEN {gen:03d}] top fitness(TR-pen)={fits[0]:.6f}  TR={TRs[0]:.3%}")

            # elitismo
            new_W = [pop_W[i].copy() for i in range(min(elite, pop_W.shape[0]))]
            new_sigma = [pop_sigma[i] for i in range(min(elite, pop_W.shape[0]))]

            # reprodução
            Pn = pop_W.shape[0]
            while len(new_W) < P:
                # torneio por fitness
                def pick():
                    idxs = rng.integers(0, Pn, size=tournament_k)
                    j = idxs[np.argmax(fits[idxs])]
                    return j
                iA = pick(); iB = pick()
                WA, WB = pop_W[iA], pop_W[iB]
                sigmaA, sigmaB = pop_sigma[iA], pop_sigma[iB]

                cx_type = rng.choice(3, p=cx_probs)
                if cx_type == 0: child = crossover_uniform(WA, WB, rng, p=0.5)
                elif cx_type == 1: child = crossover_columnwise(WA, WB, rng)
                else: child = crossover_blx_alpha(WA, WB, rng, alpha=blx_alpha)

                child = project_bounds(child, adjustable, W0, 1.0)

                # mutação auto-adaptativa
                child_sigma_parent = 0.5*(sigmaA + sigmaB)
                child_mut, child_sigma = mutate_self_adaptive(child, child_sigma_parent, rng,
                                                              sigma_min=args.ga_mut_sigma_min,
                                                              sigma_max=args.ga_mut_sigma_max,
                                                              tau=args.ga_mut_sigma_tau)
                child_mut[~adjustable] = W0[~adjustable]
                child_mut = project_bounds(child_mut, adjustable, W0, 1.0)

                # refinamento memético (aceita se TR não piorar)
                # realizamos N passos de gradiente em TR e ficamos com o melhor por TR entre {child_mut, refinado}
                W_ref = child_mut.copy()
                best_tr_child = tr_metric(W_ref)
                for s in range(args.ga_memetic_steps):
                    Xb_noise = make_Xb_for_grad(100000 + gen*10 + s)
                    P_tr = forward(W_ref, Xb_noise)
                    n_tr = max(Xb_noise.shape[0], 1)
                    Gs   = (P_tr - Y_train) / n_tr
                    Gw   = Xb_noise.T @ Gs
                    W_try = proximal_step(W_ref, Gw, W0, LR, L1, L2, adjustable, maxabs=1.0)
                    tr_try = tr_metric(W_try)
                    if tr_try >= best_tr_child - 1e-9:
                        W_ref = W_try; best_tr_child = tr_try

                new_W.append(W_ref); new_sigma.append(child_sigma)

            pop_W = np.array(new_W); pop_sigma = np.array(new_sigma, dtype=float)
            fits, TRs = eval_tr_fitness(pop_W)

            # checkpoints por geração (COMBO decide best/stop)
            stop_now = checkpoint(gen=gen, pop_W=pop_W, TRs=TRs)
            if stop_now: break

        return best_W, diag_rows, total_checks

    # ----------------- EXECUÇÃO -----------------
    if args.ga:
        best_W, diag_rows, total_checks = ga_train()
    else:
        best_W, diag_rows, total_checks = sgd_train()

    # ---------- Final com best_W selecionado por COMBO ----------
    W_tuned = project_bounds(best_W, adjustable, W0, maxabs=1.0)

    # Probabilidades em ALL / ALL_FULL (para abas)
    def forward(Wmat, Xb): return softmax_rows(Xb @ Wmat)
    P_all = forward(W_tuned, Xb_all)
    P_all_full = forward(W_tuned, Xb_all_full)

    # Métricas finais por split
    def split_metrics(yA, XbA, yB, XbB, yC, XbC, k=1):
        PA = forward(W_tuned, XbA); PB = forward(W_tuned, XbB); PC = forward(W_tuned, XbC)
        mA = macro_topk(yA, PA, class_to_idx, idx_to_class, k=k)
        mB = macro_topk(yB, PB, class_to_idx, idx_to_class, k=k)
        mC = macro_topk(yC, PC, class_to_idx, idx_to_class, k=k)
        return mA, mB, mC

    sec_name = "EARLY" if SEL_MODE=='early' else ("CV(est.)" if SEL_MODE=='cv' else "TR")
    m_tr_k1, m_sec_k1, m_te_k1 = split_metrics(y_train, Xb_train, y_early if SEL_MODE=='early' else y_train, Xb_early if SEL_MODE=='early' else Xb_train, y_test, Xb_test, k=1)
    m_tr_k2, m_sec_k2, m_te_k2 = split_metrics(y_train, Xb_train, y_early if SEL_MODE=='early' else y_train, Xb_early if SEL_MODE=='early' else Xb_train, y_test, Xb_test, k=2)
    m_tr_k3, m_sec_k3, m_te_k3 = split_metrics(y_train, Xb_train, y_early if SEL_MODE=='early' else y_train, Xb_early if SEL_MODE=='early' else Xb_train, y_test, Xb_test, k=3)

    # Abas
    df_pont_tun = pd.DataFrame(W_tuned[:m, :Kc].T, columns=cols_dados)
    df_pont_tun.insert(0, "Tipo de Transtorno", class_core)

    # Resultado_Heuristica_Tunada (filtrado: somente linhas com rótulo core)
    df_res = df_all[[df_all.columns[0]]].copy()
    if args.col_alvo in df_all.columns: df_res[args.col_alvo] = df_all[args.col_alvo]
    for j, name in enumerate(class_names): df_res[f"p_{name}"] = P_all[:, j]
    order_all = np.argsort(-P_all, axis=1)
    tops_rec = []
    for i in range(P_all.shape[0]):
        rec = {}
        for t in range(min(3, P_all.shape[1])):
            c = order_all[i, t]
            rec[f"top{t+1}_classe"] = class_names[c]
            rec[f"top{t+1}_prob"]   = float(P_all[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    # Comparativo_TopK_Tudo (TDados completo)
    df_comp = df_all_full[[df_all_full.columns[0]]].copy()
    if args.col_alvo in df_all_full.columns: df_comp[args.col_alvo] = df_all_full[args.col_alvo]
    for j, name in enumerate(class_names): df_comp[f"p_{name}"] = P_all_full[:, j]
    order_full = np.argsort(-P_all_full, axis=1)
    tops_full = []
    for i in range(P_all_full.shape[0]):
        rec = {}
        for t in range(min(3, P_all.shape[1])):
            c = order_full[i, t]
            rec[f"top{t+1}_classe"] = class_names[c]
            rec[f"top{t+1}_prob"]   = float(P_all_full[i, c])
        tops_full.append(rec)
    df_comp = pd.concat([df_comp, pd.DataFrame(tops_full)], axis=1)

    # Diagnóstico/registros
    modo = "GA" if args.ga else "SGD"
    df_regras = pd.DataFrame([
        {"param":"mode", "value":modo},
        {"param":"selection_mode", "value":SEL_MODE},
        {"param":"sel_w_tr", "value":float(wtr)},
        {"param":"sel_w_sec", "value":float(wsec)},
        {"param":"check_every (SGD)", "value":int(CHECK_EVERY)},
        {"param":"ga_check_every (GA)", "value":int(GA_CHECK_EVERY)},
        {"param":"patience (em checkpoints)", "value":int(args.patience)},
        {"param":"l1", "value":float(L1)},
        {"param":"l2", "value":float(L2)},
        {"param":"lr", "value":float(LR)},
        {"param":"label_smoothing", "value":float(args.label_smoothing)},
        {"param":"input_noise_sigma", "value":float(args.input_noise_sigma)},
        {"param":"feature_dropout", "value":float(args.feature_dropout)},
        {"param":"ga_pop", "value":int(args.ga_pop)},
        {"param":"ga_elite_frac", "value":float(args.ga_elite_frac)},
        {"param":"ga_tournament_k", "value":int(args.ga_tournament_k)},
        {"param":"ga_cx_probs (uni,col,blx)", "value":f"({args.ga_cx_prob_uniform},{args.ga_cx_prob_column},{args.ga_cx_prob_blx})"},
        {"param":"ga_blx_alpha", "value":float(args.ga_blx_alpha)},
        {"param":"ga_mut_sigma_init", "value":float(args.ga_mut_sigma_init)},
        {"param":"ga_mut_sigma_min", "value":float(args.ga_mut_sigma_min)},
        {"param":"ga_mut_sigma_max", "value":float(args.ga_mut_sigma_max)},
        {"param":"ga_mut_sigma_tau", "value":float(args.ga_mut_sigma_tau)},
        {"param":"ga_memetic_steps", "value":int(args.ga_memetic_steps)},
    ])

    saved_path = save_preserving_sheets(OUTPUT,
        [(df_pont_tun, ABA_PONTOS_TUNADA),
         (df_res, ABA_RES_HEUR_TUN),
         (pd.DataFrame([{
             f"macro_top1(TR/{sec_name}/TEST)": f"({m_tr_k1:.3%}/{m_sec_k1:.3%}/{m_te_k1:.3%})",
             f"macro_top2(TR/{sec_name}/TEST)": f"({m_tr_k2:.3%}/{m_sec_k2:.3%}/{m_te_k2:.3%})",
             f"macro_top3(TR/{sec_name}/TEST)": f"({m_tr_k3:.3%}/{m_sec_k3:.3%}/{m_te_k3:.3%})",
         }]), ABA_MET_HEUR_TUN),
         (df_regras, ABA_REGRAS_NORMAL),
         (pd.DataFrame(diag_rows), ABA_DIAG),
         (df_comp, ABA_COMPARATIVO_TUDO)])

    report = {
        "status":"ok",
        "mode": modo,
        "selection_mode": SEL_MODE,
        "sel_w_tr": float(wtr),
        "sel_w_sec": float(wsec),
        "macro_train_top1": float(m_tr_k1),
        "macro_sec_top1": float(m_sec_k1),
        "macro_test_top1":  float(m_te_k1),
        "macro_train_top2": float(m_tr_k2),
        "macro_sec_top2": float(m_sec_k2),
        "macro_test_top2":  float(m_te_k2),
        "macro_train_top3": float(m_tr_k3),
        "macro_sec_top3": float(m_sec_k3),
        "macro_test_top3":  float(m_te_k3),
        "seed": int(RANDOM_STATE),
        "lr": float(LR), "l1": float(L1), "l2": float(L2),
        "checks": int(total_checks),
        "used_sheet": aba_pontos_usada, "output_file": saved_path,
        "postrule": "none_softmax_core_only", "n_jobs": int(N_JOBS),
        "label_smoothing": float(args.label_smoothing),
        "input_noise_sigma": float(args.input_noise_sigma),
        "feature_dropout": float(args.feature_dropout),
    }
    try:
        base = os.path.splitext(OUTPUT or INPUT)[0]
        rep_path = args.report_json or base + "_report.json"
        with open(rep_path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas atualizadas:", ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_DIAG, ABA_COMPARATIVO_TUDO)
    print(f"➡️ FINAL top1 TR/{sec_name}/TEST = ({m_tr_k1:.3%}/{m_sec_k1:.3%}/{m_te_k1:.3%}) | "
          f"top2 = ({m_tr_k2:.3%}/{m_sec_k2:.3%}/{m_te_k2:.3%}) | top3 = ({m_tr_k3:.3%}/{m_sec_k3:.3%}/{m_te_k3:.3%})")
    print(f"💾 Arquivo salvo em: {saved_path}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="SGD/GA: passos locais via TR; best/stop via COMBO(TR, SEC) em checkpoints.")
    p.add_argument("--input", default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx")
    p.add_argument("--output", default=None)
    p.add_argument("--sheet-dados", default="TDados_clean")
    p.add_argument("--sheet-pontos", default="Pontuação")
    p.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    p.add_argument("--sheet-resultado-tun", default="Resultado_Heuristica_Tunada")
    p.add_argument("--sheet-metricas-tun", default="Metricas_Heuristica_Tunada")
    p.add_argument("--sheet-regras-normal", default="Regras_Normal")
    p.add_argument("--sheet-comparativo", default="Comparativo_TopK_Tudo")
    p.add_argument("--sheet-diag", dest="sheet_diag", default="Diagnostico_SUM")
    p.add_argument("--prefer-tunada", action="store_true", default=True)
    p.add_argument("--n-classes", type=int, default=11)
    p.add_argument("--linha-inicio-pontos", type=int, default=3)
    p.add_argument("--col-alvo", default="Alvo")

    # Split base (ainda geramos EARLY/TEST para relatório; mas decisões locais usam só TR)
    p.add_argument("--train-frac", type=float, default=1.0/3.0)
    p.add_argument("--early-frac", type=float, default=1.0/3.0)
    p.add_argument("--min-support-val", type=int, default=2)

    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)

    # Regularização e passo
    p.add_argument("--l1", type=float, default=0.01)
    p.add_argument("--l2", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=0.005)

    # Passos e checkpoints
    p.add_argument("--max-steps", type=int, default=15000)
    p.add_argument("--check-every", type=int, default=50, help="SGD: checkpoints/prints de COMBO a cada N iterações")
    p.add_argument("--ga-check-every", type=int, default=1, help="GA: checkpoints de COMBO a cada N gerações")
    p.add_argument("--patience", type=int, default=1200, help="nº de checkpoints sem melhora no COMBO para parar")

    # Anti-overfit (gradiente/memético, apenas TR)
    p.add_argument("--label-smoothing", type=float, default=0.05)
    p.add_argument("--input-noise-sigma", type=float, default=0.02)
    p.add_argument("--feature-dropout", type=float, default=0.05)

    # Mutations no modo SGD (aceitas se TR melhora)
    p.add_argument("--mutations", action="store_true", default=True)
    p.add_argument("--mutation-every", type=int, default=1)
    p.add_argument("--mutation-sigma", type=float, default=0.5)
    p.add_argument("--mutation-max-tries", type=int, default=1200)

    # ----------------- GA args -----------------
    p.add_argument("--ga", action="store_true", default=True)
    p.add_argument("--ga-pop", type=int, default=128)
    p.add_argument("--ga-elite-frac", type=float, default=0.1)
    p.add_argument("--ga-tournament-k", type=int, default=40)
    p.add_argument("--ga-cx-prob-uniform", type=float, default=0.4)
    p.add_argument("--ga-cx-prob-column", type=float, default=0.4)
    p.add_argument("--ga-cx-prob-blx", type=float, default=0.5)
    p.add_argument("--ga-blx-alpha", type=float, default=0.2)
    p.add_argument("--ga-mut-sigma-init", type=float, default=0.08)
    p.add_argument("--ga-mut-sigma-min", type=float, default=0.005)
    p.add_argument("--ga-mut-sigma-max", type=float, default=0.2)
    p.add_argument("--ga-mut-sigma-tau", type=float, default=0.15)
    p.add_argument("--ga-memetic-steps", type=int, default=20)
    p.add_argument("--ga-penalty-l2w0", type=float, default=0.05)

    # Seleção (COMBO apenas nos checkpoints)
    p.add_argument("--selection-mode", choices=["early","train","cv"], default="early",
                   help="Métrica secundária SEC: EARLY | TR | CV(K-fold em TREINO)")
    p.add_argument("--sel-w-tr", type=float, default=0.3, help="peso de TR no COMBO")
    p.add_argument("--sel-w-sec", type=float, default=0.7, help="peso de SEC no COMBO")
    p.add_argument("--cv-folds", type=int, default=5, help="nº de folds no modo selection-mode=cv")

    p.add_argument("--report-json", default="report.json")
    p.add_argument("--n-jobs", type=int, default=os.cpu_count())
    p.add_argument("--blas-threads", type=int, default=1)

    args = p.parse_args(); np.random.seed(args.seed); main(args)