"""
train_st_heuristica.py  (versão alinhada ao requisito "ST só na pós-regra")
--------------------------------------------------------------------------
Treina/tuna a heurística nas classes da aba Pontuação (K0 classes),
NÃO adiciona a coluna "Sem Transtorno" (ST) em W.
A ST existe apenas na PÓS-REGRA aplicada às probabilidades.
Os rótulos "Sem Transtorno" presentes no Alvo são usados APENAS
para ajustar (T1, T2, γ) via grid no TREINO e para avaliar na VALIDAÇÃO.

Rótulos 'não'/'nao' são ignorados/desprezados.
Linhas com "ST" podem entrar no split 2/3–1/3 para TREINO/VALIDAÇÃO
apenas para fins de ajuste/avaliação da pós-regra, mas NÃO entram no gradiente.

Uso típico:
    py train_st_heuristica.py --input "c:\\SourceCode\\qip\\python\\banco_dados.xlsx"
"""

import os, shutil, tempfile, argparse, json, sys
from datetime import datetime
import numpy as np
import pandas as pd

# ================== UTIL ==================
def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl  # garante engine
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.xlsx")
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile)
        base_existed = True
    except Exception:
        with pd.ExcelWriter(tmpfile, engine="openpyxl", mode="w") as writer:
            pass
    mode = "a" if base_existed else "w"
    with pd.ExcelWriter(tmpfile, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
        for df, sheet in dfs_and_sheets:
            df.to_excel(writer, sheet_name=sheet, index=False)
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

def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i")
             .replace("ó","o").replace("ô","o")
             .replace("ú","u"))

def parse_multilabel(series, core_classes, normal_label="Sem Transtorno"):
    """
    Lê coluna Alvo como multilabel.
    - Delimitadores aceitos: | ; ,
    - Rótulos 'não'/'nao' são IGNORADOS (desprezados).
    - Mantém apenas rótulos em core_classes ∪ {normal_label}.
    NÃO mapeia 'não'/'nao' para normal_label.
    """
    CORE = set(core_classes)
    KNOWN = CORE | {normal_label}
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao", "não"):  # despreza
                continue
            if lab in KNOWN:
                labs.append(lab)
        out.append(labs)
    return out

def y_distribution(y_lists, class_to_idx, K):
    """Distribuição-alvo por linha (soma 1 entre rótulos positivos)."""
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=float)
    for i, labs in enumerate(y_lists):
        pos = [class_to_idx[c] for c in labs if c in class_to_idx]
        if pos:
            w = 1.0 / len(pos)
            for j in pos:
                Y[i, j] = w
    return Y

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    """Macro top-k: média da taxa de acerto em top-k por classe (suporte>0)."""
    order = np.argsort(-proba, axis=1)
    topk = order[:, :k]
    accs = []
    for c in range(proba.shape[1]):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits / sup)
    return (float(np.mean(accs)) if accs else 0.0)

def project_bounds(W, adjustable_mask, W0, eps=1e-6):
    """
    Projeção:
      - colunas NÃO ajustáveis -> exatamente W0 (congeladas)
      - colunas ajustáveis     -> clip para [eps, 1]
    """
    Wp = W.copy()
    Wp[~adjustable_mask, :] = W0[~adjustable_mask, :]
    if np.any(adjustable_mask):
        Wp[adjustable_mask, :] = np.clip(Wp[adjustable_mask, :], eps, 1.0)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask, eps):
    """Passo proximal (Elastic Net em torno de W0) + projeção."""
    G = grad.copy()
    G[~adjustable_mask, :] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    thr = lr * l1
    Delta = np.sign(Delta) * np.maximum(np.abs(Delta) - thr, 0.0)
    W_new = W0 + Delta
    return project_bounds(W_new, adjustable_mask, W0, eps)

