# -*- coding: utf-8 -*-
"""
auto_tuner.py
-------------
Orquestrador que chama o script de treino em ciclos e refina hiperparâmetros.
Ajusta também o grid da pós-regra do "Sem Transtorno" com base em métricas
(macro_valid e taxa de acionamento da regra).

Correções importantes para Windows / PATH / UTF-8:
 - Usa por padrão o MESMO interpretador que está rodando este script (sys.executable),
   em vez de "py" (que pode não estar no PATH).
 - Resolve o caminho ABSOLUTO do script de treino e define o diretório de trabalho (cwd)
   do subprocesso para a pasta do script de treino.
 - Força UTF-8 no processo filho (treino) com PYTHONIOENCODING/ PYTHONUTF8
   para evitar UnicodeEncodeError (γ/emoji) em consoles cp1252.
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime

# ======== util de tecla (Windows) ========
def user_pressed_quit_nonblocking():
    try:
        import msvcrt  # Windows
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            try:
                c = ch.decode('utf-8').lower()
            except Exception:
                c = str(ch).lower()
            if c == 'q':
                return True
    except Exception:
        # Em sistemas sem msvcrt, não há verificação nonblocking
        return False
    return False

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def resolve_train_paths(train_script_arg: str):
    """
    Tenta resolver caminho absoluto do script de treino, procurando:
      1) caminho absoluto (se já for)
      2) no diretório de trabalho atual (CWD)
      3) no diretório deste arquivo (auto_tuner.py)
    Retorna (train_script_abs, train_cwd).
    """
    if os.path.isabs(train_script_arg):
        train_abs = train_script_arg
    else:
        cand = os.path.abspath(train_script_arg)  # CWD
        if os.path.exists(cand):
            train_abs = cand
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            cand2 = os.path.join(here, train_script_arg)
            train_abs = cand2 if os.path.exists(cand2) else cand
    train_cwd = os.path.dirname(train_abs)
    return train_abs, train_cwd

def run_train_once(args, grid_cfg, lr, l1, l2, ga_scale, seed, round_idx):
    """Executa o script de treino uma vez, retornando o dicionário de relatório."""
    report_path = os.path.splitext(args.input)[0] + f"_report_round{round_idx}.json"

    python_cmd = args.python or sys.executable
    train_script_abs, train_cwd = resolve_train_paths(args.train_script)

    if not os.path.exists(train_script_abs):
        raise FileNotFoundError(
            f"Script de treino não encontrado:\n  '{train_script_abs}'\n"
            f"Dica: passe --train-script com caminho absoluto, por ex.:\n"
            f'  --train-script "c:\\SourceCode\\qip\\python\\05_tuna_heuristica_TreinoValid.py"'
        )

    train_cmd = [
        python_cmd,
        train_script_abs,
        "--input", args.input,
        "--output", args.output or args.input,
        "--sheet-dados", args.sheet_dados,
        "--sheet-pontos", args.sheet_pontos,
        "--sheet-pontos-tunada", args.sheet_pontos_tunada,
        "--prefer-tunada",
        "--train-frac", str(args.train_frac),
        "--min-support-val", str(args.min_support_val),
        "--topk", str(args.topk),
        "--seed", str(seed),
        "--l1", str(l1),
        "--l2", str(l2),
        "--lr", str(lr),
        "--max-iters", str(args.max_iters),
        "--check-every", str(args.check_every),
        "--early-stop-patience", str(args.early_stop_patience),
        "--target-macro-topk", str(args.target_macro_topk),
        "--eps-w", str(args.eps_w),
        "--normal-label", args.normal_label,
        "--grid-t1-min", str(grid_cfg['t1_min']),
        "--grid-t1-max", str(grid_cfg['t1_max']),
        "--grid-t1-steps", str(grid_cfg['t1_steps']),
        "--grid-t2-min", str(grid_cfg['t2_min']),
        "--grid-t2-max", str(grid_cfg['t2_max']),
        "--grid-t2-steps", str(grid_cfg['t2_steps']),
        "--grid-g-min",  str(grid_cfg['g_min']),
        "--grid-g-max",  str(grid_cfg['g_max']),
        "--grid-g-steps",str(grid_cfg['g_steps']),
        "--ga-num-mutants", str(args.ga_num_mutants),
        "--ga-mutate-cols", str(args.ga_mutate_cols),
        "--ga-mutation-scale", str(ga_scale),
        "--report-json", report_path,
    ]
    print(f"[RUN] Rodada {round_idx}: chamando treino...\n  PY : {python_cmd}\n  EXE: {train_script_abs}\n  CWD: {train_cwd}\n  CMD: {' '.join(train_cmd)}")

    # Força UTF-8 no processo filho
    child_env = os.environ.copy()
    child_env.setdefault("PYTHONIOENCODING", "utf-8")
    child_env.setdefault("PYTHONUTF8", "1")

    try:
        proc = subprocess.run(train_cmd, capture_output=True, text=True, cwd=train_cwd, env=child_env)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Falha ao iniciar o processo filho. Verifique se o Python e o script existem.\n"
            f"python_cmd = '{python_cmd}'\ntrain_script = '{train_script_abs}'\nCWD = '{train_cwd}'\n"
            f"Erro original: {e}"
        ) from e

    print(proc.stdout)
    if proc.returncode != 0:
        # Mostra também o stderr para facilitar o diagnóstico
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise RuntimeError("Falha na execução do script de treino. Veja o stderr acima.")

    if not os.path.exists(report_path):
        for line in proc.stdout.splitlines():
            if line.startswith("__REPORT_JSON__="):
                blob = line.split("=", 1)[1].strip()
                return json.loads(blob)
        raise FileNotFoundError(f"Não encontrei o relatório JSON em {report_path}.")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)

def refine_strategy(last_report, grid_cfg, lr, l1, l2, ga_scale, improve,
                    target_hit_low, target_hit_high, tighten_improve=0.40, tighten_noimprove=0.60):
    best_t1 = float(last_report.get("best_T1", (grid_cfg['t1_min'] + grid_cfg['t1_max'])/2))
    best_t2 = float(last_report.get("best_T2", (grid_cfg['t2_min'] + grid_cfg['t2_max'])/2))
    best_g  = float(last_report.get("best_gamma", (grid_cfg['g_min'] + grid_cfg['g_max'])/2))
    hit     = float(last_report.get("hit_rate_train", 0.0))

    span_t1 = max(0.02, (grid_cfg['t1_max'] - grid_cfg['t1_min']) / 2.0)
    span_t2 = max(0.01, (grid_cfg['t2_max'] - grid_cfg['t2_min']) / 2.0)
    span_g  = max(0.05, (grid_cfg['g_max']  - grid_cfg['g_min'])  / 2.0)

    tighten = tighten_improve if improve else tighten_noimprove

    center_shift_factor = 0.20
    if hit < target_hit_low - 1e-6:
        best_t1 += center_shift_factor * span_t1
        best_t2 += center_shift_factor * span_t2
        best_g  = clamp(best_g * 1.05, 0.0, 0.95)
        hit_msg = f"hit {hit:.3f} < {target_hit_low:.3f} ⇒ subir T1/T2 e ↑γ"
    elif hit > target_hit_high + 1e-6:
        best_t1 -= center_shift_factor * span_t1
        best_t2 -= center_shift_factor * span_t2
        best_g  = clamp(best_g * 0.95, 0.0, 0.95)
        hit_msg = f"hit {hit:.3f} > {target_hit_high:.3f} ⇒ descer T1/T2 e ↓γ"
    else:
        hit_msg = f"hit {hit:.3f} dentro da meta [{target_hit_low:.3f},{target_hit_high:.3f}] ⇒ centro mantido"

    def new_bounds(center, span, factor):
        lo = clamp(center - span * factor, 0.0, 1.0)
        hi = clamp(center + span * factor, 0.0, 1.0)
        if hi <= lo:
            lo = clamp(center - 0.05, 0.0, 1.0)
            hi = clamp(center + 0.05, 0.0, 1.0)
        return lo, hi

    t1_min, t1_max = new_bounds(best_t1, span_t1, tighten)
    t2_min, t2_max = new_bounds(best_t2, span_t2, tighten)
    g_min,  g_max  = new_bounds(best_g,  span_g,  tighten)

    steps_up = 1 if improve else 0
    new_grid = {
        "t1_min": t1_min, "t1_max": t1_max, "t1_steps": max(6, grid_cfg['t1_steps'] + steps_up),
        "t2_min": t2_min, "t2_max": t2_max, "t2_steps": max(6, grid_cfg['t2_steps'] + steps_up),
        "g_min":  g_min,  "g_max":  g_max,  "g_steps":  max(6, grid_cfg['g_steps']  + steps_up),
    }

    if not improve:
        lr = max(1e-4, lr * 0.85)
        ga_scale = max(0.003, ga_scale * 0.85)

    print(f"[TUNER] Refinamento: {hit_msg}")
    return new_grid, lr, l1, l2, ga_scale

def main():
    parser = argparse.ArgumentParser(
        description="Orquestrador de tuning iterativo (com adaptação do grid da pós-regra ST)."
    )
    parser.add_argument("--python", default=None, help="Caminho do Python (se vazio, usa sys.executable).")
    parser.add_argument("--train-script", default="05_tuna_heuristica_TreinoValid.py")

    parser.add_argument("--input", default="c:\\SourceCode\\qip\\python\\banco_dados.xlsx", help="Caminho do arquivo Excel de entrada.")
    parser.add_argument("--output", default=None, help="Se omitido, sobrescreve o input.")

    parser.add_argument("--sheet-dados", default="TDados_clean")
    parser.add_argument("--sheet-pontos", default="Pontuação")
    parser.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    parser.add_argument("--normal-label", default="Sem Transtorno")

    parser.add_argument("--train-frac", type=float, default=2.0/3.0)
    parser.add_argument("--min-support-val", type=int, default=2)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--target-macro-topk", type=float, default=0.99)

    parser.add_argument("--l1", type=float, default=1e-3)
    parser.add_argument("--l2", type=float, default=1e-2)
    parser.add_argument("--lr", type=float, default=0.1)
    parser.add_argument("--max-iters", type=int, default=1000)
    parser.add_argument("--check-every", type=int, default=10)
    parser.add_argument("--early-stop-patience", type=int, default=100)
    parser.add_argument("--eps-w", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--t1-min", type=float, default=0.18)
    parser.add_argument("--t1-max", type=float, default=0.60)
    parser.add_argument("--t1-steps", type=int, default=12)
    parser.add_argument("--t2-min", type=float, default=0.02)
    parser.add_argument("--t2-max", type=float, default=0.20)
    parser.add_argument("--t2-steps", type=int, default=10)
    parser.add_argument("--g-min",  type=float, default=0.30)
    parser.add_argument("--g-max",  type=float, default=0.75)
    parser.add_argument("--g-steps",type=int, default=10)

    parser.add_argument("--ga-num-mutants", type=int, default=20)
    parser.add_argument("--ga-mutate-cols", type=int, default=5)
    parser.add_argument("--ga-mutation-scale", type=float, default=0.05)

    parser.add_argument("--max-rounds", type=int, default=30, help="Limite de rodadas do tuner.")
    parser.add_argument("--sleep-seconds", type=float, default=0.5, help="Pausa entre rodadas (segundos).")

    parser.add_argument("--st-target-hit-low", type=float, default=0.08, help="Alvo inferior da taxa de acionamento da ST (treino).")
    parser.add_argument("--st-target-hit-high", type=float, default=0.35, help="Alvo superior da taxa de acionamento da ST (treino).")

    args = parser.parse_args()

    grid_cfg = {
        "t1_min": args.t1_min, "t1_max": args.t1_max, "t1_steps": args.t1_steps,
        "t2_min": args.t2_min, "t2_max": args.t2_max, "t2_steps": args.t2_steps,
        "g_min":  args.g_min,  "g_max":  args.g_max,  "g_steps":  args.g_steps,
    }
    lr = args.lr
    l1 = args.l1
    l2 = args.l2
    ga_scale = args.ga_mutation_scale
    seed = args.seed

    best_macro = -1.0
    best_report = None

    print("[TUNER] Iniciando loop de tuning. Pressione 'q' para encerrar (Windows).")
    for round_idx in range(1, args.max_rounds + 1):
        if user_pressed_quit_nonblocking():
            print("[TUNER] Tecla 'q' detectada. Encerrando.")
            break

        report = run_train_once(args, grid_cfg, lr, l1, l2, ga_scale, seed, round_idx)
        macro = float(report.get("macro_valid", -1.0))
        hit   = float(report.get("hit_rate_train", 0.0))
        print(f"[TUNER] Resultado rodada {round_idx}: macro_valid={macro:.4f}  (target={args.target_macro_topk:.4f})  hit_ST_train={hit:.3f}")

        improve = macro > best_macro + 1e-9
        if improve:
            best_macro = macro
            best_report = report

        if macro >= args.target_macro_topk - 1e-12:
            print("[TUNER] ✅ Meta atingida. Encerrando.")
            break

        grid_cfg, lr, l1, l2, ga_scale = refine_strategy(
            report, grid_cfg, lr, l1, l2, ga_scale, improve,
            target_hit_low=args.st_target_hit_low, target_hit_high=args.st_target_hit_high
        )
        seed += 1

        print(f"[TUNER] Novo grid: T1[{grid_cfg['t1_min']:.3f},{grid_cfg['t1_max']:.3f}]x{grid_cfg['t1_steps']} "
              f"T2[{grid_cfg['t2_min']:.3f},{grid_cfg['t2_max']:.3f}]x{grid_cfg['t2_steps']} "
              f"γ[{grid_cfg['g_min']:.3f},{grid_cfg['g_max']:.3f}]x{grid_cfg['g_steps']}")
        print(f"[TUNER] lr={lr:.5f}  l1={l1:.6f}  l2={l2:.6f}  ga_scale={ga_scale:.4f}  seed={seed}")
        time.sleep(args.sleep_seconds)

    if best_report:
        final_summary = {
            "best_macro_valid": best_macro,
            "target": args.target_macro_topk,
            "best_T1": best_report.get("best_T1"),
            "best_T2": best_report.get("best_T2"),
            "best_gamma": best_report.get("best_gamma"),
            "st_hit_train": best_report.get("hit_rate_train"),
            "lr": lr, "l1": l1, "l2": l2, "ga_scale": ga_scale,
            "used_sheet_last": best_report.get("used_sheet"),
            "output_file_last": best_report.get("output_file"),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "st_target_hit_range": [args.st_target_hit_low, args.st_target_hit_high],
        }
        out_json = os.path.splitext(args.input)[0] + "_auto_tuner_summary.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(final_summary, f, ensure_ascii=False, indent=2)
        print(f"[TUNER] Resumo final salvo em: {out_json}")
    else:
        print("[TUNER] Nenhum relatório válido coletado.")
    
if __name__ == "__main__":
    main()
