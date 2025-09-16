# -*- coding: utf-8 -*-
"""
05_tuna_heuristica_TreinoValid.py (v3.0.1 - split 1/3-1/3-1/3 com early-stop por EARLY e limite W∈[-1,1])
- Mantém: softmax puro, L1/L2, proximal step, snapshots, mutações evolutivas (ON por padrão).
- Novidades:
  * Split em três conjuntos: TREINO (ajuste de pesos), EARLY (early-stop e seleção de best_W) e TEST (hold-out final).
  * Critério de seleção de best_W baseado em EARLY.
  * Early-stop guiado por EARLY.
  * Critério de PARADA pela meta continua olhando apenas TREINO (como solicitado).
  * Pesos W sempre projetados em [-1, 1] (incluindo bias).
  * Correção no clip inicial de W0 (antes travava em 1.0).
  * Relatórios incluem TR/EARLY/TEST.
"""

import os, sys, argparse, shutil, tempfile, json
from datetime import datetime
import numpy as np
import pandas as pd

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
    """Converte string de rótulos em listas, mantendo apenas classes do conjunto core_classes.
       Ignora 'nao'/'não' e rótulos fora de core_classes.
    """
    CORE = set(core_classes)
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS: s = s.replace(d,"|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não"): continue
            if lab in CORE:
                labs.append(lab)
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

# ======= PROJEÇÃO AGORA É SEMPRE EM [-1, 1] =======
def project_bounds(W, adjustable_mask, W0, eps=1.0):
    Wp = W.copy()
    Wp[~adjustable_mask] = W0[~adjustable_mask]
    # clip simétrico
    Wp[adjustable_mask] = np.clip(Wp[adjustable_mask], -1.0*eps, eps)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask):
    G = grad.copy(); G[~adjustable_mask] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    thr = lr*l1
    Delta = np.sign(Delta)*np.maximum(np.abs(Delta)-thr, 0.0)
    W_new = W0 + Delta
    return project_bounds(W_new, adjustable_mask, W0, 1.0)

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