# ======= Pós-regra para "Sem Transtorno" (ST) sem aumentar K =======
def add_normal_by_rule(P_core, T1, T2, gamma, st_name="Sem Transtorno"):
    """
    Recebe P_core (n, K0) de classes "core".
    Se (top1 < T1) e (top1 - top2 < T2), aloca γ para ST e reescala demais por (1-γ).
    Retorna P_aug (n, K0+1) com coluna extra ST ao final e máscara de linhas onde a regra acionou.
    """
    n, K0 = P_core.shape
    if K0 == 0:
        raise ValueError("P_core sem colunas.")
    order = np.argsort(-P_core, axis=1)
    top1_idx = order[:, 0]
    top2_idx = order[:, 1] if K0 > 1 else np.zeros(n, dtype=int)
    top1 = P_core[np.arange(n), top1_idx]
    top2 = P_core[np.arange(n), top2_idx] if K0 > 1 else np.zeros(n)
    hits = (top1 < T1) & ((top1 - top2) < T2)

    p_norm = np.zeros(n, dtype=float)
    p_norm[hits] = gamma

    scale = np.ones(n, dtype=float)
    scale[hits] = (1.0 - gamma)
    P_scaled = P_core * scale[:, None]

    P_aug = np.concatenate([P_scaled, p_norm[:, None]], axis=1)
    # renormaliza por robustez numérica
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), 1e-12)
    class_names_aug = None  # deixamos para o chamador
    return P_aug, hits

def grid_search_postrule(P_core, y_lists_aug, class_names_aug, topk=3,
                         grid_T1=None, grid_T2=None, grid_gamma=None):
    """Busca T1,T2,γ maximizando macro top-k, com ST adicionada pós-regra (sem aumentar K de W)."""
    if grid_T1 is None:
        grid_T1 = np.linspace(0.18, 0.60, 12)
    if grid_T2 is None:
        grid_T2 = np.linspace(0.02, 0.20, 10)
    if grid_gamma is None:
        grid_gamma = np.linspace(0.30, 0.75, 10)

    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}

    best = (-1.0, None, None, None, None)
    for T1 in grid_T1:
        for T2 in grid_T2:
            for g in grid_gamma:
                P_aug, hits = add_normal_by_rule(P_core, T1, T2, g, st_name=class_names_aug[-1])
                macro = macro_topk(y_lists_aug, P_aug, class_to_idx_aug, idx_to_class_aug, k=topk)
                if macro > best[0] + 1e-9:
                    best = (macro, T1, T2, g, float(hits.mean()))
    return best  # macro, T1, T2, gamma, hit_rate

