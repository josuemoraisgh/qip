# v015_defaults_plus: early stop com queda de TSTR, checkpoint do melhor por TSTR e restauração antes de gerar sintéticos.
# Padrões atualizados:
# - --smote-target 2400
# - --batch-size 256, --z-dim 128, --hidden 512, --n-critic 8
# - --lrG 2.5e-4, --lrD 4e-5, --inst-noise 0.05
# - --eval-every 250, --early-patience 2, --min-epochs-early 1500, --tstr-tol 0.1
# - --tstr-drop 2.0, --patience-drop 2
# - geração sintética proporcional ao histograma; GOLDEN-ONLY; MinMax por feature; arredondamento binário/smallint ao salvar

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
from sklearn.metrics import f1_score

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

def detect_feature_types(df: pd.DataFrame, feat_cols):
    """Detecta binárias, inteiras pequenas (0..10) e reais."""
    types = {}
    for c in feat_cols:
        col = pd.to_numeric(df[c], errors='coerce').dropna()
        if col.empty:
            types[c] = "real"
            continue
        # binária?
        uniq = set(np.unique(col.values))
        if uniq.issubset({0,1}):
            types[c] = "binary"
            continue
        # inteira pequena 0..10?
        is_int = np.all(np.isfinite(col)) and np.all(np.abs(col - np.round(col)) < 1e-6)
        in_range = (col.min() >= 0) and (col.max() <= 10)
        if is_int and in_range:
            types[c] = "smallint"
        else:
            types[c] = "real"
    return types

class MinMaxPerFeature:
    """MinMax por coluna com proteção para min==max, usado para escalar a [0,1]"""
    def __init__(self):
        self.min_ = None
        self.max_ = None
        self.range_ = None
        self.cols = None
    def fit(self, X: np.ndarray, cols):
        self.min_ = np.nanmin(X, axis=0)
        self.max_ = np.nanmax(X, axis=0)
        self.range_ = self.max_ - self.min_
        self.range_[self.range_ == 0] = 1.0  # evita div/0
        self.cols = list(cols)
        return self
    def transform(self, X: np.ndarray):
        return np.clip((X - self.min_) / self.range_, 0.0, 1.0).astype(np.float32)
    def inverse_transform(self, Xs: np.ndarray):
        return (Xs * self.range_ + self.min_).astype(np.float32)

# ---------- Oversampling helper ----------

def _ros_numpy(X, y, desired_counts, seed=42):
    """Fallback ROS manual caso imblearn não esteja disponível."""
    rng = np.random.default_rng(seed)
    X_list, y_list = [], []
    classes = np.unique(y)
    for cls in classes:
        idx = np.where(y == cls)[0]
        cur = len(idx)
        want = desired_counts.get(int(cls), cur)
        if want <= cur:
            X_list.append(X[idx])
            y_list.append(y[idx])
        else:
            # sample with replacement
            add = want - cur
            choice = rng.choice(idx, size=add, replace=True)
            X_list.append(np.concatenate([X[idx], X[choice]], axis=0))
            y_list.append(np.concatenate([y[idx], y[choice]], axis=0))
    Xr = np.concatenate(X_list, axis=0)
    yr = np.concatenate(y_list, axis=0)
    return Xr, yr

