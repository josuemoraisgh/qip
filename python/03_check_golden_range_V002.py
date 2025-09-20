
import argparse
import os
import sys
from datetime import datetime
import numpy as np
import pandas as pd

def main():
    ap = argparse.ArgumentParser(description="Checa se colunas são binárias (0/1) OU inteiras em [0,10]; reporta as que NÃO atendem")
    ap.add_argument("--input", type=str, default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx", help="Arquivo Excel de entrada")
    ap.add_argument("--data-sheet", type=str, default="TDados", help="Aba com dados (features + alvo)")
    ap.add_argument("--score-sheet", type=str, default="Pontuação", help="Aba com pesos/score (regra de ouro)")
    ap.add_argument("--target", type=str, default="Alvo", help="Nome da coluna alvo (será ignorada nas features)")
    ap.add_argument("--allow-nan", action=argparse.BooleanOptionalAction, default=True,
                    help="Se True (padrão), NaNs NÃO contam como violação.")
    ap.add_argument("--mode", type=str, choices=["nonzero","zero","not-in-pontuacao"], default="nonzero",
                    help=("Quais features checar: "
                          "'nonzero' = colunas em Pontuação com soma != 0 (padrão); "
                          "'zero' = colunas em Pontuação com soma == 0; "
                          "'not-in-pontuacao' = colunas numéricas de TDados que não aparecem em Pontuação."))
    ap.add_argument("--out", type=str, default=None, help="Arquivo Excel de relatório (opcional)")
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

    # --- groups per "regra de ouro"
    in_pont_nonzero, in_pont_zero = [], []
    for c in common:
        s = pd.to_numeric(pont[c], errors="coerce").fillna(0.0)
        if float(s.abs().sum()) == 0.0:
            in_pont_zero.append(c)
        else:
            in_pont_nonzero.append(c)
    not_in_pont = [c for c in numeric_cols if c not in common]

    # --- pick features to check
    if args.mode == "nonzero":
        features_to_check = in_pont_nonzero
        desc = "presentes em Pontuação (soma != 0)"
    elif args.mode == "zero":
        features_to_check = in_pont_zero
        desc = "presentes em Pontuação (soma == 0)"
    else:
        features_to_check = not_in_pont
        desc = "numéricas em TDados que NÃO estão na Pontuação"

    if not features_to_check:
        print(f"[OK] Não há features para checar no modo '{args.mode}' ({desc}).")
        sys.exit(0)

    print(f"[INFO] Modo: {args.mode} — checando {len(features_to_check)} features ({desc}).")

    # --- Cast para numérico nas features alvo
    df_num = df.copy()
    for c in features_to_check:
        df_num[c] = pd.to_numeric(df_num[c], errors="coerce")

    def classify_and_viol_mask(col: pd.Series, allow_nan: bool):
        """Retorna: tipo_detectado ('binary'|'smallint_0_10'|'real/mixed'), mask_violation (bool array), motivo_per_row (str array)."""
        v = col.values.astype(float)  # pode ser nan/inf
        is_nan = np.isnan(v)
        is_inf_pos = np.isposinf(v)
        is_inf_neg = np.isneginf(v)
        is_finite = np.isfinite(v)

        # valores finitos
        vf = v[is_finite]

        # 1) Binária?
        non_bin_mask = np.zeros_like(v, dtype=bool)
        if vf.size > 0:
            non_bin_f = (vf != 0.0) & (vf != 1.0)
            non_bin_mask[is_finite] = non_bin_f
        is_binary = not np.any(non_bin_mask[is_finite])

        # 2) Inteiro em [0,10]?
        not_int_mask = np.zeros_like(v, dtype=bool)
        out_range_mask = np.zeros_like(v, dtype=bool)
        if vf.size > 0:
            is_int_f = np.isclose(vf, np.round(vf))
            in_range_f = (vf >= 0.0) & (vf <= 10.0)
            not_int_mask[is_finite] = ~is_int_f
            out_range_mask[is_finite] = ~in_range_f
        is_smallint = not np.any((not_int_mask | out_range_mask)[is_finite])

        # tipo detectado
        if is_binary:
            dtype = "binary"
        elif is_smallint:
            dtype = "smallint_0_10"
        else:
            dtype = "real/mixed"

        # mask de violação: se for binary, nenhum finito pode fugir de {0,1};
        # se for smallint, nenhum finito pode ser não-inteiro OU fora de [0,10].
        # se allow_nan=False, NaN contam como violação.
        if dtype == "binary":
            viol = non_bin_mask.copy()
            reason = np.where(non_bin_mask, "not_binary", "")
        elif dtype == "smallint_0_10":
            viol = (not_int_mask | out_range_mask)
            reason = np.where(not_int_mask & out_range_mask, "not_int,out_of_0_10",
                     np.where(not_int_mask, "not_int",
                     np.where(out_range_mask, "out_of_0_10", "")))
        else:
            # 'real/mixed' => tudo que não é (binário OU int0..10) é violação nos finitos
            viol = np.zeros_like(v, dtype=bool)
            # marca violação para todos finitos
            viol[is_finite] = True
            reason = np.where(viol, "not_binary_nor_int0_10", "")

        if not allow_nan:
            viol = viol | is_nan
            reason = np.where(is_nan, (reason.astype(object) + ("," if (reason != "").any() else "") + "nan").astype(str), reason)

        # marca infs sempre como violação
        any_inf = is_inf_pos | is_inf_neg
        viol = viol | any_inf
        reason = np.where(is_inf_pos, (reason.astype(object) + ("," if (reason != "").any() else "") + "posinf").astype(str), reason)
        reason = np.where(is_inf_neg, (reason.astype(object) + ("," if (reason != "").any() else "") + "neginf").astype(str), reason)

        # limpa prefixos de vírgula eventuais
        reason = np.where((reason != "") & np.char.startswith(reason.astype(str), ","), np.char.lstrip(reason.astype(str), ","), reason)
        return dtype, viol, reason

    violations = []
    col_summary = []  # por coluna

    for c in features_to_check:
        dtype, viol_mask, reason = classify_and_viol_mask(df_num[c], args.allow_nan)
        fin = np.isfinite(df_num[c].values)
        is_ok_binary = (dtype == "binary")
        is_ok_smallint = (dtype == "smallint_0_10")
        # se não é binary nem smallint -> coluna problemática
        is_bad_col = not (is_ok_binary or is_ok_smallint)

        # resumo por coluna
        col_summary.append({
            "feature": c,
            "detected_type": dtype,
            "n_rows": int(len(df_num[c])),
            "n_violations": int(viol_mask.sum()),
            "is_ok": (not is_bad_col) and (viol_mask.sum() == 0)
        })

        # detalhamento por linha para as que têm violação
        idxs = np.where(viol_mask)[0]
        for i in idxs:
            val = df_num[c].iloc[i]
            excel_row = i + 2  # header + 1-based
            violations.append({
                "feature": c,
                "excel_row": excel_row,
                "value": val,
                "issue": reason[i] if isinstance(reason[i], (str, np.str_)) else str(reason[i])
            })

    # Filtra lista de colunas que NÃO são binárias nem int0..10
    bad_cols = [r["feature"] for r in col_summary if r["detected_type"] == "real/mixed"]

    if not bad_cols:
        print("[OK] Todas as features checadas são binárias (0/1) ou inteiras em [0,10].")
    else:
        print("[ALERTA] Colunas que NÃO são binárias nem inteiras em [0,10]:")
        for name in bad_cols:
            print(f"  - {name}")

    # imprime mini resumo por coluna
    print("\n[Resumo por coluna] feature | tipo_detectado | violacoes | ok?")
    for r in col_summary[:50]:  # limita a 50 para console
        print(f"  {r['feature']} | {r['detected_type']} | {r['n_violations']} | {r['is_ok']}")
    if len(col_summary) > 50:
        print(f"  ... (+{len(col_summary)-50} colunas)")

    # Excel
    out_path = args.out
    if out_path:
        vdf = pd.DataFrame(violations).sort_values(["feature","excel_row"]).reset_index(drop=True)
        summary_df = pd.DataFrame(col_summary).sort_values(["is_ok","n_violations","feature"])
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="SUMMARY_BY_COLUMN")
            if not vdf.empty:
                vdf.to_excel(writer, index=False, sheet_name="VIOLATIONS")
            pd.DataFrame({"features_checked": features_to_check}).to_excel(writer, index=False, sheet_name="FEATURES_CHECKED")
            ctx = pd.DataFrame({
                "group": ["in_pont_nonzero","in_pont_zero","not_in_pont"],
                "count": [len(in_pont_nonzero), len(in_pont_zero), len(not_in_pont)]
            })
            ctx.to_excel(writer, index=False, sheet_name="CONTEXT")
        print(f"\n[INFO] Relatório salvo em: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    main()
