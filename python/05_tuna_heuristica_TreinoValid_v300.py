# -*- coding: utf-8 -*-
"""
05_tuna_heuristica_TreinoValid.py (v2.9.5 - versão sem 'Sem Transtorno')
- Remove toda a lógica e parâmetros específicos da classe "Sem Transtorno" (ST).
- Mantém: tuning com softmax puro, L1/L2, proximal step, snapshots, mutações evolutivas (ON por padrão),
  abas "Pontuação_Tunada", "Resultado_Heuristica_Tunada", "Metricas_Heuristica_Tunada",
  "Regras_Normal", "Explicacao_Resultados", "Diagnostico_SUM", "Comparativo_TopK_Tudo".
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

def project_bounds(W, adjustable_mask, W0, eps=1.0):
    Wp = W.copy()
    Wp[~adjustable_mask] = W0[~adjustable_mask]
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

def macro_topk_pair(y_train, Xb_train, y_val, Xb_val, Wmat, class_to_idx, idx_to_class, k):
    P_tr = forward(Wmat, Xb_train)
    P_va = forward(Wmat, Xb_val)
    m_tr = macro_topk(y_train, P_tr, class_to_idx, idx_to_class, k=k)
    m_va = macro_topk(y_val,   P_va, class_to_idx, idx_to_class, k=k)
    return m_tr, m_va

def fmt_pair(label, tr, va):
    return f"{label}(TR/VA)=({tr:.3%}/{va:.3%})"

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

    # Split por suporte mínimo no VALID
    suportes = {c: sum((c in labs) for labs in y_lists_all) for c in class_names}
    eligible_labels = {c for c,s in suportes.items() if s >= args.min_support_val}
    minor_labels = set(class_names) - eligible_labels

    has_eligible = np.array([any(c in eligible_labels for c in l) for l in y_lists_all], bool)
    has_only_minor= np.array([all(c in minor_labels for c in l) for l in y_lists_all], bool)

    idx_tv_pool = np.where(has_eligible)[0]
    idx_minor_train_for_grid = np.where(has_only_minor)[0]

    rng = np.random.default_rng(RANDOM_STATE)
    y_tv = [y_lists_all[i] for i in idx_tv_pool]
    targets_train = {c: int(np.floor(args.train_frac * sum(c in labs for labs in y_tv))) for c in eligible_labels}
    counts_train = {c: 0 for c in eligible_labels}

    n_tv = len(y_tv)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)
    assign_train_local = np.zeros(n_tv, bool); assign_val_local = np.zeros(n_tv, bool)

    for i in order_idx:
        labs = [c for c in y_tv[i] if c in eligible_labels]
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

    # Alvos treino
    y_train = [y_lists_all[i] for i in idx_train]
    y_val   = [y_lists_all[i] for i in idx_val]
    Kc = len(class_names)
    Y_train = y_distribution(y_train, class_to_idx, Kc)

    # ---------- REGRA DE OURO ----------
    mask_w_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)  # (features,)
    W0_eff_core = W0_sheet.copy()
    W0_eff_core[~mask_w_all_zero, :] = np.clip(W0_eff_core[~mask_w_all_zero, :], 1.0, 1.0)

    # Parâmetros iniciais com bias
    W0 = np.zeros((m+1, Kc), dtype=float)
    W0[:m, :Kc] = W0_eff_core
    W0[m, :Kc]  = 0.0  # bias inicial zero para todas as classes

    adjustable = np.zeros_like(W0, dtype=bool)
    adjustable[:m, :Kc] = ~mask_w_all_zero[:, None]
    adjustable[m, :Kc]  = True  # sempre permitir ajustar bias das classes do core

    W = W0.copy()

    # Matrizes com bias
    Xb_all = with_bias(X_all)
    Xb_val = with_bias(X_all[idx_val])
    Xb_train = with_bias(X_all[idx_train])
    Xb_all_full = with_bias(X_all_full)

    # --------- Funções de perda e avaliação ---------
    def loss_with_regularizers(Wmat):
        # Cross-entropy média (multi-label via distribuição Y_train)
        P = forward(Wmat, Xb_train)
        eps = 1e-12
        ce = -np.mean(np.sum(Y_train * np.log(P + eps), axis=1))
        # L2 sobre deslocamento em relação a W0
        l2 = L2 * np.sum((Wmat - W0)**2)
        # L1 proximal já no step, mas somamos um termo leve para logging (opcional)
        l1 = L1 * np.sum(np.abs(Wmat - W0))
        return ce + l2 + 0.0*l1, ce, l2

    def objective_valid(Wmat):
        m_tr, m_va = macro_topk_pair(y_train, Xb_train, y_val, Xb_val, Wmat, class_to_idx, idx_to_class, k=TOPK)
        return m_tr, m_va

    # Baseline
    tr0, va0 = objective_valid(W)
    print("[BASE] " + fmt_pair(f"macro_top{TOPK}", tr0, va0))
    print(f"[INFO] tamanhos (TR/VA)=({Xb_train.shape[0]}/{Xb_val.shape[0]})")
    print(f"[ALVO] meta para parar: TR>= {TARGET_MACRO_TOPK:.0%}")

    best_score_va = va0; best_score_tr = tr0; best_W = W.copy()
    best_score_mix = 0.5*(tr0 + va0)
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

        # Mutações periódicas (greedy) -- default ON
        if args.mutations and (it % args.mutation_every == 0):
            improved_local = False
            base_tr, base_va = objective_valid(W)
            for _try in range(args.mutation_max_tries):
                W_mut = W.copy()
                noise = rng_mut.normal(loc=0.0, scale=args.mutation_sigma, size=W_mut.shape)
                noise[~adjustable] = 0.0
                W_mut += noise
                W_mut = project_bounds(W_mut, adjustable, W0, 1.0)
                tr_mut, va_mut = objective_valid(W_mut)
                if tr_mut > base_tr + 1e-9:
                    W = W_mut
                    base_tr, base_va = tr_mut, va_mut
                    improved_local = True
            if improved_local:
                print(f"[MUT] melhoria aceita no it={it}: " + fmt_pair("obj_VALID", base_tr, base_va))

        # Checagem
        if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
            total_checks += 1
            cur_tr, cur_va = objective_valid(W)

            improved = False
            cur_mix = 0.5*(cur_tr + cur_va)
            if cur_mix > best_score_mix + 1e-6:
                best_score_mix = cur_mix; best_score_va = cur_va; best_score_tr = cur_tr; best_W = W.copy(); improved = True

            diag_rows.append({
                "iter": it,
                f"macro_top{TOPK}_TR": cur_tr,
                f"macro_top{TOPK}_VA": cur_va,
                "improved": improved
            })

            print(f"[IT {it:05d}] " + fmt_pair(f"macro_top{TOPK}", cur_tr, cur_va) + "  " + fmt_pair("best", best_score_tr, best_score_va))

            if best_score_tr >= TARGET_MACRO_TOPK:
                print("[PARAR] Atingiu meta no TREINO."); break

            if not improved:
                if len(diag_rows) > args.early_stop_patience:
                    recent_mix = [0.5*(r[f"macro_top{TOPK}_TR"] + r[f"macro_top{TOPK}_VA"]) for r in diag_rows[-args.early_stop_patience:]]
                    if max(recent_mix) <= best_score_mix + 1e-6:
                        print("[PARAR] Early stop (sem melhora no mix TR/VA)."); break

    # ---------- Final ----------
    W_tuned = project_bounds(best_W, adjustable, W0, 1.0)
    P_all = forward(W_tuned, Xb_all)
    P_all_full = forward(W_tuned, Xb_all_full)

    # TR/VA detalhado
    P_tr_final = forward(W_tuned, Xb_train)
    P_val_final = forward(W_tuned, Xb_val)
    macro_final_train_k1 = macro_topk(y_train, P_tr_final, class_to_idx, idx_to_class, k=1)
    macro_final_valid_k1 = macro_topk(y_val,   P_val_final, class_to_idx, idx_to_class, k=1)
    macro_final_train_k2 = macro_topk(y_train, P_tr_final, class_to_idx, idx_to_class, k=2)
    macro_final_valid_k2 = macro_topk(y_val,   P_val_final, class_to_idx, idx_to_class, k=2)
    macro_final_train_k3 = macro_topk(y_train, P_tr_final, class_to_idx, idx_to_class, k=3)
    macro_final_valid_k3 = macro_topk(y_val,   P_val_final, class_to_idx, idx_to_class, k=3)

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

    # Métricas por classe no VALID (topk escolhido)
    rows = []
    for c_idx, c_name in enumerate(class_names):
        mask_tr = np.array([c_name in labs for labs in y_train], bool)
        sup_tr = int(mask_tr.sum())
        rate_tr = np.nan; hits_tr = 0
        if sup_tr > 0:
            ord_tr = np.argsort(-P_tr_final[mask_tr], axis=1)[:, :TOPK]
            hits_tr = sum(c_idx in ord_tr[r] for r in range(ord_tr.shape[0]))
            rate_tr = hits_tr / sup_tr
        mask_va = np.array([c_name in labs for labs in y_val], bool)
        sup_va = int(mask_va.sum())
        rate_va = np.nan; hits_va = 0
        if sup_va > 0:
            ord_va = np.argsort(-P_val_final[mask_va], axis=1)[:, :TOPK]
            hits_va = sum(c_idx in ord_va[r] for r in range(ord_va.shape[0]))
            rate_va = hits_va / sup_va
        rows.append({
            "classe": c_name,
            f"top{TOPK}_rate(TR/VA)": f"({rate_tr if not np.isnan(rate_tr) else 'nan'}/{rate_va if not np.isnan(rate_va) else 'nan'})",
            f"acertos_topk(TR/VA)": f"({hits_tr}/{hits_va})",
            f"suporte(TR/VA)": f"({sup_tr}/{sup_va})"
        })
    df_met_cls = pd.DataFrame(rows)

    df_met_sum = pd.DataFrame([{
        f"macro_top1(TR/VA)": f"({macro_final_train_k1:.3%}/{macro_final_valid_k1:.3%})",
        f"macro_top2(TR/VA)": f"({macro_final_train_k2:.3%}/{macro_final_valid_k2:.3%})",
        f"macro_top3(TR/VA)": f"({macro_final_train_k3:.3%}/{macro_final_valid_k3:.3%})",
        f"macro_top{TOPK}(TR/VA)": df_met_cls[f"top{TOPK}_rate(TR/VA)"].mean(skipna=True) if False else f"(n/a/n/a)",
        "observacao": "Softmax puro; mutações ON; Comparativo_TopK_Tudo no TDados completo."
    }])

    df_metricas_tun = pd.concat([pd.DataFrame([{"secao":"agregado", **df_met_sum.iloc[0].to_dict()}]),
                                 df_met_cls.assign(secao="por_classe")], ignore_index=True)

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

    report = {"status":"ok",
              "macro_train_top1": float(macro_final_train_k1),
              "macro_valid_top1": float(macro_final_valid_k1),
              "macro_train_top2": float(macro_final_train_k2),
              "macro_valid_top2": float(macro_final_valid_k2),
              "macro_train_top3": float(macro_final_train_k3),
              "macro_valid_top3": float(macro_final_valid_k3),
              "seed": int(RANDOM_STATE),
              "lr": float(LR), "l1": float(L1), "l2": float(L2),
              "checks": int(total_checks), "used_sheet": aba_pontos_usada, "output_file": saved_path,
              "postrule": "none_softmax_core_only", "n_jobs": int(N_JOBS),
              "mutations": bool(args.mutations)}
    try:
        base = os.path.splitext(OUTPUT or INPUT)[0]
        rep_path = args.report_json or base + "_report.json"
        with open(rep_path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
        print("__REPORT_JSON__=" + json.dumps(report, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] Falha ao escrever relatório JSON: {e}", file=sys.stderr)

    print("✅ Abas atualizadas:", ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_DIAG, ABA_COMPARATIVO_TUDO)
    print(f"💾 Arquivo salvo em: {saved_path}")
    print("➡️ " + fmt_pair("macro_top1", macro_final_train_k1, macro_final_valid_k1) + " | " + fmt_pair("macro_top2", macro_final_train_k2, macro_final_valid_k2) + " | " + fmt_pair("macro_top3", macro_final_train_k3, macro_final_valid_k3))

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Treino/validação com softmax puro e mutações evolutivas; versão sem 'Sem Transtorno'.")
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
    p.add_argument("--train-frac", type=float, default=2.0/3.0)
    p.add_argument("--min-support-val", type=int, default=2)
    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--l1", type=float, default=0.0025)
    p.add_argument("--l2", type=float, default=0.02)
    p.add_argument("--lr", type=float, default=0.02)
    p.add_argument("--max-iters", type=int, default=10000)
    p.add_argument("--check-every", type=int, default=50)
    p.add_argument("--early-stop-patience", type=int, default=1000)
    p.add_argument("--target-macro-topk", type=float, default=0.99)
    # Mutações (ligadas por padrão)
    p.add_argument("--mutations", action="store_true", default=True, help="Habilita mutações evolutivas (ruído Gaussiano + aceitação gulosa).")
    p.add_argument("--mutation-every", type=int, default=1, help="Intervalo de iterações entre tentativas de mutação.")
    p.add_argument("--mutation-sigma", type=float, default=0.1, help="Desvio padrão do ruído Gaussiano aplicado aos parâmetros.")
    p.add_argument("--mutation-max-tries", type=int, default=20, help="Número de tentativas por rodada de mutação.")
    p.add_argument("--report-json", default="report.json")
    p.add_argument("--n-jobs", type=int, default=os.cpu_count())
    p.add_argument("--blas-threads", type=int, default=1)
    args = p.parse_args(); np.random.seed(args.seed); main(args)