def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception: pass

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
    TARGET_MACRO_TOPK = args.target_macro_topk; RANDOM_STATE = args.seed
    REPORT_JSON = args.report_json; N_JOBS = max(1, args.n_jobs)

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

    # Normalizações
    X_all = np.clip(np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)
    X_all_full = np.clip(np.nan_to_num(X_all_full, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)

    # Rotulagem (mantém apenas classes do core)
    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core)

    # Filtra apenas linhas com algum rótulo do core para treino/valid
    keep_nonempty = [len(l)>0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]; df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]
    n_all = X_all.shape[0]

    class_names = class_core
    class_to_idx = {c:i for i,c in enumerate(class_names)}
    idx_to_class = {i:c for i,c in enumerate(class_names)}

    # Split por suporte mínimo para formar pool elegível
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

    # marcação textual (debug)
    split = np.array(["other"]*n_all, dtype=object)
    split[idx_train] = "train"
    split[idx_early] = "early"
    split[idx_test]  = "valid_final"
    split[idx_minor_train_for_grid] = "minor_train"

    # Alvos e matrizes com bias
    y_train = [y_lists_all[i] for i in idx_train]
    y_early = [y_lists_all[i] for i in idx_early]
    y_test  = [y_lists_all[i] for i in idx_test]
    Kc = len(class_names)
    Y_train = y_distribution(y_train, class_to_idx, Kc)

    # ---------- REGRA DE OURO ---------- (corrigido: clip em [-1,1])
    mask_w_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)  # (features,)
    W0_eff_core = W0_sheet.copy()
    W0_eff_core[~mask_w_all_zero, :] = np.clip(W0_eff_core[~mask_w_all_zero, :], -1.0, 1.0)

    # Parâmetros iniciais com bias
    W0 = np.zeros((m+1, Kc), dtype=float)
    W0[:m, :Kc] = W0_eff_core
    W0[m, :Kc]  = 0.0  # bias inicial

    adjustable = np.zeros_like(W0, dtype=bool)
    adjustable[:m, :Kc] = ~mask_w_all_zero[:, None]
    adjustable[m, :Kc]  = True  # ajustar bias sempre

    W = W0.copy()

    # Matrizes com bias
    Xb_all   = with_bias(X_all)
    Xb_train = with_bias(X_all[idx_train])
    Xb_early = with_bias(X_all[idx_early])
    Xb_test  = with_bias(X_all[idx_test])
    Xb_all_full = with_bias(X_all_full)

    # --------- Funções de perda e avaliação ---------
    def loss_with_regularizers(Wmat):
        # Cross-entropy média (multi-label via distribuição Y_train)
        P = forward(Wmat, Xb_train)
        eps = 1e-12
        ce = -np.mean(np.sum(Y_train * np.log(P + eps), axis=1))
        l2 = L2 * np.sum((Wmat - W0)**2)          # L2
        l1 = L1 * np.sum(np.abs(Wmat - W0))       # L1 (apenas para logging)
        return ce + l2 + 0.0*l1, ce, l2

    # Avalia TREINO vs EARLY (para seleção de best_W / early stop)
    def objective_early(Wmat):
        m_tr, m_ea = macro_topk_pair(y_train, Xb_train, y_early, Xb_early, Wmat, class_to_idx, idx_to_class, k=TOPK)
        return m_tr, m_ea

    # Baseline
    tr0, ea0 = objective_early(W)
    print("[BASE] " + fmt_pair(f"macro_top{TOPK}", tr0, ea0))
    print(f"[INFO] tamanhos (TR/EARLY/TEST)=({Xb_train.shape[0]}/{Xb_early.shape[0]}/{Xb_test.shape[0]})")
    print(f"[ALVO] meta para parar: TR>= {TARGET_MACRO_TOPK:.0%}")

    best_score_ea = ea0; best_score_tr = tr0; best_W = W.copy()
    diag_rows = []
    total_checks = 0
    rng_mut = np.random.default_rng(RANDOM_STATE+7)

    for it in range(1, MAX_ITERS+1):
        if _user_requested_quit():
            print("[PARAR] Interrompido pelo usuário (tecla 'q')."); break

        # Gradiente no TREINO
        P_tr = forward(W, Xb_train)
        n_tr = max(Xb_train.shape[0], 1)
        Gs   = (P_tr - Y_train) / n_tr
        Gw   = Xb_train.T @ Gs  # (m+1, Kc)

        # Step proximal
        W = proximal_step(W, Gw, W0, LR, L1, L2, adjustable)

        # Mutações periódicas (aceita somente se EARLY melhorar)
        if args.mutations and (it % args.mutation_every == 0):
            improved_local = False
            base_tr, base_ea = objective_early(W)
            for _try in range(args.mutation_max_tries):
                W_mut = W.copy()
                noise = rng_mut.normal(loc=0.0, scale=args.mutation_sigma, size=W_mut.shape)
                noise[~adjustable] = 0.0
                W_mut += noise
                W_mut = project_bounds(W_mut, adjustable, W0, 1.0)
                tr_mut, ea_mut = objective_early(W_mut)
                if ea_mut > base_ea + 1e-9:  # critério em EARLY
                    W = W_mut
                    base_tr, base_ea = tr_mut, ea_mut
                    improved_local = True
            if improved_local:
                print(f"[MUT] melhoria aceita no it={it}: EARLY {base_ea:.3%}")

        # Checagem
        if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
            total_checks += 1
            cur_tr, cur_ea = objective_early(W)

            improved = False
            if cur_ea > best_score_ea + 1e-6:
                best_score_ea = cur_ea
                best_score_tr = cur_tr
                best_W = W.copy()
                improved = True

            diag_rows.append({
                "iter": it,
                f"macro_top{TOPK}_TR": cur_tr,
                f"macro_top{TOPK}_EARLY": cur_ea,
                "improved": improved
            })

            print(f"[IT {it:05d}] " + fmt_pair(f"macro_top{TOPK}", cur_tr, cur_ea) +
                  f"  best(TR/EARLY)=({best_score_tr:.3%}/{best_score_ea:.3%})")

            # Parada pela meta — olhando só TREINO (como solicitado)
            if best_score_tr >= TARGET_MACRO_TOPK:
                print("[PARAR] Atingiu meta no TREINO."); break

            # Early stop: sem melhora em EARLY por 'patience' janelas
            if not improved and len(diag_rows) > args.early_stop_patience:
                recent_ea = [r[f"macro_top{TOPK}_EARLY"] for r in diag_rows[-args.early_stop_patience:]]
                if max(recent_ea) <= best_score_ea + 1e-6:
                    print("[PARAR] Early stop (sem melhora no EARLY)."); break

    # ---------- Final com best_W selecionado por EARLY ----------
    W_tuned = project_bounds(best_W, adjustable, W0, 1.0)

    # Probabilidades em ALL / ALL_FULL (para abas)
    P_all = forward(W_tuned, Xb_all)
    P_all_full = forward(W_tuned, Xb_all_full)

    # Métricas finais por split (k1..k3)
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

    # Resultado_Heuristica_Tunada (filtrado)
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
        for t in range(min(3, P_all_full.shape[1])):
            c = order_full[i, t]
            rec[f"top{t+1}_classe"] = class_names[c]
            rec[f"top{t+1}_prob"]   = float(P_all_full[i, c])
        tops_full.append(rec)
    df_comp = pd.concat([df_comp, pd.DataFrame(tops_full)], axis=1)

    # Métricas por classe no EARLY e TEST (k=TOPK) + agregados TR/EARLY/TEST
    P_tr_final    = forward(W_tuned, Xb_train)
    P_early_final = forward(W_tuned, Xb_early)
    P_test_final  = forward(W_tuned, Xb_test)

    rows = []
    for c_idx, c_name in enumerate(class_names):
        # TREINO
        mask_tr = np.array([c_name in labs for labs in y_train], bool)
        sup_tr = int(mask_tr.sum())
        rate_tr = np.nan; hits_tr = 0
        if sup_tr > 0:
            ord_tr = np.argsort(-P_tr_final[mask_tr], axis=1)[:, :TOPK]
            hits_tr = sum(c_idx in ord_tr[r] for r in range(ord_tr.shape[0]))
            rate_tr = hits_tr / sup_tr

        # EARLY
        mask_ea = np.array([c_name in labs for labs in y_early], bool)
        sup_ea = int(mask_ea.sum())
        rate_ea = np.nan; hits_ea = 0
        if sup_ea > 0:
            ord_ea = np.argsort(-P_early_final[mask_ea], axis=1)[:, :TOPK]
            hits_ea = sum(c_idx in ord_ea[r] for r in range(ord_ea.shape[0]))
            rate_ea = hits_ea / sup_ea

        # TEST
        mask_te = np.array([c_name in labs for labs in y_test], bool)
        sup_te = int(mask_te.sum())
        rate_te = np.nan; hits_te = 0
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
        "observacao": "Best_W selecionado por EARLY; TEST é hold-out final."
    }])

    df_metricas_tun = pd.concat([
        pd.DataFrame([{"secao":"agregado", **df_met_sum.iloc[0].to_dict()}]),
        df_met_cls.assign(secao="por_classe")
    ], ignore_index=True)

    # Regras/diagnóstico
    df_regras = pd.DataFrame([
        {"param": "mutations", "value": bool(args.mutations)},
        {"param": "mutation_every", "value": int(args.mutation_every)},
        {"param": "mutation_sigma", "value": float(args.mutation_sigma)},
        {"param": "mutation_max_tries", "value": int(args.mutation_max_tries)},
        {"param": "l1", "value": float(L1)},
        {"param": "l2", "value": float(L2)},
        {"param": "lr", "value": float(LR)},
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
        "checks": int(total_checks), "used_sheet": aba_pontos_usada, "output_file": saved_path,
        "postrule": "none_softmax_core_only", "n_jobs": int(N_JOBS),
        "mutations": bool(args.mutations)
    }
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
    p = argparse.ArgumentParser(description="Treino com softmax puro, W∈[-1,1], split 1/3-1/3-1/3 (train/early/test) e mutações evolutivas.")
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

    # ==== NOVO: frações para split 1/3 - 1/3 - 1/3 ====
    p.add_argument("--train-frac", type=float, default=1.0/3.0,
                   help="fração do pool elegível usada para TREINO")
    p.add_argument("--early-frac", type=float, default=1.0/3.0,
                   help="fração do pool elegível usada para EARLY; o restante vira TEST (hold-out final)")

    p.add_argument("--min-support-val", type=int, default=2)
    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--l1", type=float, default=0.0025)
    p.add_argument("--l2", type=float, default=0.02)
    p.add_argument("--lr", type=float, default=0.02)
    p.add_argument("--max-iters", type=int, default=10000)
    p.add_argument("--check-every", type=int, default=50)
    p.add_argument("--early-stop-patience", type=int, default=1000)
    p.add_argument("--target-macro-topk", type=float, default=0.95)  # ligeiramente mais realista para TR

    # Mutações (ligadas por padrão)
    p.add_argument("--mutations", action="store_true", default=True, help="Habilita mutações evolutivas (ruído Gaussiano + aceitação gulosa por EARLY).")
    p.add_argument("--mutation-every", type=int, default=1, help="Intervalo de iterações entre tentativas de mutação.")
    p.add_argument("--mutation-sigma", type=float, default=0.07, help="Desvio padrão do ruído Gaussiano aplicado aos parâmetros.")
    p.add_argument("--mutation-max-tries", type=int, default=15, help="Número de tentativas por rodada de mutação.")

    p.add_argument("--report-json", default="report.json")
    p.add_argument("--n-jobs", type=int, default=os.cpu_count())
    p.add_argument("--blas-threads", type=int, default=1)
    args = p.parse_args(); np.random.seed(args.seed); main(args)