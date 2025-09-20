import argparse
import os
import sys
from datetime import datetime
import numpy as np
import pandas as pd

def main():
    ap = argparse.ArgumentParser(description="Checagem de intervalo [0,1] por regra de ouro (foco configurável)")
    ap.add_argument("--input", type=str, default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx", help="Arquivo Excel de entrada")
    ap.add_argument("--data-sheet", type=str, default="TDados", help="Aba com dados (features + alvo)")
    ap.add_argument("--score-sheet", type=str, default="Pontuação", help="Aba com pesos/score (regra de ouro)")
    ap.add_argument("--target", type=str, default="Alvo", help="Nome da coluna alvo (será ignorada nas features)")
    ap.add_argument("--allow-nan", action=argparse.BooleanOptionalAction, default=False,
                    help="Se True, NaNs não serão considerados violação")
    ap.add_argument("--mode", type=str, choices=["nonzero","zero","not-in-pontuacao"], default="nonzero",
                    help=("Qual conjunto de features checar: "
                          "'nonzero' = colunas em Pontuação com soma != 0 (padrão); "
                          "'zero' = colunas em Pontuação com soma == 0; "
                          "'not-in-pontuacao' = colunas numéricas de TDados que não aparecem em Pontuação."))
    ap.add_argument("--out", type=str, default=None, help="Arquivo Excel para salvar o relatório")
    args = ap.parse_args()

    # --- load
    if not os.path.isfile(args.input):
        print(f"[ERRO] Arquivo não encontrado: {args.input}")
        sys.exit(1)

    try:
        xls = pd.ExcelFile(args.input)
    except Exception as e:
        print(f"[ERRO] Falha ao abrir Excel: {e}")
        sys.exit(1)

    if args.data_sheet not in xls.sheet_names:
        print(f"[ERRO] Aba '{args.data_sheet}' não encontrada. Abas: {xls.sheet_names}")
        sys.exit(1)
    if args.score_sheet not in xls.sheet_names:
        print(f"[ERRO] Aba '{args.score_sheet}' não encontrada. Abas: {xls.sheet_names}")
        sys.exit(1)

    df = pd.read_excel(args.input, sheet_name=args.data_sheet)
    pont = pd.read_excel(args.input, sheet_name=args.score_sheet)

    # --- numeric set (excluding target)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if args.target in numeric_cols:
        numeric_cols.remove(args.target)

    # --- intersect with Pontuação
    common = [c for c in pont.columns if c in numeric_cols and c != args.target]

    # --- compute groups according to golden rule
    in_pont_nonzero = []
    in_pont_zero = []
    for c in common:
        s = pd.to_numeric(pont[c], errors="coerce").fillna(0.0)
        if float(s.abs().sum()) == 0.0:
            in_pont_zero.append(c)
        else:
            in_pont_nonzero.append(c)
    not_in_pont = [c for c in numeric_cols if c not in common]

    # --- choose focus set
    if args.mode == "nonzero":
        features_to_check = in_pont_nonzero
        desc = "presentes em Pontuação e COM soma != 0 (fora da condição de todos zeros)"
    elif args.mode == "zero":
        features_to_check = in_pont_zero
        desc = "presentes em Pontuação e COM soma == 0 (as que a regra de ouro excluiria)"
    else:  # not-in-pontuacao
        features_to_check = not_in_pont
        desc = "numéricas em TDados que NÃO aparecem na aba Pontuação"

    if not features_to_check:
        print(f"[OK] Não há features a checar no modo '{args.mode}' ({desc}).")
        sys.exit(0)

    print(f"[INFO] Modo: {args.mode} — checando {len(features_to_check)} features ({desc}).")

    # --- coerce TDados numeric for those features
    df_num = df.copy()
    for c in features_to_check:
        df_num[c] = pd.to_numeric(df_num[c], errors="coerce")

    # --- check for violations in [0,1]
    violations = []
    for c in features_to_check:
        col = df_num[c]
        mask_nan = col.isna()
        mask_inf_pos = col==np.inf
        mask_inf_neg = col==-np.inf
        mask_lt0 = col < 0
        mask_gt1 = col > 1

        if args.allow_nan:
            mask_any = mask_inf_pos | mask_inf_neg | mask_lt0 | mask_gt1
        else:
            mask_any = mask_nan | mask_inf_pos | mask_inf_neg | mask_lt0 | mask_gt1

        idxs = np.where(mask_any.values)[0]
        for i in idxs:
            val = col.iloc[i]
            issue = []
            if not args.allow_nan and pd.isna(val): issue.append("nan")
            if val is not None and val==np.inf: issue.append("posinf")
            if val is not None and val==-np.inf: issue.append("neginf")
            try:
                if float(val) < 0: issue.append("lt0")
                if float(val) > 1: issue.append("gt1")
            except Exception:
                pass
            if not issue:
                issue = ["viol"]
            excel_row = i + 2  # header + 1-based
            violations.append({
                "feature": c,
                "row_idx": i,
                "excel_row": excel_row,
                "value": val,
                "issue": ",".join(issue)
            })

    # --- report & output
    if not violations:
        print("[OK] Nenhuma violação de intervalo [0,1] encontrada "
              f"nas features selecionadas ({len(features_to_check)} checadas).")
        sys.exit(0)

    vdf = pd.DataFrame(violations).sort_values(["feature","excel_row"]).reset_index(drop=True)

    # Console summary
    print(f"[ALERTA] {len(vdf)} violações em {vdf['feature'].nunique()} feature(s). Exibindo até 20:")
    print(vdf.head(20).to_string(index=False))

    counts = vdf.groupby("feature").size().sort_values(ascending=False)

    # Excel output
    out_path = args.out
    if out_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"golden_focus_{args.mode}_check_{ts}.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        vdf.to_excel(writer, index=False, sheet_name="VIOLATIONS")
        counts.rename("violations").to_frame().to_excel(writer, sheet_name="SUMMARY")
        pd.DataFrame({"features_checked": features_to_check}).to_excel(writer, index=False, sheet_name="FEATURES_CHECKED")
        # contexto do conjunto
        ctx = pd.DataFrame({
            "group": ["in_pont_nonzero","in_pont_zero","not_in_pont"],
            "count": [len(in_pont_nonzero), len(in_pont_zero), len(not_in_pont)]
        })
        ctx.to_excel(writer, index=False, sheet_name="CONTEXT")

    print(f"[INFO] Relatório salvo em: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    main()