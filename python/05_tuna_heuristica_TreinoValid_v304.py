# -*- coding: utf-8 -*-
"""
05_tuna_heuristica_TreinoValid_vGA_wmix.py (v4.1.0)
- Split 1/3-1/3-1/3: TRAIN / EARLY (validação parcial) / TEST (hold-out final)
- best_W e early-stop guiados por COMBO = w_tr*TR + w_early*EARLY (ponderado)  <<< NOVO
- Mutações (SGD) e refinamento memético (GA) aceitos se COMBO não piorar (ou melhorar)  <<< NOVO
- No GA: fitness passa a ser COMBO - penalidades (antes era EARLY - penalidades)  <<< NOVO
- Pesos W sempre projetados em [-1, 1] (inclui bias)
- Anti-overfitting: label smoothing, ruído em X e feature-dropout no passo de gradiente do TREINO/memético
- GA com 3 crossovers (uniforme, por-coluna, BLX-α) e mutação auto-adaptativa (σ por indivíduo)
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

def macro_topk_pair(y_A, Xb_A, y_B, Xb_B, Wmat, class_to_idx, idx_to_class, k):
    P_A = forward(Wmat, Xb_A)
    P_B = forward(Wmat, Xb_B)
    m_A = macro_topk(y_A, P_A, class_to_idx, idx_to_class, k=k)
    m_B = macro_topk(y_B, P_B, class_to_idx, idx_to_class, k=k)
    return m_A, m_B

def fmt_pair(label, a, b):
    return f"{label}(A/B)=({a:.3%}/{b:.3%})"

# ========================== MAIN ==========================
def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception: pass

    # helper local para COMBO
    wtr = max(0.0, args.sel_w_tr); wea = max(0.0, args.sel_w_early)
    if (wtr + wea) <= 0:
        wea = 1.0  # defaulta para olhar EARLY se pesos inválidos
    def combo(tr, ea):
        return (wtr*tr + wea*ea) / (wtr + wea)

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

    L1 = args.l1; L2 = args.l2; LR = args.lr; MAX_ITERS = args.max_iters; CHECK_EVERY = args.check_every
    RANDOM_STATE = args.seed
    REPORT_JSON = args.report_json; N_JOBS = max(1, args.n_jobs)

    rng_global = np.random.default_rng(RANDOM_STATE)

    # ----- Carrega planilhas base -----
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
    n_all_full = X_all_full.shape[0]

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
    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core)

    # Filtra apenas linhas com algum rótulo do core
    keep_nonempty = [len(l)>0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]; df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]
    n_all = X_all.shape[0]

    class_names = class_core
    class_to_idx = {c:i for i,c in enumerate(class_names)}
    idx_to_class = {i:c for i,c in enumerate(class_names)}

    # Elegibilidade por suporte mínimo
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

    # Alvos e matrizes
    y_train = [y_lists_all[i] for i in idx_train]
    y_early = [y_lists_all[i] for i in idx_early]
    y_test  = [y_lists_all[i] for i in idx_test]
    Kc = len(class_names)
    Y_train = y_distribution(y_train, class_to_idx, Kc)

    # ---------- Label smoothing ----------
    eps = args.label_smoothing
    if eps > 0:
        Y_train = (1 - eps) * Y_train + eps * (1.0 / Y_train.shape[1])

    # ---------- REGRA DE OURO ----------
    W0_sheet = W0_sheet if 'W0_sheet' in locals() else None  # just to avoid linter; it's defined earlier
    mask_w_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)
    W0_eff_core = W0_sheet.copy()
    W0_eff_core[~mask_w_all_zero, :] = np.clip(W0_eff_core[~mask_w_all_zero, :], -1.0, 1.0)

    # Pesos iniciais + bias
    W0 = np.zeros((m+1, Kc), dtype=float)
    W0[:m, :Kc] = W0_eff_core
    W0[m, :Kc]  = 0.0  # bias inicial

    adjustable = np.zeros_like(W0, dtype=bool)
    adjustable[:m, :Kc] = ~mask_w_all_zero[:, None]
    adjustable[m, :Kc]  = True  # ajustar bias sempre

    # Matrizes com bias
    Xb_all   = with_bias(X_all)
    Xb_train = with_bias(X_all[idx_train])
    Xb_early = with_bias(X_all[idx_early])
    Xb_test  = with_bias(X_all[idx_test])
    Xb_all_full = with_bias(X_all_full)

    # --------- Perda (treino) ---------
    def loss_with_regularizers(Wmat, Xb_for_grad, Y_target):
        P = forward(Wmat, Xb_for_grad)
        eps_n = 1e-12
        ce = -np.mean(np.sum(Y_target * np.log(P + eps_n), axis=1))
        l2 = L2 * np.sum((Wmat - W0)**2)
        l1 = L1 * np.sum(np.abs(Wmat - W0))
        return ce + l2 + 0.0*l1, ce, l2

    # --------- Avaliação para seleção (TREINO vs EARLY) ---------
    def objective_early(Wmat):
        m_tr, m_ea = macro_topk_pair(y_train, Xb_train, y_early, Xb_early, Wmat, class_to_idx, idx_to_class, k=TOPK)
        return m_tr, m_ea

    # --------- Data augmentation no TREINO (para gradiente) ---------
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

    # --------- SGD/Proximal loop (se GA desligado) ---------
    def sgd_train():
        W = W0.copy()
        tr0, ea0 = objective_early(W)
        best_combo = combo(tr0, ea0)
        print("[BASE] " + fmt_pair(f"macro_top{TOPK}", tr0, ea0) + f" | combo={best_combo:.3%}")
        print(f"[INFO] tamanhos (TR/EARLY/TEST)=({Xb_train.shape[0]}/{Xb_early.shape[0]}/{Xb_test.shape[0]})")

        best_score_ea = ea0; best_score_tr = tr0; best_W = W.copy()
        diag_rows = []; total_checks = 0
        rng_mut = np.random.default_rng(RANDOM_STATE+7)

        for it in range(1, MAX_ITERS+1):
            if _user_requested_quit():
                print("[PARAR] Interrompido pelo usuário (tecla 'q')."); break

            Xb_noise = make_Xb_for_grad(it)
            P_tr = forward(W, Xb_noise)
            n_tr = max(Xb_noise.shape[0], 1)
            Gs   = (P_tr - Y_train) / n_tr
            Gw   = Xb_noise.T @ Gs  # (m+1, Kc)

            W = proximal_step(W, Gw, W0, LR, L1, L2, adjustable, maxabs=1.0)

            # Mutações (avaliadas por COMBO)
            if args.mutations and (it % args.mutation_every == 0):
                improved_local = False
                base_tr, base_ea = objective_early(W)
                base_combo = combo(base_tr, base_ea)
                for _try in range(args.mutation_max_tries):
                    W_mut = W.copy()
                    noise = rng_mut.normal(loc=0.0, scale=args.mutation_sigma, size=W_mut.shape)
                    noise[~adjustable] = 0.0
                    W_mut += noise
                    W_mut = project_bounds(W_mut, adjustable, W0, maxabs=1.0)
                    tr_mut, ea_mut = objective_early(W_mut)
                    combo_mut = combo(tr_mut, ea_mut)
                    if combo_mut > base_combo + 1e-9:  # aceita se COMBO melhorar
                        W = W_mut
                        base_tr, base_ea, base_combo = tr_mut, ea_mut, combo_mut
                        improved_local = True
                if improved_local:
                    print(f"[MUT] melhoria aceita no it={it}: COMBO {base_combo:.3%} (TR={base_tr:.3%}, EARLY={base_ea:.3%})")

            if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
                total_checks += 1
                cur_tr, cur_ea = objective_early(W)
                cur_combo = combo(cur_tr, cur_ea)
                improved = False
                if cur_combo > best_combo + 1e-6:
                    best_combo = cur_combo
                    best_score_ea = cur_ea
                    best_score_tr = cur_tr
                    best_W = W.copy()
                    improved = True

                diag_rows.append({
                    "iter": it,
                    f"macro_top{TOPK}_TR": cur_tr,
                    f"macro_top{TOPK}_EARLY": cur_ea,
                    "combo": cur_combo,
                    "improved": improved
                })

                print(f"[IT {it:05d}] " + fmt_pair(f"macro_top{TOPK}", cur_tr, cur_ea) +
                      f"  combo={cur_combo:.3%}  best(TR/EARLY/COMBO)=({best_score_tr:.3%}/{best_score_ea:.3%}/{best_combo:.3%})")

                # Early stop: sem melhora em COMBO
                if not improved and len(diag_rows) > args.early_stop_patience:
                    recent_combo = [r["combo"] for r in diag_rows[-args.early_stop_patience:]]
                    if max(recent_combo) <= best_combo + 1e-6:
                        print("[PARAR] Early stop (sem melhora no COMBO)."); break
        return best_W, best_score_tr, best_score_ea, best_combo, diag_rows, total_checks

    # --------------- GA (Genetic Algorithm) ---------------
    # Crossover operators
    def crossover_uniform(WA, WB, rng, p=0.5):
        mask = rng.random(WA.shape) < p
        child = np.where(mask, WA, WB)
        return child

    def crossover_columnwise(WA, WB, rng):
        m1,k1 = WA.shape
        chooseA = rng.random(k1) < 0.5
        child = WB.copy()
        child[:, chooseA] = WA[:, chooseA]
        return child

    def crossover_blx_alpha(WA, WB, rng, alpha=0.2):
        lam = rng.uniform(-alpha, 1.0+alpha, size=WA.shape)
        child = lam*WA + (1.0 - lam)*WB
        return child

    # Mutação auto-adaptativa (σ escalar por indivíduo)
    def mutate_self_adaptive(W, sigma, rng, sigma_min, sigma_max, tau):
        sigma_prime = float(np.clip(sigma * np.exp(tau * rng.normal()), sigma_min, sigma_max))
        noise = rng.normal(0.0, sigma_prime, size=W.shape)
        return W + noise, sigma_prime

    # Fitness do GA (maximizar): COMBO(TR,EARLY) - penalidades
    def fitness_of(W):
        tr, ea = objective_early(W)
        fit = combo(tr, ea)
        if args.ga_penalty_l2w0 > 0:
            fit -= args.ga_penalty_l2w0 * np.sum((W - W0)**2) / W.size
        if args.ga_penalty_gap > 0:
            gap = max(0.0, tr - ea)
            fit -= args.ga_penalty_gap * gap
        return fit, tr, ea

    def local_refine_memetic(W_init, steps, rng):
        Wc = W_init.copy()
        best_tr, best_ea = objective_early(Wc)
        best_combo = combo(best_tr, best_ea)
        for s in range(steps):
            # poucos passos de gradiente com data augmentation
            Xb_noise = make_Xb_for_grad(10000 + s + int(rng.integers(0, 1_000_000)))
            P_tr = forward(Wc, Xb_noise)
            n_tr = max(Xb_noise.shape[0], 1)
            Gs   = (P_tr - Y_train) / n_tr
            Gw   = Xb_noise.T @ Gs
            Wc_new = proximal_step(Wc, Gw, W0, LR, L1, L2, adjustable, maxabs=1.0)
            tr_new, ea_new = objective_early(Wc_new)
            combo_new = combo(tr_new, ea_new)
            # aceita somente se COMBO não piorar
            if combo_new >= best_combo - 1e-9:
                Wc, best_tr, best_ea, best_combo = Wc_new, tr_new, ea_new, combo_new
        return Wc, best_tr, best_ea, best_combo

    def ga_train():
        rng = np.random.default_rng(RANDOM_STATE+777)

        # população: lista de (W, sigma, fit, tr, ea)
        P = args.ga_pop
        elite = max(1, int(np.round(args.ga_elite_frac * P)))
        tournament_k = args.ga_tournament_k
        blx_alpha = args.ga_blx_alpha

        # prob de cada crossover
        cx_probs = np.array([args.ga_cx_prob_uniform, args.ga_cx_prob_column, args.ga_cx_prob_blx], dtype=float)
        if cx_probs.sum() <= 0: cx_probs[:] = 1.0
        cx_probs = cx_probs / cx_probs.sum()

        # inicializa população
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
            pop_W.append(Wi)
            pop_sigma.append(base_sigma)
        pop_W = np.array(pop_W)   # (P, m+1, K)
        pop_sigma = np.array(pop_sigma, dtype=float)

        # avalia população
        def eval_population(Ws):
            fits = np.zeros(Ws.shape[0], dtype=float)
            trs  = np.zeros(Ws.shape[0], dtype=float)
            eas  = np.zeros(Ws.shape[0], dtype=float)
            for i in range(Ws.shape[0]):
                f, tr, ea = fitness_of(Ws[i])
                fits[i], trs[i], eas[i] = f, tr, ea
            return fits, trs, eas

        fits, trs, eas = eval_population(pop_W)

        best_idx = int(np.argmax(fits))
        best_W = pop_W[best_idx].copy()
        best_fit, best_tr, best_ea = fits[best_idx], trs[best_idx], eas[best_idx]
        best_combo = combo(best_tr, best_ea)

        print("[GA] base EARLY =", f"{best_ea:.3%}", "| base TR =", f"{best_tr:.3%}", "| base COMBO =", f"{best_combo:.3%}")
        print(f"[INFO] tamanhos (TR/EARLY/TEST)=({Xb_train.shape[0]}/{Xb_early.shape[0]}/{Xb_test.shape[0]})")

        no_improve_gens = 0
        diag_rows = []
        total_checks = 0

        for gen in range(1, args.ga_gens+1):
            if _user_requested_quit():
                print("[PARAR] GA interrompido pelo usuário."); break

            # ordena por fitness (desc)
            order = np.argsort(-fits)
            pop_W = pop_W[order]
            pop_sigma = pop_sigma[order]
            fits = fits[order]; trs = trs[order]; eas = eas[order]

            cur_combo = combo(trs[0], eas[0])
            print(f"[GA GEN {gen:03d}] best TR={trs[0]:.3%}  EARLY={eas[0]:.3%}  COMBO={cur_combo:.3%}  fitness={fits[0]:.6f}")

            # early stop populacional (por COMBO)
            improved = False
            if cur_combo > best_combo + 1e-6:
                best_combo = cur_combo; best_tr = trs[0]; best_ea = eas[0]; best_fit = fits[0]; best_W = pop_W[0].copy()
                improved = True; no_improve_gens = 0
            else:
                no_improve_gens += 1

            total_checks += 1
            diag_rows.append({"gen": gen, "best_TR": float(trs[0]), "best_EARLY": float(eas[0]), "best_combo": float(cur_combo), "improved": improved})

            if no_improve_gens >= args.ga_early_stop_gens:
                print("[PARAR] GA early stop: sem melhora no COMBO por", args.ga_early_stop_gens, "gerações."); break

            # --- Nova geração ---
            new_W = []
            new_sigma = []

            # elitismo
            for i in range(elite):
                new_W.append(pop_W[i].copy()); new_sigma.append(pop_sigma[i])

            # gerar filhos até completar população
            Pn = pop_W.shape[0]
            while len(new_W) < P:
                # seleção por torneio
                def tournament_pick():
                    idxs = rng.integers(0, Pn, size=tournament_k)
                    best_i = idxs[0]; best_f = fits[idxs[0]]
                    for j in idxs[1:]:
                        if fits[j] > best_f:
                            best_i, best_f = j, fits[j]
                    return best_i
                iA = tournament_pick(); iB = tournament_pick()
                WA, WB = pop_W[iA], pop_W[iB]
                sigmaA, sigmaB = pop_sigma[iA], pop_sigma[iB]

                # sorteia crossover
                cx_probs = np.array([args.ga_cx_prob_uniform, args.ga_cx_prob_column, args.ga_cx_prob_blx], dtype=float)
                if cx_probs.sum() <= 0: cx_probs[:] = 1.0
                cx_probs = cx_probs / cx_probs.sum()
                cx_type = rng.choice(3, p=cx_probs)
                if cx_type == 0:
                    child = crossover_uniform(WA, WB, rng, p=0.5)
                elif cx_type == 1:
                    child = crossover_columnwise(WA, WB, rng)
                else:
                    child = crossover_blx_alpha(WA, WB, rng, alpha=args.ga_blx_alpha)

                # projeção e respeito à máscara
                child = project_bounds(child, adjustable, W0, 1.0)

                # mutação auto-adaptativa
                child_sigma_parent = 0.5*(sigmaA + sigmaB)
                child_mut, child_sigma = mutate_self_adaptive(child, child_sigma_parent, rng,
                                                              sigma_min=args.ga_mut_sigma_min,
                                                              sigma_max=args.ga_mut_sigma_max,
                                                              tau=args.ga_mut_sigma_tau)
                child_mut[~adjustable] = W0[~adjustable]
                child_mut = project_bounds(child_mut, adjustable, W0, 1.0)

                # refinamento local (memético): poucos passos de gradiente; aceita se COMBO não piorar
                W_ref, tr_ref, ea_ref, combo_ref = local_refine_memetic(child_mut, args.ga_memetic_steps, rng)

                new_W.append(W_ref)
                new_sigma.append(child_sigma)

            # substitui população
            pop_W = np.array(new_W); pop_sigma = np.array(new_sigma, dtype=float)
            fits, trs, eas = eval_population(pop_W)

        # fim GA
        return best_W, best_tr, best_ea, best_combo, diag_rows, total_checks

    # ----------------- EXECUÇÃO: GA ou SGD -----------------
    if args.ga:
        best_W, best_score_tr, best_score_ea, best_combo, diag_rows, total_checks = ga_train()
    else:
        best_W, best_score_tr, best_score_ea, best_combo, diag_rows, total_checks = sgd_train()

    # ---------- Final com best_W selecionado por COMBO ----------
    W_tuned = project_bounds(best_W, adjustable, W0, maxabs=1.0)

    # Probabilidades em ALL / ALL_FULL (para abas)
    P_all = forward(W_tuned, Xb_all)
    P_all_full = forward(W_tuned, Xb_all_full)

    # Métricas finais por split
    def split_metrics(yA, XbA, yB, XbB, yC, XbC, k=1):
        PA = forward(W_tuned, XbA); PB = forward(W_tuned, XbB); PC = forward(W_tuned, XbC)
        mA = macro_topk(yA, PA, class_to_idx, idx_to_class, k=k)
        mB = macro_topk(yB, PB, class_to_idx, idx_to_class, k=k)
        mC = macro_topk(yC, PC, class_to_idx, idx_to_class, k=k)
        return mA, mB, mC

    m_tr_k1, m_ea_k1, m_te_k1 = split_metrics(y_train, Xb_train, y_early, Xb_early, y_test, Xb_test, k=1)
    m_tr_k2, m_ea_k2, m_te_k2 = split_metrics(y_train, Xb_train, y_early, Xb_early, y_test, Xb_test, k=2)
    m_tr_k3, m_ea_k3, m_te_k3 = split_metrics(y_train, Xb_train, y_early, Xb_early, y_test, Xb_test, k=3)

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

    # Métricas por classe (EARLY/TEST) + agregados
    P_tr_final    = forward(W_tuned, Xb_train)
    P_early_final = forward(W_tuned, Xb_early)
    P_test_final  = forward(W_tuned, Xb_test)

    rows = []
    for c_idx, c_name in enumerate(class_names):
        mask_tr = np.array([c_name in labs for labs in y_train], bool)
        sup_tr = int(mask_tr.sum()); rate_tr = np.nan; hits_tr = 0
        if sup_tr > 0:
            ord_tr = np.argsort(-P_tr_final[mask_tr], axis=1)[:, :TOPK]
            hits_tr = sum(c_idx in ord_tr[r] for r in range(ord_tr.shape[0]))
            rate_tr = hits_tr / sup_tr

        mask_ea = np.array([c_name in labs for labs in y_early], bool)
        sup_ea = int(mask_ea.sum()); rate_ea = np.nan; hits_ea = 0
        if sup_ea > 0:
            ord_ea = np.argsort(-P_early_final[mask_ea], axis=1)[:, :TOPK]
            hits_ea = sum(c_idx in ord_ea[r] for r in range(ord_ea.shape[0]))
            rate_ea = hits_ea / sup_ea

        mask_te = np.array([c_name in labs for labs in y_test], bool)
        sup_te = int(mask_te.sum()); rate_te = np.nan; hits_te = 0
        if sup_te > 0:
            ord_te = np.argsort(-P_test_final[mask_te], axis=1)[:, :TOPK]
            hits_te = sum(c_idx in ord_te[r] for r in range(ord_te.shape[0]))
            rate_te = hits_te / sup_te

        rows.append({
            "classe": c_name,
            f"top{TOPK}_rate(TR/EARLY/TEST)": f"({rate_tr if not np.isnan(rate_tr) else 'nan'}/"
                                              f"{rate_ea if not np.isnan(rate_ea) else 'nan'}/"
                                              f"{rate_te if not np.isnan(rate_te) else 'nan'})",
            f"acertos_topk(TR/EARLY/TEST)": f"({hits_tr}/{hits_ea}/{hits_te})",
            f"suporte(TR/EARLY/TEST)": f"({sup_tr}/{sup_ea}/{sup_te})"
        })
    df_met_cls = pd.DataFrame(rows)

    df_met_sum = pd.DataFrame([{
        f"macro_top1(TR/EARLY/TEST)": f"({m_tr_k1:.3%}/{m_ea_k1:.3%}/{m_te_k1:.3%})",
        f"macro_top2(TR/EARLY/TEST)": f"({m_tr_k2:.3%}/{m_ea_k2:.3%}/{m_te_k2:.3%})",
        f"macro_top3(TR/EARLY/TEST)": f"({m_tr_k3:.3%}/{m_ea_k3:.3%}/{m_te_k3:.3%})",
        "observacao": ("best_W selecionado por COMBO (w_tr, w_early); TEST é hold-out final; "
                       "SGD puro ou GA (uniforme/coluna/BLX-α, mutação auto-adaptativa, "
                       "refinamento memético aceito se COMBO não piorar).")
    }])

    df_metricas_tun = pd.concat([
        pd.DataFrame([{"secao":"agregado", **df_met_sum.iloc[0].to_dict()}]),
        df_met_cls.assign(secao="por_classe")
    ], ignore_index=True)

    # Regras/diagnóstico
    modo = "GA" if args.ga else "SGD"
    df_regras = pd.DataFrame([
        {"param": "mode", "value": modo},
        {"param": "sel_w_tr", "value": float(wtr)},
        {"param": "sel_w_early", "value": float(wea)},
        {"param": "l1", "value": float(L1)},
        {"param": "l2", "value": float(L2)},
        {"param": "lr", "value": float(LR)},
        {"param": "label_smoothing", "value": float(args.label_smoothing)},
        {"param": "input_noise_sigma", "value": float(args.input_noise_sigma)},
        {"param": "feature_dropout", "value": float(args.feature_dropout)},
        {"param": "ga_pop", "value": int(args.ga_pop)},
        {"param": "ga_gens", "value": int(args.ga_gens)},
        {"param": "ga_elite_frac", "value": float(args.ga_elite_frac)},
        {"param": "ga_tournament_k", "value": int(args.ga_tournament_k)},
        {"param": "ga_cx_probs (uni,col,blx)", "value": f"({args.ga_cx_prob_uniform},{args.ga_cx_prob_column},{args.ga_cx_prob_blx})"},
        {"param": "ga_blx_alpha", "value": float(args.ga_blx_alpha)},
        {"param": "ga_mut_sigma_init", "value": float(args.ga_mut_sigma_init)},
        {"param": "ga_mut_sigma_min", "value": float(args.ga_mut_sigma_min)},
        {"param": "ga_mut_sigma_max", "value": float(args.ga_mut_sigma_max)},
        {"param": "ga_mut_sigma_tau", "value": float(args.ga_mut_sigma_tau)},
        {"param": "ga_memetic_steps", "value": int(args.ga_memetic_steps)},
        {"param": "ga_early_stop_gens", "value": int(args.ga_early_stop_gens)},
        {"param": "ga_penalty_l2w0", "value": float(args.ga_penalty_l2w0)},
        {"param": "ga_penalty_gap", "value": float(args.ga_penalty_gap)},
    ])

    saved_path = save_preserving_sheets(OUTPUT,
        [(df_pont_tun, ABA_PONTOS_TUNADA),
         (df_res, ABA_RES_HEUR_TUN),
         (df_metricas_tun, ABA_MET_HEUR_TUN),
         (df_regras, ABA_REGRAS_NORMAL),
         (pd.DataFrame(diag_rows), ABA_DIAG),
         (df_comp, ABA_COMPARATIVO_TUDO)])

    report = {
        "status":"ok",
        "mode": modo,
        "sel_w_tr": float(wtr),
        "sel_w_early": float(wea),
        "macro_train_top1": float(m_tr_k1),
        "macro_early_top1": float(m_ea_k1),
        "macro_test_top1":  float(m_te_k1),
        "macro_train_top2": float(m_tr_k2),
        "macro_early_top2": float(m_ea_k2),
        "macro_test_top2":  float(m_te_k2),
        "macro_train_top3": float(m_tr_k3),
        "macro_early_top3": float(m_ea_k3),
        "macro_test_top3":  float(m_te_k3),
        "seed": int(RANDOM_STATE),
        "lr": float(LR), "l1": float(L1), "l2": float(L2),
        "checks_or_gens": int(total_checks),
        "used_sheet": aba_pontos_usada, "output_file": saved_path,
        "postrule": "none_softmax_core_only", "n_jobs": int(N_JOBS),
        "label_smoothing": float(args.label_smoothing),
        "input_noise_sigma": float(args.input_noise_sigma),
        "feature_dropout": float(args.feature_dropout),
    }
    if args.ga:
        report.update({
            "ga_pop": int(args.ga_pop),
            "ga_gens": int(args.ga_gens),
            "ga_elite_frac": float(args.ga_elite_frac),
            "ga_tournament_k": int(args.ga_tournament_k),
            "ga_cx_probs": (float(args.ga_cx_prob_uniform), float(args.ga_cx_prob_column), float(args.ga_cx_prob_blx)),
            "ga_blx_alpha": float(args.ga_blx_alpha),
            "ga_mut_sigma_init": float(args.ga_mut_sigma_init),
            "ga_mut_sigma_min": float(args.ga_mut_sigma_min),
            "ga_mut_sigma_max": float(args.ga_mut_sigma_max),
            "ga_mut_sigma_tau": float(args.ga_mut_sigma_tau),
            "ga_memetic_steps": int(args.ga_memetic_steps),
            "ga_early_stop_gens": int(args.ga_early_stop_gens),
            "ga_penalty_l2w0": float(args.ga_penalty_l2w0),
            "ga_penalty_gap": float(args.ga_penalty_gap),
        })
    try:
        base = os.path.splitext(OUTPUT or INPUT)[0]
        rep_path = args.report_json or base + "_report.json"
        with open(rep_path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas atualizadas:", ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_DIAG, ABA_COMPARATIVO_TUDO)
    print("➡️ FINAL top1 TR/EARLY/TEST =", f"({m_tr_k1:.3%}/{m_ea_k1:.3%}/{m_te_k1:.3%})",
          "| top2 =", f"({m_tr_k2:.3%}/{m_ea_k2:.3%}/{m_te_k2:.3%})",
          "| top3 =", f"({m_tr_k3:.3%}/{m_ea_k3:.3%}/{m_te_k3:.3%})")
    print(f"💾 Arquivo salvo em: {saved_path}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Softmax + W∈[-1,1] + split train/early/test + GA (uniforme/coluna/BLX-α) + mutação auto-adaptativa + refinamento memético + COMBO (TR/EARLY).")
    p.add_argument("--input", default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx")
    p.add_argument("--output", default=None)
    p.add_argument("--sheet-dados", default="TDados_clean")
    p.add_argument("--sheet-pontos", default="Pontuação_new_range")
    p.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    p.add_argument("--sheet-resultado-tun", default="Resultado_Heuristica_Tunada")
    p.add_argument("--sheet-metricas-tun", default="Metricas_Heuristica_Tunada")
    p.add_argument("--sheet-regras-normal", default="Regras_Normal")
    p.add_argument("--sheet-comparativo", default="Comparativo_TopK_Tudo")
    p.add_argument("--sheet-diag", dest="sheet_diag", default="Diagnostico_SUM")
    p.add_argument("--prefer-tunada", action="store_true", default=True)
    p.add_argument("--n-classes", type=int, default=7)
    p.add_argument("--linha-inicio-pontos", type=int, default=3)
    p.add_argument("--col-alvo", default="Alvo")

    # Frações: 1/3 - 1/3 - 1/3 por padrão
    p.add_argument("--train-frac", type=float, default=1.0/3.0, help="fração do pool elegível usada para TREINO")
    p.add_argument("--early-frac", type=float, default=1.0/3.0, help="fração do pool elegível usada para EARLY; o restante vira TEST (hold-out final)")
    p.add_argument("--min-support-val", type=int, default=1)

    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)

    # Regularização e passo (para memético/SGD)
    p.add_argument("--l1", type=float, default=0.01)
    p.add_argument("--l2", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=0.005)

    # SGD-only
    p.add_argument("--max-iters", type=int, default=15000)
    p.add_argument("--check-every", type=int, default=1)
    p.add_argument("--early-stop-patience", type=int, default=150, help="É a paciência do early stop: quantos checkpoints seguidos podemos tolerar sem melhora no COMBO antes de parar.")

    # Anti-overfit adicionais (usados no gradiente de treino e no refinamento memético)
    p.add_argument("--label-smoothing", type=float, default=0.05, help="suavização dos alvos (0=off)")
    p.add_argument("--input-noise-sigma", type=float, default=0.02, help="ruído gaussiano em X (apenas no passo de gradiente do TREINO/memético)")
    p.add_argument("--feature-dropout", type=float, default=0.05, help="porcentagem de colunas de X mascaradas por iteração (0..1)")

    # Mutations no modo SGD (habilitadas por padrão)
    p.add_argument("--mutations", action="store_true", default=True)
    p.add_argument("--mutation-every", type=int, default=1)
    p.add_argument("--mutation-sigma", type=float, default=0.1)
    p.add_argument("--mutation-max-tries", type=int, default=1200)

    # ----------------- GA args -----------------
    p.add_argument("--ga", action="store_true", default=True, help="ativa o modo GA (genetic algorithm)")
    p.add_argument("--ga-pop", type=int, default=128, help="tamanho da população")
    p.add_argument("--ga-gens", type=int, default=15000, help="número máximo de gerações")
    p.add_argument("--ga-elite-frac", type=float, default=0.1, help="fração elitista (mantida intacta em cada geração)")
    p.add_argument("--ga-tournament-k", type=int, default=40, help="tamanho do torneio para seleção de pais")
    p.add_argument("--ga-cx-prob-uniform", type=float, default=0.4, help="probabilidade de crossover uniforme")
    p.add_argument("--ga-cx-prob-column", type=float, default=0.4, help="probabilidade de crossover por coluna (class-wise)")
    p.add_argument("--ga-cx-prob-blx", type=float, default=0.5, help="probabilidade de crossover BLX-α/aritmético")
    p.add_argument("--ga-blx-alpha", type=float, default=0.2, help="α do BLX-α (λ ~ U(-α, 1+α))")
    p.add_argument("--ga-mut-sigma-init", type=float, default=0.08, help="σ inicial da mutação por indivíduo")
    p.add_argument("--ga-mut-sigma-min", type=float, default=0.005, help="σ mínimo (clamp)")
    p.add_argument("--ga-mut-sigma-max", type=float, default=0.2, help="σ máximo (clamp)")
    p.add_argument("--ga-mut-sigma-tau", type=float, default=0.15, help="taxa de adaptação log-normal da σ (self-adaptive)")
    p.add_argument("--ga-memetic-steps", type=int, default=20, help="passos de gradiente local por filho (memetic refinement)")
    p.add_argument("--ga-early-stop-gens", type=int, default=1200, help="geraçōes sem melhora em COMBO para parar o GA")
    p.add_argument("--ga-penalty-l2w0", type=float, default=0.05, help="penalidade λ * ||W-W0||^2 / |W| no fitness")
    p.add_argument("--ga-penalty-gap", type=float, default=0.0, help="penalidade α * max(0, TR - EARLY) no fitness")

    # --------- PESOS DO CRITÉRIO COMBO (TR vs EARLY) ---------
    p.add_argument("--sel-w-tr", type=float, default=0.3, help="peso de TR no critério COMBO")
    p.add_argument("--sel-w-early", type=float, default=0.6, help="peso de EARLY no critério COMBO")

    p.add_argument("--report-json", default="report.json")
    p.add_argument("--n-jobs", type=int, default=os.cpu_count())
    p.add_argument("--blas-threads", type=int, default=1)

    args = p.parse_args(); np.random.seed(args.seed); main(args)