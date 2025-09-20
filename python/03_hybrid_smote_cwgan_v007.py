
import os
import sys
import math
import argparse
import warnings
import numpy as np
import pandas as pd
import unicodedata

warnings.filterwarnings("ignore")

from collections import deque
from datetime import datetime

# ML/Stats
from scipy.stats import ks_2samp
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score

# Imbalance
try:
    from imblearn.over_sampling import SMOTE, RandomOverSampler
except Exception as e:
    SMOTE = None
    RandomOverSampler = None

# Torch
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ---------- Utils ----------

def set_seed(seed: int = 42):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.benchmark = True

def user_pressed_q_nonblocking():
    # funciona no Windows (msvcrt). Em outros SOs, sempre False.
    try:
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch.lower() == 'q'
    except Exception:
        pass
    return False

def onehot(y_idx: torch.Tensor, n_classes: int) -> torch.Tensor:
    return F.one_hot(y_idx, num_classes=n_classes).float()

def ks_report(X_real: np.ndarray, X_syn: np.ndarray, feat_cols):
    rows = []
    for j in range(X_real.shape[1]):
        try:
            stat = ks_2samp(X_real[:, j], X_syn[:, j]).statistic
        except Exception:
            stat = np.nan
        rows.append((feat_cols[j], stat))
    return pd.DataFrame(rows, columns=["feature", "ks_stat"])

def corr_gap(X_real: np.ndarray, X_syn: np.ndarray) -> float:
    try:
        C_r = np.corrcoef(X_real, rowvar=False)
        C_s = np.corrcoef(X_syn, rowvar=False)
        if np.isnan(C_r).any() or np.isnan(C_s).any():
            C_r = np.nan_to_num(C_r, nan=0.0)
            C_s = np.nan_to_num(C_s, nan=0.0)
        return float(np.linalg.norm(C_r - C_s, ord='fro'))
    except Exception:
        return float('nan')

def per_class_split(df, target_col, perc=50.0, seed=42):
    rng = np.random.default_rng(seed)
    y = df[target_col].astype(str).values
    mask = np.zeros(len(df), dtype=bool)
    classes = np.unique(y)
    for c in classes:
        idx = np.where(y == c)[0]
        if len(idx) == 0:
            continue
        n_train = int(math.ceil(len(idx) * float(perc) / 100.0))
        n_train = max(1, min(n_train, len(idx)))
        choose = rng.choice(idx, size=n_train, replace=False)
        mask[choose] = True
    return mask

def _strip_accents(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch))

def _normalize_series_text(ser: pd.Series) -> pd.Series:
    return ser.astype(str).str.strip().apply(lambda x: _strip_accents(x).lower())

def impute_numeric(df: pd.DataFrame, feat_cols, strategy="median"):
    df = df.copy()
    # replace inf with NaN
    for c in feat_cols:
        col = pd.to_numeric(df[c], errors='coerce')
        col = col.replace([np.inf, -np.inf], np.nan)
        df[c] = col
    if strategy == "median":
        med = df[feat_cols].median(numeric_only=True)
        df[feat_cols] = df[feat_cols].fillna(med)
    else:
        df[feat_cols] = df[feat_cols].fillna(0.0)
    return df

def fit_resample_balanced(X, y, n_classes, seed=42, target_total=5400):
    """SMOTE com k adaptativo; se min_classe<2, cai para ROS. Depois, ROS2 para atingir target_total."""
    X_res, y_res = X, y
    used = []
    counts = np.bincount(y, minlength=n_classes)
    pos_counts = counts[counts > 0]
    min_count = int(pos_counts.min()) if len(pos_counts) else 0

    did_smote = False
    if SMOTE is not None and min_count >= 2:
        k = max(1, min(5, min_count - 1))  # 2->1, 3->2, ..., limite superior 5
        try:
            sm = SMOTE(random_state=seed, k_neighbors=k)
            X_res, y_res = sm.fit_resample(X, y)
            used.append(f"SMOTE(k={k})")
            did_smote = True
        except Exception as e:
            print(f"[WARN] SMOTE falhou ({e}); usando RandomOverSampler.", flush=True)

    if not did_smote:
        if RandomOverSampler is None:
            print("[WARN] imblearn não disponível; seguindo sem oversampling.", flush=True)
            return X, y, "None"
        ros = RandomOverSampler(random_state=seed)
        X_res, y_res = ros.fit_resample(X, y)
        used.append("ROS")

    # Completa para target_total com ROS de estratégia por classe
    if target_total is not None and len(X_res) < target_total and RandomOverSampler is not None:
        counts2 = np.bincount(y_res, minlength=n_classes)
        per_cls = int(math.ceil(float(target_total) / n_classes))
        sampling_strategy = {c: max(per_cls, int(counts2[c])) for c in range(n_classes)}
        ros2 = RandomOverSampler(random_state=seed, sampling_strategy=sampling_strategy)
        X_res, y_res = ros2.fit_resample(X_res, y_res)
        used.append("ROS2")

    return X_res, y_res, "+".join(used) if used else "None"