def fit_resample_balanced(X, y, n_classes, seed=42, target_total=2400):
    """
    1) Tenta SMOTE até, no mínimo, nivelar todas as classes em 'ceil(target_total/n_classes)'.
       - Ajusta k_neighbors = min(5, min_cls-1).
       - Se falhar ou houver classe com <2 amostras, cai para ROS.
    2) Se total < target_total, faz uma 2ª passada com ROS para chegar no total exato, distribuindo uniformemente.
    Retorna: X_res, y_res, tag (ex.: 'SMOTE', 'ROS', 'SMOTE+ROS2').
    """
    y = y.astype(int)
    classes = np.arange(n_classes, dtype=int)
    counts = np.bincount(y, minlength=n_classes)
    per_class_goal = int(math.ceil(target_total / float(n_classes)))
    desired = {int(c): max(int(counts[c]), per_class_goal) for c in classes}

    used = None
    X_res, y_res = X, y

    def _ros_to_desired(Xa, ya, desired_map, tag_label):
        nonlocal used
        if RandomOverSampler is not None:
            ros = RandomOverSampler(random_state=seed, sampling_strategy=desired_map)
            Xb, yb = ros.fit_resample(Xa, ya)
        else:
            Xb, yb = _ros_numpy(Xa, ya, desired_map, seed=seed)
        used = tag_label if used is None else used + "+" + tag_label
        return Xb, yb

    # Try SMOTE first
    can_smote = (SMOTE is not None) and (counts.min() >= 2) and (sum(counts > 0) > 1)
    if can_smote:
        try:
            k = min(5, int(counts[counts >= 2].min()) - 1)
            k = max(k, 1)
            # only request for classes that need upsampling
            smote_targets = {cls: tgt for cls, tgt in desired.items() if counts[cls] < tgt}
            if len(smote_targets) > 0:
                sm = SMOTE(random_state=seed, k_neighbors=k, sampling_strategy=smote_targets)
                X_res, y_res = sm.fit_resample(X, y)
                used = "SMOTE"
            else:
                used = "NONE"
        except Exception as e:
            print(f"[WARN] SMOTE falhou ({e}); usando RandomOverSampler.", flush=True)
            X_res, y_res = _ros_to_desired(X, y, desired, "ROS")
    else:
        if SMOTE is None:
            print("[WARN] 'imblearn' não disponível; usando RandomOverSampler.", flush=True)
        else:
            print("[WARN] Classe(s) com <2 amostras; SMOTE indisponível. Usando RandomOverSampler.", flush=True)
        X_res, y_res = _ros_to_desired(X, y, desired, "ROS")

    # Stage 2: if total still less than target_total, distribute extras using ROS
    cur_total = len(y_res)
    if cur_total < target_total:
        rem = target_total - cur_total
        cur_counts = np.bincount(y_res, minlength=n_classes)
        # distribute approximately uniform, favoring classes com menores contagens atuais
        order = np.argsort(cur_counts)  # ascending
        desired2 = {int(c): int(cur_counts[c]) for c in classes}
        i = 0
        while rem > 0:
            desired2[int(order[i % n_classes])] += 1
            rem -= 1
            i += 1
        X_res, y_res = _ros_to_desired(X_res, y_res, desired2, "ROS2")

    if used is None:
        used = "NONE"
    return X_res, y_res, used

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
    def __init__(self, z_dim, y_dim, x_dim, hidden=512):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(z_dim + y_dim, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(hidden, x_dim),
            nn.Sigmoid()  # gera em [0,1] compatível com MinMax
        )

    def forward(self, z, y_onehot):
        h = torch.cat([z, y_onehot], dim=1)
        return self.fc(h)