# ================== PIPELINE ==================
def main(args):
    # ---------- CONFIG ----------
    INPUT = args.input
    OUTPUT = args.output or INPUT

    ABA_DADOS = args.sheet_dados
    ABA_PONTOS_TUNADA = args.sheet_pontos_tunada
    ABA_PONTOS = args.sheet_pontos
    ABA_RES_HEUR_TUN = args.sheet_resultado_tun
    ABA_MET_HEUR_TUN = args.sheet_metricas_tun
    ABA_EXPLICAO = args.sheet_explicacao
    ABA_REGRAS_NORMAL = args.sheet_regras_normal
    ABA_COMPARATIVO_TUDO = args.sheet_comparativo

    COLUNA_TAM = args.n_classes            # nº de classes em Pontuação (K0, SEM ST)
    LINHA_INICIO_PONTOS = args.linha_inicio_pontos
    COL_ALVO = args.col_alvo
    TOPK = args.topk

    # otimização
    LAMBDA_L1 = args.l1
    LAMBDA_L2 = args.l2
    LR        = args.lr
    MAX_ITERS = args.max_iters
    CHECK_EVERY = args.check_every
    TARGET_MACRO_TOPK = args.target_macro_topk
    EPS_W = args.eps_w
    RANDOM_STATE = args.seed

    # split
    ST_LABEL = args.normal_label  # nome exato no Alvo para "Sem Transtorno"
    TRAIN_FRAC = args.train_frac
    MIN_SUPPORT_VAL = args.min_support_val

    # grid
    GRID_T1 = np.linspace(args.grid_t1_min, args.grid_t1_max, args.grid_t1_steps)
    GRID_T2 = np.linspace(args.grid_t2_min, args.grid_t2_max, args.grid_t2_steps)
    GRID_G  = np.linspace(args.grid_g_min,  args.grid_g_max,  args.grid_g_steps)

    # GA (variabilidade genética)
    GA_NUM = args.ga_num_mutants
    GA_COLS = args.ga_mutate_cols
    GA_SCALE = args.ga_mutation_scale

    REPORT_JSON = args.report_json

    print("[INFO] Configuração:")
    print(f"  INPUT={INPUT} | OUTPUT={OUTPUT}")
    print(f"  Dados={ABA_DADOS} | Pontuação preferida Tunada? {args.prefer_tunada}")
    print(f"  TOPK={TOPK} | TRAIN_FRAC={TRAIN_FRAC:.4f} | MIN_SUPPORT_VAL={MIN_SUPPORT_VAL}")
    print(f"  seed={RANDOM_STATE} | max_iters={MAX_ITERS} | check_every={CHECK_EVERY}")
    print(f"  grid T1=[{args.grid_t1_min},{args.grid_t1_max}]x{args.grid_t1_steps}  "
          f"T2=[{args.grid_t2_min},{args.grid_t2_max}]x{args.grid_t2_steps}  "
          f"gamma=[{args.grid_g_min},{args.grid_g_max}]x{args.grid_g_steps}")
    print(f"  GA: num_mutants={GA_NUM} mutate_cols={GA_COLS} scale={GA_SCALE}")
    print(f"  REPORT_JSON={REPORT_JSON}")

    # ================== LEITURA BASE ==================
    df_all = pd.read_excel(INPUT, sheet_name=ABA_DADOS)

    # Decide qual matriz de pesos usar (Tunada se existir e preferida)
    xl = pd.ExcelFile(INPUT)
    usar_tunada = args.prefer_tunada and (ABA_PONTOS_TUNADA in xl.sheet_names)
    aba_pontos_usada = ABA_PONTOS_TUNADA if usar_tunada else ABA_PONTOS
    df_pont = pd.read_excel(INPUT, sheet_name=aba_pontos_usada)

    # X (colunas da B em diante)
    cols_dados = df_all.columns[1:]
    if len(cols_dados) == 0:
        raise ValueError(f"{ABA_DADOS} não possui colunas a partir da coluna B.")
    X_all = df_all[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    n_all, m = X_all.shape

    # Seleção de linhas/classes na Pontuação (K0 classes CORE)
    r0 = LINHA_INICIO_PONTOS - 2
    linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM:
        raise ValueError(f"Aba '{aba_pontos_usada}' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

    faltantes = [c for c in cols_dados if c not in df_pont.columns]
    if faltantes:
        raise ValueError(f"Colunas de {ABA_DADOS} ausentes em '{aba_pontos_usada}': "
                         f"{faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

    # W0 core (m, K0)
    W_block = df_pont.loc[linhas_modelos, cols_dados]
    W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T  # (m, K0)
    K0 = W0.shape[1]
    if K0 != COLUNA_TAM:
        raise ValueError(f"Dimensão inesperada de W core: {W0.shape}, esperado K0={COLUNA_TAM}.")

    # nomes de classes CORE
    if "Tipo de Transtorno" in df_pont.columns:
        class_core = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
    else:
        class_core = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    # saneamento X_all
    X_all = np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0)
    X_all = np.clip(X_all, 0.0, 1.0)

    # alvo multilabel (CORE ∪ ST), ignorando 'não'/'nao'
    y_lists_all = parse_multilabel(df_all[COL_ALVO], class_core, normal_label=ST_LABEL)

    # manter linhas com pelo menos 1 rótulo entre (CORE ∪ ST)
    keep_nonempty = [len(l) > 0 for l in y_lists_all]
    X_all = X_all[keep_nonempty]
    df_all = df_all.loc[keep_nonempty].reset_index(drop=True)
    y_lists_all = [l for l,k in zip(y_lists_all, keep_nonempty) if k]
    n_all = X_all.shape[0]

    # Versões dos rótulos
    CORE = set(class_core)
    # versão CORE-only (para gradiente):
    y_core_all = [[c for c in labs if c in CORE] for labs in y_lists_all]
    # versão AUG (CORE + ST) para grid/metrics:
    class_names_aug = class_core + [ST_LABEL]

    # ====== SUPORTE para split (usado para grid: CORE + ST) ======
    suportes_aug = {c: sum(c in labs for labs in y_lists_all) for c in class_names_aug}
    eligible_labels_aug = {c for c,s in suportes_aug.items() if s >= MIN_SUPPORT_VAL}
    minor_labels_aug    = set(class_names_aug) - eligible_labels_aug

    has_eligible_aug = np.array([any(c in eligible_labels_aug for c in l) for l in y_lists_all], dtype=bool)
    has_only_minor_aug= np.array([all(c in minor_labels_aug for c in l) for l in y_lists_all], dtype=bool)

    # Pool para split (linhas com pelo menos uma label elegível — CORE ou ST)
    idx_tv_pool = np.where(has_eligible_aug)[0]
    # Linhas que vão 100% pro TREINO para efeito de grid (apenas minoritárias nas labels AUG)
    idx_minor_train_for_grid = np.where(has_only_minor_aug)[0]

    # ---------- split guloso por label (AUG) ----------
    rng = np.random.default_rng(RANDOM_STATE)
    y_tv_aug = [y_lists_all[i] for i in idx_tv_pool]

    targets_train = {c: int(np.floor(TRAIN_FRAC * sum(c in labs for labs in y_tv_aug)))
                     for c in eligible_labels_aug}
    counts_train = {c: 0 for c in eligible_labels_aug}

    n_tv = len(y_tv_aug)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)
    assign_train_local = np.zeros(n_tv, dtype=bool)
    assign_val_local   = np.zeros(n_tv, dtype=bool)

    for i in order_idx:
        labs = [c for c in y_tv_aug[i] if c in eligible_labels_aug]
        if not labs:
            assign_train_local[i] = True
            continue
        needs = any(counts_train[c] < targets_train[c] for c in labs)
        if needs:
            assign_train_local[i] = True
            for c in labs:
                if counts_train[c] < targets_train[c]:
                    counts_train[c] += 1
        else:
            assign_val_local[i] = True

    # índices GLOBAIS para GRID/MÉTRICAS
    idx_train_grid = np.concatenate([idx_tv_pool[np.where(assign_train_local)[0]],
                                     idx_minor_train_for_grid], axis=0)
    idx_val_grid   = idx_tv_pool[np.where(assign_val_local)[0]]
    idx_train_grid = np.unique(idx_train_grid)
    idx_val_grid   = np.setdiff1d(np.unique(idx_val_grid), idx_train_grid)

    # ---------- Conjuntos para GRADIENTE (apenas CORE labels) ----------
    has_core_label = np.array([len([c for c in labs if c in CORE])>0 for labs in y_lists_all], dtype=bool)
    idx_train_grad = idx_train_grid[has_core_label[idx_train_grid]]  # remove linhas ST-only
    # (Validação não é usada no gradiente)

    # ---------- prepara matrizes e distribuições ----------
    adjustable_mask = (X_all.max(axis=0) > 0)
    print(f"[INFO] Colunas congeladas (X coluna toda = 0): {int((~adjustable_mask).sum())}")
    print(f"[INFO] Colunas ajustáveis (X tem algum valor >0): {int(adjustable_mask.sum())}")

    class_to_idx_core = {c:i for i,c in enumerate(class_core)}
    idx_to_class_core = {i:c for i,c in enumerate(class_core)}
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for i,c in enumerate(class_names_aug)}

    X_train_grad = X_all[idx_train_grad]
    X_train_grid = X_all[idx_train_grid]
    X_val_grid   = X_all[idx_val_grid]

    y_train_core = [y_core_all[i] for i in idx_train_grad]     # para CE
    y_train_aug  = [y_lists_all[i] for i in idx_train_grid]    # para grid
    y_val_aug    = [y_lists_all[i] for i in idx_val_grid]      # para métricas/seleção

    # Distribuição alvo APENAS CORE (K0)
    K0 = len(class_core)
    Ydist_train = y_distribution(y_train_core, class_to_idx_core, K0)

    # W inicial
    W = project_bounds(W0.copy(), adjustable_mask, W0, EPS_W)

    # ---- helpers de avaliação com grid (ST pós-regra) ----
    def grid_eval(W_current):
        # treino (para buscar T1/T2/γ)
        P_tr_core = softmax_rows(X_train_grid @ W_current)  # (n_tr_grid, K0)
        macro_tr, T1_b, T2_b, G_b, hit_tr = grid_search_postrule(
            P_tr_core, y_train_aug, class_names_aug, topk=TOPK,
            grid_T1=GRID_T1, grid_T2=GRID_T2, grid_gamma=GRID_G
        )
        # validação (com parâmetros do treino)
        P_v_core  = softmax_rows(X_val_grid @ W_current)
        P_v_aug, _ = add_normal_by_rule(P_v_core, T1_b, T2_b, G_b, st_name=ST_LABEL)
        macro_val = macro_topk(y_val_aug, P_v_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK)
        return macro_val, (T1_b, T2_b, G_b), hit_tr

    # baseline
    best_macro_val, (best_T1, best_T2, best_G), best_hit_tr = grid_eval(W)
    best_W = W.copy()
    no_improve = 0
    print(f"[INFO] Baseline VALID macro top-{TOPK} (grid no TREINO): {best_macro_val:.3%} | "
          f"T1={best_T1:.3f} T2={best_T2:.3f} γ={best_G:.2f} | aciona_TREINO={best_hit_tr:.1%}")

    rng = np.random.default_rng(RANDOM_STATE)

    # ---------- loop de treino (grad + mutação genética) ----------
    total_checks = 0
    for it in range(1, MAX_ITERS+1):
        # grad no TREINO (apenas CORE)
        if X_train_grad.shape[0] > 0:
            P_tr = softmax_rows(X_train_grad @ W)
            n_tr = max(X_train_grad.shape[0], 1)
            Gs   = (P_tr - Ydist_train) / n_tr
            Gw   = X_train_grad.T @ Gs
            W = proximal_step(W, Gw, W0, LR, LAMBDA_L1, LAMBDA_L2, adjustable_mask, EPS_W)

        if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
            total_checks += 1
            macro_val, (T1_c, T2_c, G_c), hit_tr = grid_eval(W)

            improved = False
            if macro_val > best_macro_val + 1e-6:
                best_macro_val = macro_val
                best_W = W.copy()
                best_T1, best_T2, best_G = T1_c, T2_c, G_c
                best_hit_tr = hit_tr
                improved = True

            # ====== VARIABILIDADE GENÉTICA (mutantes) ======
            if GA_NUM > 0 and GA_COLS > 0 and GA_SCALE > 0:
                cand_W = best_W.copy()
                best_local_macro = best_macro_val
                best_local_tuple = (best_T1, best_T2, best_G, best_hit_tr)

                for _ in range(GA_NUM):
                    W_mut = cand_W.copy()
                    cols = rng.choice(W_mut.shape[1], size=min(GA_COLS, W_mut.shape[1]), replace=False)
                    noise = 1.0 + rng.normal(0.0, GA_SCALE, size=(W_mut.shape[0], len(cols)))
                    W_mut[:, cols] = W_mut[:, cols] * noise
                    W_mut = project_bounds(W_mut, adjustable_mask, W0, EPS_W)

                    mval, (t1m, t2m, gm), hitm = grid_eval(W_mut)
                    if mval > best_local_macro + 1e-6:
                        best_local_macro = mval
                        cand_W = W_mut.copy()
                        best_local_tuple = (t1m, t2m, gm, hitm)

                if best_local_macro > best_macro_val + 1e-6:
                    best_macro_val = best_local_macro
                    best_W = cand_W.copy()
                    best_T1, best_T2, best_G, best_hit_tr = best_local_tuple
                    W = best_W.copy()
                    improved = True
                    print(f"[IT {it:03d}] 🔬 GA melhorou VALID macro_top{TOPK} -> {best_macro_val:.3%} "
                          f"(T1={best_T1:.3f} T2={best_T2:.3f} γ={best_G:.2f})")

            if improved:
                no_improve = 0
            else:
                no_improve += 1

            print(f"[IT {it:03d}] VALID macro_top{TOPK}={macro_val:.3%} (grid no TREINO)  "
                  f"best={best_macro_val:.3%}  | T1={T1_c:.3f} T2={T2_c:.3f} γ={G_c:.2f}  aciona_TREINO={hit_tr:.1%}")

            if best_macro_val >= TARGET_MACRO_TOPK:
                print("[PARAR] Atingiu meta de macro top-k.")
                break
            if no_improve >= args.early_stop_patience:
                print("[PARAR] Early stop (sem melhora).")
                break

    # projeção final
    W_tuned = project_bounds(best_W, adjustable_mask, W0, EPS_W)

    # ================== APLICA EM TODO O CONJUNTO ==================
    P_all_core = softmax_rows(X_all @ W_tuned)
    P_all_aug, hits_all = add_normal_by_rule(P_all_core, best_T1, best_T2, best_G, st_name=ST_LABEL)

    # métricas finais na VAL (com grid do TREINO)
    P_val_core = softmax_rows(X_val_grid @ W_tuned)
    P_val_aug, _ = add_normal_by_rule(P_val_core, best_T1, best_T2, best_G, st_name=ST_LABEL)
    macro_final_valid = macro_topk(y_val_aug, P_val_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK)

    print(f"[RESULTADO] VALID macro top-{TOPK} (grid no TREINO) = {macro_final_valid:.3%}")
    print(f"[REGRAS] T1={best_T1:.3f}  T2={best_T2:.3f}  γ={best_G:.2f}  aciona_TREINO={best_hit_tr:.1%}")

    # ---------- Saídas em abas ----------
    # 1) Pontuação_Tunada (linhas=classes CORE, colunas=features) — sem ST em W
    df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
    df_pont_tun.insert(0, "Tipo de Transtorno", class_core)

    # 2) Resultado_Heuristica_Tunada — TODO o conjunto (probas + tops), com ST na pós-regra
    df_res = df_all[[df_all.columns[0]]].copy()
    if COL_ALVO in df_all.columns:
        df_res[COL_ALVO] = df_all[COL_ALVO]
    for j, name in enumerate(class_names_aug):
        if j < K0:
            df_res[f"p_{name}"] = P_all_aug[:, j]
        else:
            df_res[f"p_{name}"] = P_all_aug[:, j]  # ST

    order_all = np.argsort(-P_all_aug, axis=1)
    tops_rec = []
    for i in range(P_all_aug.shape[0]):
        rec = {}
        for t in range(min(TOPK, P_all_aug.shape[1])):
            c = order_all[i, t]
            rec[f"top{t+1}_classe"] = class_names_aug[c]
            rec[f"top{t+1}_prob"] = float(P_all_aug[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    # 3) Metricas_Heuristica_Tunada — VALID (agregado e por classe, incluindo ST)
    rows = []
    for c_idx, c_name in enumerate(class_names_aug):
        mask = np.array([c_name in labs for labs in y_val_aug], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, f"top{TOPK}_rate": np.nan, "suporte": 0})
            continue
        ord_c = np.argsort(-P_val_aug[mask], axis=1)[:, :TOPK]
        hits = np.sum([c_idx in ord_c[r] for r in range(ord_c.shape[0])])
        rows.append({"classe": c_name, f"top{TOPK}_rate": hits / sup, "suporte": sup})
    df_met_cls = pd.DataFrame(rows)
    df_met_sum = pd.DataFrame([{
        f"macro_top{TOPK}_VALID": df_met_cls[f"top{TOPK}_rate"].mean(skipna=True),
        "observacao": (f"Macro top-{TOPK} na VALID com pós-regra de '{ST_LABEL}' (T1/T2/γ) ajustada no TREINO; "
                       "W treina apenas classes CORE; ST não aumenta K de W.")
    }])
    df_metricas_tun = pd.concat([
        pd.DataFrame([{"secao": "agregado_VALID", **df_met_sum.iloc[0].to_dict()}]),
        df_met_cls.assign(secao="por_classe_VALID")
    ], ignore_index=True)

    # 4) Regras_Normal
    df_regras = pd.DataFrame([
        {"param": "T1_top1_core_max (ajustado_no_TREINO)", "value": best_T1},
        {"param": "T2_margem_top1_core_top2_core_max (ajustado_no_TREINO)", "value": best_T2},
        {"param": "gamma_para_ST (ajustado_no_TREINO)", "value": best_G},
        {"param": "taxa_acionamento_regra_no_TREINO", "value": best_hit_tr},
        {f"param": f"macro_top{TOPK}_VALID_final", "value": macro_final_valid},
        {"param": "aba_pesos_utilizada", "value": aba_pontos_usada},
    ])

    # 5) Explicacao_Resultados
    df_expl_add = pd.DataFrame([{
        "Aba": ABA_RES_HEUR_TUN,
        "Descricao": (
            "Treino de W nas classes CORE (aba Pontuação), sem coluna ST. "
            f"Rótulos '{ST_LABEL}' do Alvo são usados para ajustar a PÓS-REGRA por baixa ativação/margem, "
            "sem alterar a dimensionalidade de W. Rótulos 'não/nao' são ignorados. "
            "Split 2/3–1/3 por label (CORE+ST) para fins de TREINO/VALIDAÇÃO da pós-regra; "
            "linhas com apenas labels minoritários entram somente no TREINO (para grid). "
            "Seleção do melhor modelo considera macro top-k na VALIDAÇÃO após aplicar a pós-regra."
        )
    }])

    # 6) Comparativo_TopK_Tudo — reusa df_res
    df_comp_tudo = df_res.copy()

    saved_path = save_preserving_sheets(
        OUTPUT,
        [
            (df_pont_tun,     ABA_PONTOS_TUNADA),
            (df_res,          ABA_RES_HEUR_TUN),
            (df_metricas_tun, ABA_MET_HEUR_TUN),
            (df_regras,       ABA_REGRAS_NORMAL),
            (df_expl_add,     ABA_EXPLICAO),
            (df_comp_tudo,    ABA_COMPARATIVO_TUDO),
        ]
    )

    # ---------- relatório JSON ----------
    report = {
        "status": "ok",
        "converged": bool(best_macro_val >= TARGET_MACRO_TOPK - 1e-12),
        "macro_valid": float(macro_final_valid),
        "target_macro": float(TARGET_MACRO_TOPK),
        "best_T1": float(best_T1),
        "best_T2": float(best_T2),
        "best_gamma": float(best_G),
        "hit_rate_train": float(best_hit_tr),
        "seed": int(RANDOM_STATE),
        "grid": {
            "t1_min": float(GRID_T1.min()), "t1_max": float(GRID_T1.max()), "t1_steps": int(len(GRID_T1)),
            "t2_min": float(GRID_T2.min()), "t2_max": float(GRID_T2.max()), "t2_steps": int(len(GRID_T2)),
            "g_min":  float(GRID_G.min()),  "g_max":  float(GRID_G.max()),  "g_steps":  int(len(GRID_G)),
        },
        "lr": float(LR), "l1": float(LAMBDA_L1), "l2": float(LAMBDA_L2),
        "ga": {"num_mutants": int(GA_NUM), "mutate_cols": int(GA_COLS), "mutation_scale": float(GA_SCALE)},
        "checks": int(total_checks),
        "used_sheet": aba_pontos_usada,
        "output_file": saved_path,
        "postrule_on": True,
        "st_in_W": False
    }

    try:
        if REPORT_JSON is None:
            base = os.path.splitext(OUTPUT or INPUT)[0]
            REPORT_JSON = base + "_report.json"
        with open(REPORT_JSON, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas criadas/atualizadas:",
          ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN,
          ABA_REGRAS_NORMAL, ABA_EXPLICAO, ABA_COMPARATIVO_TUDO)
    print(f"💾 Arquivo salvo em: {saved_path}")
    print(f"➡️ VALID macro top-{TOPK} (grid no TREINO) final: {macro_final_valid:.3%}")

# ================== CLI ==================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Heurística com ST apenas na pós-regra: W treina nas classes core; "
                    "ST vem da regra (T1,T2,γ) ajustada no TREINO e avaliada na VALIDAÇÃO."
    )
    # Caminhos e abas
    parser.add_argument("--input", default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx")
    parser.add_argument("--output", default=None)
    parser.add_argument("--sheet-dados", default="TDados_clean")
    parser.add_argument("--sheet-pontos", default="Pontuação")
    parser.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    parser.add_argument("--sheet-resultado-tun", default="Resultado_Heuristica_Tunada")
    parser.add_argument("--sheet-metricas-tun", default="Metricas_Heuristica_Tunada")
    parser.add_argument("--sheet-explicacao", default="Explicacao_Resultados")
    parser.add_argument("--sheet-regras-normal", default="Regras_Normal")
    parser.add_argument("--sheet-comparativo", default="Comparativo_TopK_Tudo")
    parser.add_argument("--prefer-tunada", action="store_true", default=True,
                        help="Se existir 'Pontuação_Tunada', usar como base ao invés de 'Pontuação'. (default: True)")

    # Estrutura Pontuação
    parser.add_argument("--n-classes", type=int, default=11, help="Nº de classes em Pontuação (SEM ST em W)." )
    parser.add_argument("--linha-inicio-pontos", type=int, default=3)
    parser.add_argument("--col-alvo", default="Alvo")

    # Split / métrica
    parser.add_argument("--train-frac", type=float, default=2.0/3.0)
    parser.add_argument("--min-support-val", type=int, default=2)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)

    # Otimização
    parser.add_argument("--l1", type=float, default=1e-3)
    parser.add_argument("--l2", type=float, default=1e-2)
    parser.add_argument("--lr", type=float, default=0.1)
    parser.add_argument("--max-iters", type=int, default=1000)
    parser.add_argument("--check-every", type=int, default=10)
    parser.add_argument("--early-stop-patience", type=int, default=100)
    parser.add_argument("--target-macro-topk", type=float, default=0.99)
    parser.add_argument("--eps-w", type=float, default=1e-6)

    # Pós-regra ST (grid)
    parser.add_argument("--normal-label", default="Sem Transtorno")
    parser.add_argument("--grid-t1-min", type=float, default=0.18)
    parser.add_argument("--grid-t1-max", type=float, default=0.60)
    parser.add_argument("--grid-t1-steps", type=int, default=12)
    parser.add_argument("--grid-t2-min", type=float, default=0.02)
    parser.add_argument("--grid-t2-max", type=float, default=0.20)
    parser.add_argument("--grid-t2-steps", type=int, default=10)
    parser.add_argument("--grid-g-min", type=float, default=0.30)
    parser.add_argument("--grid-g-max", type=float, default=0.75)
    parser.add_argument("--grid-g-steps", type=int, default=10)

    # Variabilidade genética (mutação)
    parser.add_argument("--ga-num-mutants", type=int, default=20, help="Nº de mutantes testados por checagem.")
    parser.add_argument("--ga-mutate-cols", type=int, default=5, help="Qtd de colunas (classes) mutadas por indivíduo.")
    parser.add_argument("--ga-mutation-scale", type=float, default=0.05, help="Desvio padrão do ruído multiplicativo." )

    # Saída JSON
    parser.add_argument("--report-json", default=None, help="Caminho do relatório JSON (para o orquestrador).")

    args = parser.parse_args()
    main(args)