# ---------- Data ----------

class TabularDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)
    def __len__(self):
        return self.X.shape[0]
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# ---------- Models ----------

class Generator(nn.Module):
    def __init__(self, z_dim, y_dim, x_dim, hidden=256):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(z_dim + y_dim, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, x_dim),
            nn.Sigmoid()
        )

    def forward(self, z, y_onehot):
        h = torch.cat([z, y_onehot], dim=1)
        return self.fc(h)

class Discriminator(nn.Module):
    def __init__(self, x_dim, y_dim, hidden=256):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(x_dim + y_dim, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, 1)
        )

    def forward(self, x, y_onehot):
        h = torch.cat([x, y_onehot], dim=1)
        return self.fc(h)

class CWGAN_GP:
    def __init__(self, x_dim, n_classes, z_dim=64, hidden=256, gp_lambda=10.0, n_critic=5,
                 lrG=1e-4, lrD=1e-4, inst_noise=0.0, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.z_dim = z_dim
        self.gp_lambda = gp_lambda
        self.n_critic = n_critic
        self.inst_noise = float(inst_noise)
        self.G = Generator(z_dim, n_classes, x_dim, hidden).to(self.device)
        self.D = Discriminator(x_dim, n_classes, hidden).to(self.device)
        self.opt_G = torch.optim.Adam(self.G.parameters(), lr=lrG, betas=(0.5, 0.9))
        self.opt_D = torch.optim.Adam(self.D.parameters(), lr=lrD, betas=(0.5, 0.9))

    def _add_instance_noise(self, x):
        if self.inst_noise > 0.0:
            x = x + self.inst_noise * torch.randn_like(x)
            x = torch.clamp(x, 0.0, 1.0)
        return x

    def gradient_penalty(self, x_real, x_fake, y_onehot):
        alpha = torch.rand(x_real.size(0), 1, device=self.device).expand_as(x_real)
        interpolates = alpha * x_real + (1 - alpha) * x_fake
        interpolates.requires_grad_(True)
        d_interpolates = self.D(interpolates, y_onehot)
        grads = torch.autograd.grad(
            outputs=d_interpolates,
            inputs=interpolates,
            grad_outputs=torch.ones_like(d_interpolates),
            create_graph=True,
            retain_graph=True,
            only_inputs=True
        )[0]
        grads = grads.view(grads.size(0), -1)
        gp = ((grads.norm(2, dim=1) - 1) ** 2).mean()
        return gp

    def sample(self, n, y_idx=None, n_classes=None):
        self.G.eval()
        with torch.no_grad():
            if y_idx is None:
                assert n_classes is not None, "Informe n_classes ou y_idx"
                y_idx = torch.randint(low=0, high=n_classes, size=(n,), device=self.device)
            y_oh = onehot(y_idx, n_classes if n_classes is not None else int(y_idx.max().item()+1))
            z = torch.randn(n, self.z_dim, device=self.device)
            x = self.G(z, y_oh)
        self.G.train()
        return x.detach().cpu().numpy(), y_idx.detach().cpu().numpy()

    def train(self, loader, n_classes, epochs=2000, log_every=100,
              eval_every=0, eval_fn=None, early_cfg=None):
        stop_now = False
        last_gap = None
        gaps = deque(maxlen=(early_cfg['gap_window'] if early_cfg else 500))
        eval_history = []
        best_tstr = None
        plateau = 0
        stable_gap = 0

        for ep in range(1, epochs + 1):
            if user_pressed_q_nonblocking():
                print("[INFO] Stop solicitado pelo usuário ('q'). Encerrando treino antecipadamente.", flush=True)
                break
            for x_real, y_idx in loader:
                if user_pressed_q_nonblocking():
                    print("[INFO] Stop solicitado pelo usuário ('q'). Encerrando treino antecipadamente.", flush=True)
                    stop_now = True
                    break
                x_real = x_real.to(self.device)
                y_idx = y_idx.to(self.device)
                y_oh = onehot(y_idx, n_classes)

                # Segurança contra NaNs/inf
                x_real = torch.nan_to_num(x_real, nan=0.0, posinf=1.0, neginf=0.0)

                # --- Critic updates ---
                for _ in range(self.n_critic):
                    z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                    with torch.no_grad():
                        x_fake = self.G(z, y_oh)
                    # Instance noise em ambas as entradas do D
                    xr = self._add_instance_noise(x_real)
                    xf = self._add_instance_noise(x_fake)
                    d_real = self.D(xr, y_oh).mean()
                    d_fake = self.D(xf, y_oh).mean()
                    gp = self.gradient_penalty(xr, xf, y_oh)
                    d_loss = -(d_real - d_fake) + self.gp_lambda * gp
                    self.opt_D.zero_grad(set_to_none=True)
                    d_loss.backward()
                    self.opt_D.step()

                # --- Generator update ---
                z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                x_gen = self.G(z, y_oh)
                xg = self._add_instance_noise(x_gen)
                g_loss = -self.D(xg, y_oh).mean()
                self.opt_G.zero_grad(set_to_none=True)
                g_loss.backward()
                self.opt_G.step()

                last_gap = (d_real - d_fake).item()
                gaps.append(last_gap)

            if stop_now:
                break

            if ep % log_every == 0 or ep == 1:
                gap_ma = float(np.mean(gaps)) if len(gaps) else float('nan')
                print(f"[{ep:04d}/{epochs}] D_loss={d_loss.item():.4f}  G_loss={g_loss.item():.4f}  "
                      f"D(real)={d_real.item():.4f} D(fake)={d_fake.item():.4f}  gap={last_gap:.4f} gap_ma={gap_ma:.4f}",
                      flush=True)

            # Avaliação + early stop
            if eval_every and (ep % eval_every == 0):
                gap_ma = float(np.mean(gaps)) if len(gaps) else float('nan')
                metrics = {"epoch": ep, "gap_ma": gap_ma, "gap_last": last_gap}
                if callable(eval_fn):
                    try:
                        ev = eval_fn(self)
                        metrics.update(ev)
                    except Exception as e:
                        print(f"[WARN] eval_fn falhou: {e}")
                eval_history.append(metrics)

                if early_cfg:
                    cur_tstr = metrics.get("tstr_macro_f1", None)
                    if cur_tstr is not None and not np.isnan(cur_tstr):
                        if best_tstr is None or (cur_tstr - best_tstr) > (early_cfg.get("tstr_tol", 0.5) / 100.0):
                            best_tstr = cur_tstr
                            plateau = 0
                        else:
                            plateau += 1
                    if (gap_ma == gap_ma) and (early_cfg.get("gap_low", 0.05) <= gap_ma <= early_cfg.get("gap_high", 0.30)):
                        stable_gap += 1
                    else:
                        stable_gap = 0
                    if ep >= early_cfg.get("min_epochs", 2000) and plateau >= early_cfg.get("patience", 3) and stable_gap >= early_cfg.get("patience", 3):
                        print(f"[EARLY STOP] Sem melhora TSTR por {plateau} avaliações e gap_ma estável ({gap_ma:.3f}). Ep={ep}", flush=True)
                        break

                # Print resumo eval
                msg = [f"[EVAL ep={ep}] gap_ma={gap_ma:.4f}"]
                for k in ("tstr_macro_f1", "tstr_ratio", "baseline_macro_f1", "ks_median", "corr_gap_fro", "class_diff_mean", "class_diff_max"):
                    if k in metrics and metrics[k] is not None:
                        if k.endswith("macro_f1") or k == "tstr_ratio":
                            msg.append(f"{k}={metrics[k]*100:.2f}%")
                        else:
                            msg.append(f"{k}={metrics[k]:.4f}")
                print("  " + "  |  ".join(msg), flush=True)

        return eval_history

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Hybrid SMOTE + cWGAN-GP for Tabular Conditional Synthesis")
    ap.add_argument("--input", type=str, default="c:\\SourceCode\\qip\\python\\banco_dados.xlsx", help="Arquivo de entrada (Excel).")
    ap.add_argument("--sheet", type=str, default="TDados", help="Aba com os dados (features + alvo).")
    ap.add_argument("--target", type=str, default="Alvo", help="Nome da coluna alvo.")
    ap.add_argument("--seed", type=int, default=42, help="Random seed.")
    ap.add_argument("--epochs", type=int, default=50000, help="Número de épocas para o GAN.")
    ap.add_argument("--log-every", type=int, default=100, help="Frequência de logs.")
    ap.add_argument("--half-split", action=argparse.BooleanOptionalAction, default=False,
                    help="Se ligado, separa por classe usando --split-perc para treino e o resto como holdout.")
    ap.add_argument("--split-perc", type=float, default=100.0,
                    help="Percentual (0-100) de cada classe que vai para treino quando --half-split está ativo.")
    ap.add_argument("--min-samples-per-class", type=int, default=4,
                    help="Classes com menos amostras que este valor serão REMOVIDAS antes do split.")
    ap.add_argument("--smote-target", type=int, default=5400, help="Tamanho alvo após oversampling.")
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--z-dim", type=int, default=64)
    ap.add_argument("--hidden", type=int, default=384)
    ap.add_argument("--gp-lambda", type=float, default=10.0)
    ap.add_argument("--n-critic", type=int, default=3)
    ap.add_argument("--lrG", type=float, default=2e-4)
    ap.add_argument("--lrD", type=float, default=5e-5)
    ap.add_argument("--inst-noise", type=float, default=0.02,
                    help="Desvio-padrão do ruído gaussiano (instance noise) aplicado às entradas do D.")
    ap.add_argument("--eval-every", type=int, default=1000,
                    help="Frequência (épocas) para rodar avaliação TSTR/KS/correlação durante o treino (0 desativa).")
    ap.add_argument("--early-patience", type=int, default=3,
                    help="Número de avaliações sem melhora significativa para parar (plateau).")
    ap.add_argument("--gap-window", type=int, default=500,
                    help="Janela da média móvel do gap de Wasserstein (D(real)-D(fake)).")
    ap.add_argument("--gap-stable-low", type=float, default=0.05,
                    help="Limite inferior para considerar o gap médio estável.")
    ap.add_argument("--gap-stable-high", type=float, default=0.30,
                    help="Limite superior para considerar o gap médio estável.")
    ap.add_argument("--tstr-tol", type=float, default=0.5,
                    help="Variação mínima (em pontos percentuais) no TSTR macro-F1 para considerar melhora.")
    ap.add_argument("--min-epochs-early", type=int, default=4000,
                    help="Épocas mínimas antes de permitir parada antecipada.")
    ap.add_argument("--save-excel-report", action=argparse.BooleanOptionalAction, default=True,
                    help="Salvar planilha com abas de saída ('REPORT', 'EVAL_HISTORY', etc.).")
    ap.add_argument("--out", type=str, default=None, help="Arquivo Excel de saída (default: gera com timestamp).")
    ap.add_argument("--drop-nao", action=argparse.BooleanOptionalAction, default=True,
                    help="Remove linhas cujo alvo seja 'não/nao' (desconhecido) do treino/avaliação.")
    ap.add_argument("--impute", type=str, choices=["median","zero"], default="median",
                    help="Estratégia de imputação para NaNs nas features numéricas.")

    args = ap.parse_args()

    set_seed(args.seed)

    in_path = args.input
    sheet = args.sheet
    target = args.target

    if not os.path.isfile(in_path):
        print(f"[ERRO] Arquivo de entrada não encontrado: {in_path}")
        sys.exit(1)

    print(f"[INFO] Reading: {os.path.abspath(in_path)} (sheet='{sheet}') target='{target}'")

    # Lê Excel
    xls = pd.ExcelFile(in_path)
    if sheet not in xls.sheet_names:
        raise ValueError(f"Aba '{sheet}' não encontrada no Excel. Disponíveis: {xls.sheet_names}")

    df_full = pd.read_excel(in_path, sheet_name=sheet)
    df_full = df_full.copy()

    # Copiar "Pontuação" se existir
    pontos_df = None
    if "Pontuação" in xls.sheet_names:
        try:
            pontos_df = pd.read_excel(in_path, sheet_name="Pontuação")
            print("[INFO] Aba 'Pontuação' encontrada e será copiada para o arquivo de saída.")
        except Exception:
            pontos_df = None

    # Drop 'não/nao' (desconhecido), se habilitado
    if args.drop_nao:
        tgt_norm0 = _normalize_series_text(df_full[target])
        drop_mask0 = tgt_norm0.eq("nao") | tgt_norm0.eq("não") | tgt_norm0.eq("nao/nao") | tgt_norm0.eq("nao / nao")
        if drop_mask0.any():
            before0 = len(df_full)
            df_full = df_full.loc[~drop_mask0].copy()
            removed0 = before0 - len(df_full)
            print(f"[INFO] Removidas {removed0} linhas com alvo 'não/nao'.")

    # Mostrar contagem por classe (após o drop acima) e remover classes raras
    counts_full = df_full[target].value_counts().sort_index()
    print("[INFO] Contagem por classe (após drop 'nao'):")
    for cls, cnt in counts_full.items():
        print(f"  - {cls}: {cnt}")

    threshold = max(0, int(args.min_samples_per_class))
    rare_classes = [cls for cls, cnt in counts_full.items() if cnt < threshold]
    excluded_rare_df = None
    if len(rare_classes) > 0 and threshold > 0:
        print(f"[INFO] Removendo {len(rare_classes)} classe(s) com < {threshold} amostras:")
        for cls in rare_classes:
            print(f"  - {cls}: {counts_full[cls]} (removida)")
        excluded_rare_df = df_full[df_full[target].isin(rare_classes)].copy()
        df_full = df_full[~df_full[target].isin(rare_classes)].copy()

    # Seleciona colunas numéricas como features
    num_cols = df_full.select_dtypes(include=[np.number]).columns.tolist()
    if target in num_cols:
        num_cols.remove(target)
    feat_cols = [c for c in num_cols if c != target]
    if len(feat_cols) == 0:
        raise ValueError("Nenhuma feature numérica encontrada. Verifique suas colunas.")

    # Alvo como string limpa e mapa de índices (após remover raras)
    y_str_full = df_full[target].astype(str).str.strip()
    classes = sorted(y_str_full.unique())
    label_to_idx = {c: i for i, c in enumerate(classes)}
    print(f"[INFO] Found {len(classes)} classes após remoções: {classes}")

    # Split opcional por classe
    if args.half_split:
        train_mask = per_class_split(df_full, target, perc=args.split_perc, seed=args.seed)
        df_train = df_full.loc[train_mask].copy()
        df_holdout = df_full.loc[~train_mask].copy()
        print(f"[INFO] Half-split ({args.split_perc:.1f}% por classe): train={len(df_train)}  holdout={len(df_holdout)}")
    else:
        df_train = df_full.copy()
        df_holdout = None

    # Imputação de NaNs nas features numéricas
    if args.impute:
        df_train = impute_numeric(df_train, feat_cols, strategy=args.impute)
        if df_holdout is not None and len(df_holdout) > 0:
            df_holdout = impute_numeric(df_holdout, feat_cols, strategy=args.impute)

    # Matriz X e y a partir do train
    X_all = df_train[feat_cols].to_numpy(dtype=np.float32)
    if not np.isfinite(X_all).all():
        n_nans = np.isnan(X_all).sum()
        n_infs = np.isinf(X_all).sum()
        print(f"[WARN] Encontrados NaNs({n_nans}) e Infs({n_infs}) em X_all; serão imputados/zerados.")
        X_all = np.nan_to_num(X_all, nan=0.0, posinf=1.0, neginf=0.0)
    X_all = np.clip(X_all, 0.0, 1.0)
    y_all = df_train[target].astype(str).str.strip().map(label_to_idx).to_numpy(dtype=np.int64)
    n_classes = len(classes)

    # Oversampling
    X_sm, y_sm, over_used = fit_resample_balanced(X_all, y_all, n_classes, seed=args.seed, target_total=args.smote_target)
    print(f"[INFO] SMOTE: {len(X_all)} -> {len(X_sm)} rows (training set) [{over_used}]")

    # DataLoader
    ds = TabularDataset(X_sm, y_sm)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    # Conjunto REAL para avaliação (holdout; senão carve-out 20% do train)
    if df_holdout is not None and len(df_holdout) > 0:
        X_eval = df_holdout[feat_cols].to_numpy(dtype=np.float32)
        X_eval = np.nan_to_num(X_eval, nan=0.0, posinf=1.0, neginf=0.0)
        X_eval = np.clip(X_eval, 0.0, 1.0)
        y_eval = df_holdout[target].astype(str).str.strip().map(label_to_idx).to_numpy(dtype=np.int64)
    else:
        eval_frac = 0.20
        counts = np.bincount(y_all, minlength=n_classes)
        can_strat = (
            counts.min() >= 2 and
            np.all(counts * eval_frac >= 1) and
            np.all(counts * (1.0 - eval_frac) >= 1)
        )
        if not can_strat:
            print("[WARN] Classe com <=1 amostra ou fração insuficiente por classe; usando split aleatório SEM estratificar para o conjunto de avaliação.")
        X_tmp, X_eval, y_tmp, y_eval = train_test_split(
            X_all, y_all,
            test_size=eval_frac,
            random_state=args.seed,
            stratify=(y_all if can_strat else None),
        )
        del X_tmp, y_tmp
        X_eval = np.nan_to_num(X_eval, nan=0.0, posinf=1.0, neginf=0.0)
        X_eval = np.clip(X_eval, 0.0, 1.0)

    # Modelo
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CWGAN_GP(
        x_dim=X_all.shape[1],
        n_classes=n_classes,
        z_dim=args.z_dim,
        hidden=args.hidden,
        gp_lambda=args.gp_lambda,
        n_critic=args.n_critic,
        lrG=args.lrG, lrD=args.lrD,
        inst_noise=args.inst_noise,
        device=device
    )

    # Distribuições para amostragem de rótulos durante avaliação
    counts_sm = np.bincount(y_sm, minlength=n_classes).astype(float)
    p_sm = counts_sm / max(counts_sm.sum(), 1.0)
    counts_real_eval = np.bincount(y_eval, minlength=n_classes).astype(float)
    p_real = counts_real_eval / max(counts_real_eval.sum(), 1.0)

    def _eval_fn(m: 'CWGAN_GP'):
        # Escolhe distribuição real se disponível; senão, usa a do treino SMOTE
        p_use = p_real if np.isfinite(p_real).all() and p_real.sum() > 0 else p_sm
        n_syn = min(len(X_eval), 5000) if len(X_eval) > 0 else 1000
        y_idx_syn = np.random.choice(np.arange(n_classes), size=n_syn, replace=True, p=p_use)
        y_idx_syn_t = torch.tensor(y_idx_syn, dtype=torch.long, device=m.device)
        X_syn, Y_syn = m.sample(n_syn, y_idx=y_idx_syn_t, n_classes=n_classes)

        # TSTR: treino no sintético, teste no real
        X_syn = np.nan_to_num(X_syn, nan=0.0, posinf=1.0, neginf=0.0)
        scaler = StandardScaler().fit(X_syn)
        Xtr = scaler.transform(X_syn)
        Xte = scaler.transform(X_eval) if len(X_eval) > 0 else X_eval
        clf = LogisticRegression(max_iter=300, multi_class="auto")
        try:
            clf.fit(Xtr, Y_syn)
            y_pred = clf.predict(Xte) if len(X_eval) > 0 else np.array([])
            tstr_macro_f1 = f1_score(y_eval, y_pred, average="macro") if len(X_eval) > 0 else float('nan')
        except Exception as e:
            print(f"[WARN] TSTR falhou: {e}")
            tstr_macro_f1 = float('nan')

        # Baseline real→real (treina no real de treino, testa no real de avaliação)
        try:
            scaler_b = StandardScaler().fit(X_all)
            Xtr_b = scaler_b.transform(X_all)
            Xte_b = scaler_b.transform(X_eval) if len(X_eval) > 0 else X_eval
            clf_b = LogisticRegression(max_iter=300, multi_class="auto").fit(Xtr_b, y_all)
            yb = clf_b.predict(Xte_b) if len(X_eval) > 0 else np.array([])
            baseline_macro_f1 = f1_score(y_eval, yb, average="macro") if len(X_eval) > 0 else float('nan')
        except Exception as e:
            print(f"[WARN] Baseline real→real falhou: {e}")
            baseline_macro_f1 = float('nan')

        # tstr_ratio
        if baseline_macro_f1 is not None and baseline_macro_f1 == baseline_macro_f1 and baseline_macro_f1 > 0:
            tstr_ratio = float(tstr_macro_f1 / baseline_macro_f1)
        else:
            tstr_ratio = float('nan')

        # KS/Corr
        try:
            ks_df = ks_report(X_eval, X_syn, feat_cols) if len(X_eval) > 0 else pd.DataFrame(columns=["feature", "ks_stat"])
            ks_median = float(ks_df["ks_stat"].median()) if not ks_df.empty else float('nan')
        except Exception:
            ks_median = float('nan')
        try:
            corr_fro = corr_gap(X_eval, X_syn) if len(X_eval) > 0 else float('nan')
        except Exception:
            corr_fro = float('nan')

        # Diferença de distribuição de classes
        try:
            real_p = counts_real_eval / max(counts_real_eval.sum(), 1.0)
            syn_p = np.bincount(Y_syn, minlength=n_classes).astype(float); syn_p /= max(syn_p.sum(), 1.0)
            class_diff = np.abs(real_p - syn_p)
            class_diff_mean = float(class_diff.mean())
            class_diff_max  = float(class_diff.max())
        except Exception:
            class_diff_mean = float('nan')
            class_diff_max = float('nan')

        return {
            "tstr_macro_f1": float(tstr_macro_f1),
            "baseline_macro_f1": float(baseline_macro_f1),
            "tstr_ratio": float(tstr_ratio),
            "ks_median": ks_median,
            "corr_gap_fro": float(corr_fro),
            "class_diff_mean": class_diff_mean,
            "class_diff_max": class_diff_max
        }

    early_cfg = dict(
        patience=args.early_patience,
        gap_window=args.gap_window,
        gap_low=args.gap_stable_low,
        gap_high=args.gap_stable_high,
        tstr_tol=args.tstr_tol,
        min_epochs=args.min_epochs_early
    )

    eval_history = model.train(
        loader, n_classes=n_classes, epochs=args.epochs, log_every=args.log_every,
        eval_every=args.eval_every, eval_fn=_eval_fn, early_cfg=early_cfg
    )

    # --------- Saída ---------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = args.out if args.out else f"banco_dados_sintetico_{ts}.xlsx"
    with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
        # Dados de treino (após split)
        df_train_out = df_train.copy()
        df_train_out.to_excel(writer, index=False, sheet_name="DATA_TRAIN")
        # Holdout se existir
        if df_holdout is not None and len(df_holdout) > 0:
            df_holdout.to_excel(writer, index=False, sheet_name="DATA_HOLDOUT")
        # Copia Pontuação se existir
        if pontos_df is not None:
            pontos_df.to_excel(writer, index=False, sheet_name="Pontuação")
        # Excluídas por rareza (se houver)
        if excluded_rare_df is not None and len(excluded_rare_df) > 0:
            excluded_rare_df.to_excel(writer, index=False, sheet_name="DATA_EXCLUDED_RARE")
        # Report simples
        rep = pd.DataFrame({
            "metric": ["n_classes", "train_rows", "holdout_rows", "smote_rows", "device", "oversampler"],
            "value": [len(classes), len(df_train), 0 if df_holdout is None else len(df_holdout), len(X_sm), ("cuda" if torch.cuda.is_available() else "cpu"), "SMOTE/ROS"]
        })
        if args.save_excel_report:
            rep.to_excel(writer, index=False, sheet_name="REPORT")
            # Histórico de avaliações
            try:
                hist_df = pd.DataFrame(eval_history)
                if not hist_df.empty:
                    hist_df.to_excel(writer, index=False, sheet_name="EVAL_HISTORY")
            except Exception as e:
                print(f"[WARN] Não foi possível salvar EVAL_HISTORY: {e}")

    print(f"[INFO] Arquivo salvo em: {os.path.abspath(out_xlsx)}")

if __name__ == "__main__":
    main()