class Discriminator(nn.Module):
    def __init__(self, x_dim, y_dim, hidden=512):
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
    def __init__(self, x_dim, n_classes, z_dim=128, hidden=512, gp_lambda=10.0, n_critic=8,
                 lrG=2.5e-4, lrD=4e-5, inst_noise=0.05, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.z_dim = z_dim
        self.gp_lambda = gp_lambda
        self.n_critic = n_critic
        self.inst_noise = float(inst_noise)
        self.G = Generator(z_dim, n_classes, x_dim, hidden).to(self.device)
        self.D = Discriminator(x_dim, n_classes, hidden).to(self.device)
        self.opt_G = torch.optim.Adam(self.G.parameters(), lr=lrG, betas=(0.5, 0.9))
        self.opt_D = torch.optim.Adam(self.D.parameters(), lr=lrD, betas=(0.5, 0.9))

        # checkpoint do melhor por TSTR
        self.best = {"tstr": None, "epoch": None, "G": None, "D": None}

    def _save_best(self, epoch, tstr_val):
        self.best["tstr"]  = float(tstr_val)
        self.best["epoch"] = int(epoch)
        self.best["G"] = {k: v.detach().cpu().clone() for k, v in self.G.state_dict().items()}
        self.best["D"] = {k: v.detach().cpu().clone() for k, v in self.D.state_dict().items()}

    def load_best(self):
        if self.best["G"] is not None and self.best["D"] is not None:
            self.G.load_state_dict(self.best["G"])
            self.D.load_state_dict(self.best["D"])

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
        gaps = deque(maxlen=(early_cfg['gap_window'] if early_cfg else 500))
        eval_history = []
        plateau = 0
        stable_gap = 0
        last_tstr = None
        drop_count = 0

        for ep in range(1, epochs + 1):
            if user_pressed_q_nonblocking():
                print("[INFO] Stop solicitado pelo usuário ('q'). Encerrando treino antecipadamente.", flush=True)
                break

            # reset métricas do último batch da época
            last_d_loss = float('nan')
            last_g_loss = float('nan')
            last_d_real = float('nan')
            last_d_fake = float('nan')
            last_gap = float('nan')

            batches = 0
            for x_real, y_idx in loader:
                batches += 1
                if user_pressed_q_nonblocking():
                    print("[INFO] Stop solicitado pelo usuário ('q'). Encerrando treino antecipadamente.", flush=True)
                    ep = epochs  # forçar saída
                    break

                x_real = x_real.to(self.device)
                y_idx = y_idx.to(self.device)
                y_oh = onehot(y_idx, n_classes)

                x_real = torch.nan_to_num(x_real, nan=0.0, posinf=1.0, neginf=0.0)

                # Passos do crítico
                for _ in range(self.n_critic if self.n_critic > 0 else 1):
                    z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                    with torch.no_grad():
                        x_fake = self.G(z, y_oh)
                    xr = self._add_instance_noise(x_real)
                    xf = self._add_instance_noise(x_fake)
                    d_real = self.D(xr, y_oh).mean()
                    d_fake = self.D(xf, y_oh).mean()
                    gp = self.gradient_penalty(xr, xf, y_oh)
                    d_loss = -(d_real - d_fake) + self.gp_lambda * gp
                    self.opt_D.zero_grad(set_to_none=True)
                    d_loss.backward()
                    self.opt_D.step()

                    last_d_loss = float(d_loss.item())
                    last_d_real = float(d_real.item())
                    last_d_fake = float(d_fake.item())

                # Passo do gerador
                z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                x_gen = self.G(z, y_oh)
                xg = self._add_instance_noise(x_gen)
                g_loss = -self.D(xg, y_oh).mean()
                self.opt_G.zero_grad(set_to_none=True)
                g_loss.backward()
                self.opt_G.step()

                last_g_loss = float(g_loss.item())
                last_gap = float(last_d_real - last_d_fake)
                gaps.append(last_gap)

            if batches == 0:
                print("[ERROR] DataLoader não gerou batches (tamanho do dataset < batch-size?). Ajuste --batch-size ou verifique os dados.")
                break

            # LOG
            if (ep % log_every == 0) or (ep == 1):
                gap_ma = float(np.mean(gaps)) if len(gaps) else float('nan')
                def fmt(x): 
                    return ("n/a" if (x != x) else f"{x:.4f}")
                print(f"[{ep:04d}/{epochs}] D_loss={fmt(last_d_loss)}  G_loss={fmt(last_g_loss)}  "
                      f"D(real)={fmt(last_d_real)} D(fake)={fmt(last_d_fake)}  gap={fmt(last_gap)} gap_ma={fmt(gap_ma)}",
                      flush=True)

            # EVAL
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

                # --- salvar melhor por TSTR
                cur_tstr = metrics.get("tstr_macro_f1", None)
                if cur_tstr is not None and not np.isnan(cur_tstr):
                    if (self.best["tstr"] is None) or (cur_tstr > self.best["tstr"]):
                        self._save_best(ep, cur_tstr)

                # --- lógica de early stop
                if early_cfg:
                    tol = early_cfg.get("tstr_tol", 0.1) / 100.0   # pp -> fração
                    drop_pp = early_cfg.get("tstr_drop", 2.0) / 100.0
                    pat = early_cfg.get("patience", 2)
                    pat_drop = early_cfg.get("patience_drop", 2)
                    min_ep = early_cfg.get("min_epochs", 1500)

                    # plateau vs best
                    if (self.best["tstr"] is None) or (cur_tstr is None) or np.isnan(cur_tstr):
                        plateau = 0
                    else:
                        plateau = 0 if (cur_tstr - self.best["tstr"]) > tol else plateau + 1

                    # queda consecutiva vs última avaliação
                    if (last_tstr is not None) and (cur_tstr is not None) and not np.isnan(cur_tstr):
                        drop_count = (drop_count + 1) if (cur_tstr < last_tstr - drop_pp) else 0
                    else:
                        drop_count = 0
                    last_tstr = cur_tstr

                    # estabilidade do gap
                    if (gap_ma == gap_ma) and (early_cfg.get("gap_low", 0.05) <= gap_ma <= early_cfg.get("gap_high", 0.30)):
                        stable_gap += 1
                    else:
                        stable_gap = 0

                    if (ep >= min_ep) and ((plateau >= pat) or (drop_count >= pat_drop)) and (stable_gap >= pat):
                        print(f"[EARLY STOP] Plateau (≥{pat}) ou Queda de TSTR (>{early_cfg.get('tstr_drop', 2.0)}pp por ≥{pat_drop}) "
                              f"com gap_ma estável ({gap_ma:.3f}). Ep={ep}", flush=True)
                        break

                # PRINT métricas
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
    ap = argparse.ArgumentParser(description="Hybrid SMOTE + cWGAN-GP (v013_defaults_plus: TSTR-early, histograma, GOLDEN, MinMax, inteiros/0..10)")
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
    ap.add_argument("--smote-target", type=int, default=2400, help="Tamanho alvo após oversampling (padrão 2400).")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--z-dim", type=int, default=128)
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--gp-lambda", type=float, default=10.0)
    ap.add_argument("--n-critic", type=int, default=8)
    ap.add_argument("--lrG", type=float, default=2.5e-4)
    ap.add_argument("--lrD", type=float, default=4e-5)
    ap.add_argument("--inst-noise", type=float, default=0.05,
                    help="Desvio-padrão do ruído gaussiano (instance noise) aplicado às entradas do D.")
    ap.add_argument("--eval-every", type=int, default=250,
                    help="Frequência (épocas) para rodar avaliação TSTR/KS/correlação durante o treino (0 desativa).")
    ap.add_argument("--early-patience", type=int, default=2,
                    help="Número de avaliações sem melhora significativa (plateau) para parar.")
    ap.add_argument("--gap-window", type=int, default=500,
                    help="Janela da média móvel do gap de Wasserstein (D(real)-D(fake)).")
    ap.add_argument("--gap-stable-low", type=float, default=0.05,
                    help="Limite inferior para considerar o gap médio estável.")
    ap.add_argument("--gap-stable-high", type=float, default=0.30,
                    help="Limite superior para considerar o gap médio estável.")
    ap.add_argument("--tstr-tol", type=float, default=0.1,
                    help="Variação mínima (em pontos percentuais) no TSTR macro-F1 para considerar melhora.")
    ap.add_argument("--tstr-drop", type=float, default=2.0,
                    help="Queda máxima de TSTR (em pp) tolerada entre avaliações antes de contar como 'queda'.")
    ap.add_argument("--patience-drop", type=int, default=2,
                    help="Número de avaliações consecutivas com queda para parar.")
    ap.add_argument("--min-epochs-early", type=int, default=1500,
                    help="Épocas mínimas antes de permitir parada antecipada.")
    ap.add_argument("--save-excel-report", action=argparse.BooleanOptionalAction, default=True,
                    help="Salvar planilha com abas de saída ('REPORT', 'EVAL_HISTORY', etc.).")
    ap.add_argument("--out", type=str, default=None, help="Arquivo Excel de saída (default: gera com timestamp).")
    ap.add_argument("--drop-nao", action=argparse.BooleanOptionalAction, default=True,
                    help="Remove linhas cujo alvo seja 'não/nao' (desconhecido) do treino/avaliação.")
    ap.add_argument("--impute", type=str, choices=["median","zero"], default="median",
                    help="Estratégia de imputação para NaNs nas features numéricas.")
    ap.add_argument("--golden-only", action=argparse.BooleanOptionalAction, default=True,
                    help="Usa APENAS as features presentes em 'Pontuação' com soma != 0 (regra de ouro).")
    ap.add_argument("--round-on-save", action=argparse.BooleanOptionalAction, default=True,
                    help="Ao salvar sintético, arredonda binárias e inteiros (0..10) na escala original.")

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

    df_full = pd.read_excel(in_path, sheet_name=sheet).copy()

    # Carrega Pontuação se houver
    pontos_df = None
    if "Pontuação" in xls.sheet_names:
        try:
            pontos_df = pd.read_excel(in_path, sheet_name="Pontuação")
            print("[INFO] Aba 'Pontuação' encontrada.")
        except Exception:
            pontos_df = None
    else:
        print("[WARN] Aba 'Pontuação' não encontrada; 'golden-only' não poderá ser aplicado totalmente.")

    # Drop 'não/nao' (desconhecido), se habilitado
    if args.drop_nao:
        tgt_norm0 = _normalize_series_text(df_full[target])
        drop_mask0 = tgt_norm0.eq("nao") | tgt_norm0.eq("não") | tgt_norm0.eq("nao/nao") | tgt_norm0.eq("nao / nao")
        if drop_mask0.any():
            before0 = len(df_full)
            df_full = df_full.loc[~drop_mask0].copy()
            removed0 = before0 - len(df_full)
            print(f"[INFO] Removidas {removed0} linhas com alvo 'não/nao'.")

    # ---------- GOLDEN-ONLY ----------
    features_not_in_pont = []
    features_zero_in_pont = []
    features_kept_golden = []
    if args.golden_only and pontos_df is not None:
        numeric_cols_all = df_full.select_dtypes(include=[np.number]).columns.tolist()
        if target in numeric_cols_all:
            numeric_cols_all.remove(target)
        common = [c for c in pontos_df.columns if c in numeric_cols_all and c != target]

        for c in common:
            s = pd.to_numeric(pontos_df[c], errors='coerce').fillna(0.0)
            if float(s.abs().sum()) == 0.0:
                features_zero_in_pont.append(c)
            else:
                features_kept_golden.append(c)

        features_not_in_pont = [c for c in numeric_cols_all if c not in common]

        df_full = df_full.drop(columns=features_not_in_pont + features_zero_in_pont, errors='ignore')
        print(f"[INFO] GOLDEN-ONLY ativo.")
        print(f"       - Numéricas totais: {len(numeric_cols_all)}")
        print(f"       - Em Pontuação: {len(common)}")
        print(f"       - Mantidas (Pontuação soma != 0): {len(features_kept_golden)}")
        print(f"       - Excluídas (não estão na Pontuação): {len(features_not_in_pont)}")
        print(f"       - Excluídas (Pontuação soma == 0): {len(features_zero_in_pont)}")
        if features_kept_golden[:10]:
            print("       - Mantidas (amostra):", features_kept_golden[:10])

    # Contagem por classe e remoção de raras
    counts_full = df_full[target].value_counts().sort_index()
    print("[INFO] Contagem por classe (após pré-processamento):")
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

    # Seleciona colunas numéricas como features (após GOLDEN-ONLY)
    num_cols = df_full.select_dtypes(include=[np.number]).columns.tolist()
    if target in num_cols:
        num_cols.remove(target)
    feat_cols = [c for c in num_cols if c != target]
    if len(feat_cols) == 0:
        raise ValueError("Nenhuma feature numérica encontrada após aplicar a regra GOLDEN-ONLY. Verifique a aba 'Pontuação'.")

    # Imputação
    df_full = impute_numeric(df_full, feat_cols, strategy=args.impute)

    # Detecta tipos (binária / smallint / real) na base inteira (pós-imputação)
    feat_types = detect_feature_types(df_full, feat_cols)
    n_binary = sum(1 for t in feat_types.values() if t == "binary")
    n_smallint = sum(1 for t in feat_types.values() if t == "smallint")
    n_real = sum(1 for t in feat_types.values() if t == "real")
    print(f"[INFO] Tipos de features: binary={n_binary}  smallint(0..10)={n_smallint}  real={n_real}")

    # Split
    if args.half_split:
        train_mask = per_class_split(df_full, target, perc=args.split_perc, seed=args.seed)
        df_train = df_full.loc[train_mask].copy()
        df_holdout = df_full.loc[~train_mask].copy()
        print(f"[INFO] Half-split ({args.split_perc:.1f}% por classe): train={len(df_train)}  holdout={len(df_holdout)}")
    else:
        df_train = df_full.copy()
        df_holdout = None

    # Tabelas originais (antes do scaling) para salvar/avaliar
    X_train_orig = df_train[feat_cols].to_numpy(dtype=np.float32)
    y_train = df_train[target].astype(str).str.strip().values
    if df_holdout is not None and len(df_holdout) > 0:
        X_eval_orig = df_holdout[feat_cols].to_numpy(dtype=np.float32)
        y_eval_idx = pd.Series(df_holdout[target]).astype(str).map({c:i for i,c in enumerate(sorted(df_train[target].astype(str).unique()))}).to_numpy(dtype=np.int64)
    else:
        X_eval_orig = None
        y_eval_idx = None

    # Escala MinMax em [0,1] com base no TREINO
    scaler = MinMaxPerFeature().fit(X_train_orig, feat_cols)
    X_all = scaler.transform(X_train_orig).astype(np.float32)

    # Alvo e classes
    classes = sorted(pd.Series(y_train).unique())
    label_to_idx = {c: i for i, c in enumerate(classes)}
    y_all = pd.Series(y_train).map(label_to_idx).to_numpy(dtype=np.int64)
    n_classes = len(classes)
    print(f"[INFO] Found {n_classes} classes após remoções: {classes}")
    print(f"[INFO] Features finais: {len(feat_cols)}")

    # Oversampling (feita no conjunto de treino)
    X_sm, y_sm, over_used = fit_resample_balanced(X_all, y_all, n_classes, seed=args.seed, target_total=args.smote_target)
    print(f"[INFO] SMOTE: {len(X_all)} -> {len(X_sm)} rows (training set) [{over_used}]")

    # DataLoader
    ds = TabularDataset(X_sm, y_sm)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=False)

    # Se não tem holdout, carve-out 20% APENAS para avaliação, sem tocar no loader
    if df_holdout is None:
        eval_frac = 0.20
        counts = np.bincount(y_all, minlength=n_classes)
        can_strat = (counts.min() >= 2 and np.all(counts * eval_frac >= 1) and np.all(counts * (1.0 - eval_frac) >= 1))
        if not can_strat:
            print("[WARN] Classe com <=1 amostra ou fração insuficiente; split aleatório SEM estratificar.")
        X_tr_o, X_eval_orig, y_tr_i, y_eval_idx = train_test_split(
            X_train_orig, y_all,
            test_size=eval_frac,
            random_state=args.seed,
            stratify=(y_all if can_strat else None),
        )
        # Avaliação usa X_eval_orig/y_eval_idx; treino segue com X_sm/y_sm

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

    # Distribuição alvo para amostragem de y na avaliação
    if (y_eval_idx is not None) and (len(y_eval_idx) > 0):
        counts_real_eval = np.bincount(y_eval_idx, minlength=n_classes).astype(float)
        p_real = counts_real_eval / max(counts_real_eval.sum(), 1.0)
    else:
        p_real = None
    counts_sm = np.bincount(y_sm, minlength=n_classes).astype(float)
    p_sm = counts_sm / max(counts_sm.sum(), 1.0)

    def round_back_to_types(Xorig: np.ndarray):
        """Arredonda conforme tipo: binária -> {0,1}; smallint -> int 0..10; real -> sem alteração."""
        Xr = Xorig.copy()
        for j, c in enumerate(feat_cols):
            t = feat_types.get(c, "real")
            if t == "binary":
                Xr[:, j] = (Xr[:, j] >= 0.5).astype(np.float32)
            elif t == "smallint":
                Xr[:, j] = np.clip(np.round(Xr[:, j]), 0, 10).astype(np.float32)
            else:
                pass
        return Xr

    def _eval_fn(m: 'CWGAN_GP'):
        if (X_eval_orig is None) or (len(X_eval_orig) == 0):
            return {}

        p_use = p_real if (p_real is not None) else p_sm
        n_syn = min(len(X_eval_orig), 5000) if len(X_eval_orig) > 0 else 1000
        y_idx_syn = np.random.choice(np.arange(n_classes), size=n_syn, replace=True, p=p_use)
        y_idx_syn_t = torch.tensor(y_idx_syn, dtype=torch.long, device=m.device)
        X_syn_s, Y_syn = m.sample(n_syn, y_idx=y_idx_syn_t, n_classes=n_classes)

        # volta para escala original
        X_syn_orig = scaler.inverse_transform(X_syn_s)
        X_syn_orig = np.nan_to_num(X_syn_orig, nan=0.0, posinf=0.0, neginf=0.0)
        X_syn_orig = round_back_to_types(X_syn_orig)

        # TSTR
        scaler_t = StandardScaler().fit(X_syn_orig)
        Xtr = scaler_t.transform(X_syn_orig)
        Xte = scaler_t.transform(X_eval_orig)
        clf = LogisticRegression(max_iter=300, multi_class="auto")
        try:
            clf.fit(Xtr, Y_syn)
            y_pred = clf.predict(Xte)
            tstr_macro_f1 = f1_score(y_eval_idx, y_pred, average="macro")
        except Exception as e:
            print(f"[WARN] TSTR falhou: {e}")
            tstr_macro_f1 = float('nan')

        # Baseline real→real
        try:
            scaler_b = StandardScaler().fit(X_train_orig)
            Xtr_b = scaler_b.transform(X_train_orig)
            Xte_b = scaler_b.transform(X_eval_orig)
            y_all_idx = pd.Series(y_train).map(label_to_idx).to_numpy(dtype=np.int64)
            clf_b = LogisticRegression(max_iter=300, multi_class="auto").fit(Xtr_b, y_all_idx)
            yb = clf_b.predict(Xte_b)
            baseline_macro_f1 = f1_score(y_eval_idx, yb, average="macro")
        except Exception as e:
            print(f"[WARN] Baseline real→real falhou: {e}")
            baseline_macro_f1 = float('nan')

        tstr_ratio = float(tstr_macro_f1 / baseline_macro_f1) if (baseline_macro_f1 == baseline_macro_f1 and baseline_macro_f1 > 0) else float('nan')

        # KS e correlação
        try:
            ks_df = ks_report(X_eval_orig, X_syn_orig, feat_cols)
            ks_median = float(ks_df["ks_stat"].median()) if not ks_df.empty else float('nan')
        except Exception:
            ks_median = float('nan')
        try:
            corr_fro = corr_gap(X_eval_orig, X_syn_orig)
        except Exception:
            corr_fro = float('nan')

        # Proporções de classe
        try:
            real_p = counts_real_eval / max(counts_real_eval.sum(), 1.0) if (p_real is not None) else None
            syn_p = np.bincount(Y_syn, minlength=n_classes).astype(float); syn_p /= max(syn_p.sum(), 1.0)
            if real_p is not None:
                class_diff = np.abs(real_p - syn_p)
                class_diff_mean = float(class_diff.mean())
                class_diff_max  = float(class_diff.max())
            else:
                class_diff_mean = float('nan')
                class_diff_max = float('nan')
        except Exception:
            class_diff_mean = float('nan')
            class_diff_max = float('nan')

        out = {
            "tstr_macro_f1": float(tstr_macro_f1),
            "baseline_macro_f1": float(baseline_macro_f1),
            "tstr_ratio": float(tstr_ratio),
            "ks_median": ks_median,
            "corr_gap_fro": float(corr_fro),
            "class_diff_mean": float(class_diff_mean),
            "class_diff_max": float(class_diff_max)
        }
        return out

    early_cfg = dict(
        patience=args.early_patience,
        gap_window=args.gap_window,
        gap_low=args.gap_stable_low,
        gap_high=args.gap_stable_high,
        tstr_tol=args.tstr_tol,
        min_epochs=args.min_epochs_early,
        tstr_drop=args.tstr_drop,
        patience_drop=args.patience_drop
    )

    eval_history = model.train(
        loader, n_classes=n_classes, epochs=args.epochs, log_every=args.log_every,
        eval_every=args.eval_every, eval_fn=_eval_fn, early_cfg=early_cfg
    )

    # --------- Saída ---------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = args.out if args.out else f"banco_dados_sintetico_{ts}.xlsx"

    # Restaura o melhor checkpoint por TSTR antes de gerar sintéticos finais
    model.load_best()

    # Amostra final de sintéticos balanceados (em [0,1] -> original + arredondamento)
    n_final = len(X_train_orig)
    y_idx_final = np.random.choice(np.arange(n_classes), size=n_final, replace=True, p=(p_sm if p_sm is not None else None))
    y_idx_final_t = torch.tensor(y_idx_final, dtype=torch.long, device=model.device)
    X_syn_s_final, Y_syn_final = model.sample(n_final, y_idx=y_idx_final_t, n_classes=n_classes)
    X_syn_orig_final = scaler.inverse_transform(X_syn_s_final)
    X_syn_orig_final = np.nan_to_num(X_syn_orig_final, nan=0.0, posinf=0.0, neginf=0.0)
    # arredondamento conforme tipos
    def round_back_to_types(Xorig: np.ndarray):
        Xr = Xorig.copy()
        for j, c in enumerate(feat_cols):
            t = feat_types.get(c, "real")
            if t == "binary":
                Xr[:, j] = (Xr[:, j] >= 0.5).astype(np.float32)
            elif t == "smallint":
                Xr[:, j] = np.clip(np.round(Xr[:, j]), 0, 10).astype(np.float32)
        return Xr
    X_syn_orig_final = round_back_to_types(X_syn_orig_final)

    df_syn = pd.DataFrame(X_syn_orig_final, columns=feat_cols)
    df_syn[target] = pd.Series(Y_syn_final).map({v:k for k,v in label_to_idx.items()})

    with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
        df_train_out = df_train.copy()
        df_train_out.to_excel(writer, index=False, sheet_name="DATA_TRAIN")
        if df_holdout is not None and len(df_holdout) > 0:
            df_holdout.to_excel(writer, index=False, sheet_name="DATA_HOLDOUT")
        df_syn.to_excel(writer, index=False, sheet_name="DATA_SYNTH")

        if pontos_df is not None:
            pontos_df.to_excel(writer, index=False, sheet_name="Pontuação")
        if excluded_rare_df is not None and len(excluded_rare_df) > 0:
            excluded_rare_df.to_excel(writer, index=False, sheet_name="DATA_EXCLUDED_RARE")

        pd.DataFrame({"features_kept_golden": features_kept_golden}).to_excel(writer, index=False, sheet_name="FEATURES_GOLDEN_KEPT")
        if features_zero_in_pont:
            pd.DataFrame({"features_zero_in_pont": features_zero_in_pont}).to_excel(writer, index=False, sheet_name="FEATURES_DROPPED_ZERO")
        if features_not_in_pont:
            pd.DataFrame({"features_not_in_pont": features_not_in_pont}).to_excel(writer, index=False, sheet_name="FEATURES_EXCLUDED_NOT_IN_PONT")

        pd.DataFrame({"feature": feat_cols, "type": [feat_types[c] for c in feat_cols]}).to_excel(writer, index=False, sheet_name="FEATURE_TYPES")
        mm_info = pd.DataFrame({"feature": scaler.cols, "min": scaler.min_, "max": scaler.max_, "range": scaler.range_})
        mm_info.to_excel(writer, index=False, sheet_name="MINMAX_PARAMS")

        rep = pd.DataFrame({
            "metric": ["n_classes", "train_rows", "holdout_rows", "smote_rows", "device", "oversampler", "feat_final", "best_tstr_epoch", "best_tstr_macro_f1"],
            "value": [len(classes), len(df_train), 0 if df_holdout is None else len(df_holdout), len(X_sm), ("cuda" if torch.cuda.is_available() else "cpu"), "SMOTE/ROS", len(feat_cols), 
                      (model.best["epoch"] if model.best["epoch"] is not None else "n/a"),
                      (f"{model.best['tstr']*100:.2f}%" if model.best["tstr"] is not None else "n/a")]
        })
        rep.to_excel(writer, index=False, sheet_name="REPORT")
        try:
            hist_df = pd.DataFrame(eval_history)
            if not hist_df.empty:
                hist_df.to_excel(writer, index=False, sheet_name="EVAL_HISTORY")
        except Exception as e:
            print(f"[WARN] Não foi possível salvar EVAL_HISTORY: {e}")

    print(f"[INFO] Arquivo salvo em: {os.path.abspath(out_xlsx)}")

if __name__ == "__main__":
    main()