# auto_tuner.py
# Busca rápida (grid) pelos parâmetros (T1, T2, gamma) usando
# a mesma leitura/semântica do 05_tuna_heuristica_TreinoValid.py.

import os, sys, argparse, time
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importa utilidades do seu script 05 (que você já tem na pasta python)
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
FILE_05 = os.path.join(HERE, "05_tuna_heuristica_TreinoValid.py")

spec = importlib.util.spec_from_file_location("tuna05", FILE_05)
tuna05 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tuna05)

softmax_rows = tuna05.softmax_rows
parse_multilabel = tuna05.parse_multilabel
macro_topk = tuna05.macro_topk

# ====== Avaliador real: lê o Excel e prepara tudo ======
def build_real_evaluator(
    input_path,
    sheet_dados="TDados_clean",
    sheet_pontos="Pontuação",
    sheet_pontos_tunada="Pontuação_Tunada",
    normal_label="Sem Transtorno",
    col_alvo="Alvo",
    n_classes=11,
    linha_inicio_pontos=3,
    topk=3,
    train_frac=2.0/3.0,
    min_support_val=2,
    seed=42,
    st_truth_mode="exclusive",
):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_path}")

    # Lê dados
    df_all = pd.read_excel(input_path, sheet_name=sheet_dados)
    xl = pd.ExcelFile(input_path)
    usar_tunada = (sheet_pontos_tunada in xl.sheet_names)
    aba_pontos = sheet_pontos_tunada if usar_tunada else sheet_pontos
    df_pont = pd.read_excel(input_path, sheet_name=aba_pontos)

    # Colunas de dados = tudo a partir da coluna B, exatamente igual ao 05
    cols_dados = df_all.columns[1:]
    if len(cols_dados) == 0:
        raise ValueError(f"{sheet_dados} não possui colunas a partir da coluna B.")

    X_all = df_all[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    X_all = np.clip(np.nan_to_num(X_all, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)

    # Lê bloco de pesos da aba Pontuação/Pontuação_Tunada
    r0 = linha_inicio_pontos - 2             # linha “visual” 3 => índice 1
    linhas_modelos = df_pont.index[r0 : r0 + n_classes]
    if len(linhas_modelos) != n_classes:
        raise ValueError(
            f"Aba '{aba_pontos}' não tem {n_classes} linhas a partir da linha {linha_inicio_pontos}."
        )

    faltantes = [c for c in cols_dados if c not in df_pont.columns]
    if faltantes:
        raise ValueError(
            f"Colunas de {sheet_dados} ausentes em '{aba_pontos}': "
            f"{faltantes[:10]}{'...' if len(faltantes)>10 else ''}"
        )

    W_block = df_pont.loc[linhas_modelos, cols_dados]
    W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
    if W0.shape[1] != n_classes:
        raise ValueError(f"Dimensão inesperada de W core: {W0.shape}, esperado K0={n_classes}.")
    class_core = (
        df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
        if "Tipo de Transtorno" in df_pont.columns
        else [f"Classe_{i+1}" for i in range(n_classes)]
    )

    # Alvos multilabel a partir da coluna 'Alvo'
    y_lists_all = parse_multilabel(df_all[col_alvo], class_core, normal_label=normal_label)

    # Remove linhas sem nenhum rótulo válido
    keep = [len(l) > 0 for l in y_lists_all]
    X_all = X_all[keep]
    y_lists_all = [l for l, k in zip(y_lists_all, keep) if k]

    # Construções auxiliares (iguais ao 05)
    class_names_aug = class_core + [normal_label]
    suportes_aug = {c: sum(c in labs for labs in y_lists_all) for c in class_names_aug}
    eligible_labels_aug = {c for c, s in suportes_aug.items() if s >= min_support_val}
    minor_labels_aug = set(class_names_aug) - eligible_labels_aug

    has_eligible_aug = np.array([any(c in eligible_labels_aug for c in l) for l in y_lists_all], bool)
    has_only_minor_aug = np.array([all(c in minor_labels_aug for c in l) for l in y_lists_all], bool)

    idx_tv_pool = np.where(has_eligible_aug)[0]
    idx_minor_train_for_grid = np.where(has_only_minor_aug)[0]

    rng = np.random.default_rng(seed)
    y_tv_aug = [y_lists_all[i] for i in idx_tv_pool]

    # Split equilibrado por classe elegível
    targets_train = {c: int(np.floor(train_frac * sum(c in labs for labs in y_tv_aug))) for c in eligible_labels_aug}
    counts_train = {c: 0 for c in eligible_labels_aug}

    n_tv = len(y_tv_aug)
    order_idx = np.arange(n_tv); rng.shuffle(order_idx)
    assign_train = np.zeros(n_tv, bool); assign_val = np.zeros(n_tv, bool)

    for pos in order_idx:
        labs = y_tv_aug[pos]
        # prefere mandar para treino até bater as metas
        if any(counts_train.get(c, 0) < targets_train.get(c, 0) for c in labs if c in eligible_labels_aug):
            assign_train[pos] = True
            for c in labs:
                if c in eligible_labels_aug:
                    counts_train[c] = counts_train.get(c, 0) + 1
        else:
            assign_val[pos] = True

    idx_train_bal = np.array([idx_tv_pool[i] for i in np.where(assign_train)[0]], int)
    idx_val_bal   = np.array([idx_tv_pool[i] for i in np.where(assign_val)[0]], int)

    # Observações “apenas minor” entram no treino do grid
    idx_train_grid = np.concatenate([idx_train_bal, idx_minor_train_for_grid], axis=0)
    idx_val_grid   = idx_val_bal

    # Matrizes finais do grid
    X_train_grid = X_all[idx_train_grid]
    X_val_grid   = X_all[idx_val_grid]
    y_train_aug  = [y_lists_all[i] for i in idx_train_grid]
    y_val_aug    = [y_lists_all[i] for i in idx_val_grid]

    class_to_idx_aug = {c: i for i, c in enumerate(class_names_aug)}
    idx_to_class_aug = {i: c for c, i in class_to_idx_aug.items()}

    # Probabilidades CORE (antes da regra ST)
    def core_proba(X, W):
        return softmax_rows(X @ W)

    # Função de avaliação de um trio (T1,T2,gamma)
    def evaluate_triple(T1, T2, G):
        # Aplica regra ST da mesma forma do 05 — reimplementação mínima
        # Para ST, você quer: se p1 >= T1 e (p1 - p2) >= T2 e p1 >= G então vira "Sem Transtorno".
        # No 05 isso é feito por add_normal_by_rule; aqui faremos de forma equivalente.
        P_val_core = core_proba(X_val_grid, W0)

        # encontra top1/top2 no CORE
        order = np.argsort(-P_val_core, axis=1)
        top1 = order[:, 0]
        top2 = order[:, 1] if P_val_core.shape[1] > 1 else np.zeros(len(order), int)
        p1   = P_val_core[np.arange(P_val_core.shape[0]), top1]
        p2   = P_val_core[np.arange(P_val_core.shape[0]), top2]
        margin = p1 - p2

        # monta prob. aumentada (CORE + ST)
        K0 = P_val_core.shape[1]
        K  = K0 + 1  # + ST
        P_aug = np.zeros((P_val_core.shape[0], K), dtype=float)
        P_aug[:, :K0] = P_val_core

        # regra ST
        hits_st = (p1 >= T1) & (margin >= T2) & (p1 >= G)
        # transfere massa para ST quando regra aciona
        P_aug[hits_st, :K0] = 0.0
        P_aug[hits_st, K0]  = 1.0

        macro_val = macro_topk(
            y_val_aug, P_aug, class_to_idx_aug, idx_to_class_aug, k=topk,
            st_truth_mode=st_truth_mode, st_label=normal_label
        )
        acionamento = float(hits_st.mean())
        return macro_val, acionamento

    return {
        "evaluate_triple": evaluate_triple,
        "class_names_aug": class_core + [normal_label],
        "info": {
            "sheet_usada": aba_pontos,
            "n_train": int(len(y_train_aug)),
            "n_valid": int(len(y_val_aug)),
            "cols_dados": list(map(str, cols_dados)),
        }
    }


def run_grid(evaluator, grid_t1, grid_t2, grid_g, n_jobs=8):
    eval_fn = evaluator["evaluate_triple"]

    def job(T1, T2, G):
        macro, hit = eval_fn(T1, T2, G)
        return (macro, hit, T1, T2, G)

    futs = []
    best = None
    total = len(grid_t1) * len(grid_t2) * len(grid_g)
    print(f"[INFO] Rodando malha inicial: {total} pontos; n_jobs={n_jobs}")

    with ThreadPoolExecutor(max_workers=max(1, int(n_jobs))) as ex:
        for T1 in grid_t1:
            for T2 in grid_t2:
                for G in grid_g:
                    futs.append(ex.submit(job, float(T1), float(T2), float(G)))

        for fut in as_completed(futs):
            macro, hit, T1, T2, G = fut.result()
            if (best is None) or (macro > best[0] + 1e-12):
                best = (macro, hit, T1, T2, G)

    m, h, T1b, T2b, Gb = best
    print(f"[BEST] VAL={m:.3%}  T1={T1b:.3f}  T2={T2b:.3f}  γ={Gb:.3f}")
    return best


def main():
    p = argparse.ArgumentParser(description="Auto-tuner simples para (T1, T2, γ) com leitura igual ao 05.")
    p.add_argument("--input", default=r"c:\SourceCode\qip\python\banco_dados.xlsx")
    p.add_argument("--sheet-dados", default="TDados_clean")
    p.add_argument("--sheet-pontos", default="Pontuação")
    p.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    p.add_argument("--col-alvo", default="Alvo")
    p.add_argument("--normal-label", default="Sem Transtorno")
    p.add_argument("--n-classes", type=int, default=11)
    p.add_argument("--linha-inicio-pontos", type=int, default=3)
    p.add_argument("--topk", type=int, default=3)
    p.add_argument("--train-frac", type=float, default=2.0/3.0)
    p.add_argument("--min-support-val", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--st-truth-mode", choices=["exclusive", "contains"], default="exclusive")

    # grade padrão igual (aprox) ao 05
    p.add_argument("--t1-min", type=float, default=0.15)
    p.add_argument("--t1-max", type=float, default=0.65)
    p.add_argument("--t1-steps", type=int, default=12)
    p.add_argument("--t2-min", type=float, default=0.01)
    p.add_argument("--t2-max", type=float, default=0.25)
    p.add_argument("--t2-steps", type=int, default=10)
    p.add_argument("--g-min",  type=float, default=0.25)
    p.add_argument("--g-max",  type=float, default=0.80)
    p.add_argument("--g-steps", type=int, default=12)

    p.add_argument("--n-jobs", type=int, default=os.cpu_count())

    args = p.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Monta avaliador real
    evaluator = build_real_evaluator(
        input_path=args.input,
        sheet_dados=args.sheet_dados,
        sheet_pontos=args.sheet_pontos,
        sheet_pontos_tunada=args.sheet_pontos_tunada,
        normal_label=args.normal_label,
        col_alvo=args.col_alvo,
        n_classes=args.n_classes,
        linha_inicio_pontos=args.linha_inicio_pontos,
        topk=args.topk,
        train_frac=args.train_frac,
        min_support_val=args.min_support_val,
        seed=args.seed,
        st_truth_mode=args.st_truth_mode,
    )

    # Gera grades
    GRID_T1 = np.linspace(args.t1_min, args.t1_max, args.t1_steps)
    GRID_T2 = np.linspace(args.t2_min, args.t2_max, args.t2_steps)
    GRID_G  = np.linspace(args.g_min,  args.g_max,  args.g_steps)

    # Roda grid
    run_grid(evaluator, GRID_T1, GRID_T2, GRID_G, n_jobs=args.n_jobs)


if __name__ == "__main__":
    main()
