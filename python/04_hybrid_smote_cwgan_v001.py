
"""
Hybrid Data Augmentation for Small Tabular Clinical Data
(After Wang & Pai, 2023: Hybrid SMOTE + WCGAN-GP)

- Step 1 (SMOTE): Upsample each class to a minimum training size for stable GAN training.
- Step 2 (cWGAN-GP): Train a conditional WGAN-GP on the SMOTE-augmented dataset.
- Step 3 (Generation): Sample exactly N synthetic rows per class (e.g., 50).
- Optional Post-processing:
    * CDF match per feature (monotone rank mapping) to better align marginals.
    * Privacy filter: drop synthetic rows too close to any original row (L2 min distance).

Assumptions:
- Input sheet TDados_clean; values in [0, 1] for numerical features.
- Target column is categorical (string or numeric class id). Only numerical features (excluding target) are used as X.

Usage examples:
    python hybrid_smote_cwgan.py --excel Banco_dados.xlsx --sheet TDados_clean --target alvo \
        --per-class-count 50 --smote-min-per-class 200 --balance --cdf-match --ignore-labels "nao,não,desconhecido"

Install (if needed):
    pip install pandas numpy scikit-learn imbalanced-learn torch openpyxl

Outputs:
- pacientes_virtuais_hybrid_<timestamp>.xlsx    (synthetic data with target column first)
- hybrid_aug_report_<timestamp>.csv             (KS tests, correlation gap, C2ST AUC, privacy stats)
"""
import os
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

import argparse
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.utils import check_random_state
from scipy.stats import ks_2samp

import torch
import torch.nn as nn
import torch.autograd as autograd
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from imblearn.over_sampling import SMOTE, RandomOverSampler


# -----------------------------
# Utils
# -----------------------------

def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def find_excel_case_insensitive(path_str: str) -> Path:
    p = Path(path_str)
    if p.exists():
        return p
    if p.parent.exists():
        stem_lower = p.stem.lower()
        for child in p.parent.iterdir():
            if child.suffix.lower() in ('.xlsx', '.xls'):
                if child.stem.lower() == stem_lower:
                    return child
    alt = p.with_name(p.name.lower())
    if alt.exists():
        return alt
    return p

def onehot(idx: torch.Tensor, n_classes: int) -> torch.Tensor:
    oh = torch.zeros((idx.size(0), n_classes), device=idx.device)
    oh.scatter_(1, idx.view(-1,1), 1.0)
    return oh

def cdf_match_column(x_synth: np.ndarray, x_real: np.ndarray) -> np.ndarray:
    """Monotone rank-based mapping of synthetic to real marginal distribution."""
    n = len(x_synth)
    if len(x_real) < 2 or n == 0:
        return x_synth
    # ranks in [0,1]
    ranks = (pd.Series(x_synth).rank(method='average') - 0.5) / len(x_synth)
    # quantile mapping using real
    q = np.quantile(x_real, ranks, method='linear')
    return q

def privacy_filter(X_synth: np.ndarray, X_real: np.ndarray, min_nn_dist: float) -> np.ndarray:
    """Return boolean mask keeping only rows whose NN distance to original >= min_nn_dist."""
    if len(X_real) == 0 or len(X_synth) == 0:
        return np.ones(len(X_synth), dtype=bool)
    nbrs = NearestNeighbors(n_neighbors=1, algorithm='auto').fit(X_real)
    dists, _ = nbrs.kneighbors(X_synth, n_neighbors=1, return_distance=True)
    dists = dists.reshape(-1)
    return dists >= float(min_nn_dist)

# -----------------------------
# Conditional WGAN-GP models
# -----------------------------

class GenC(nn.Module):
    def __init__(self, z_dim: int, y_dim: int, out_dim: int, hidden=256, depth=3):
        super().__init__()
        in_dim = z_dim + y_dim
        layers = []
        h = hidden
        for _ in range(depth):
            layers += [nn.Linear(in_dim, h), nn.LeakyReLU(0.2, inplace=True)]
            in_dim = h
            h = max(h // 1, 64)
        layers += [nn.Linear(in_dim, out_dim), nn.Sigmoid()]  # ensure [0,1]
        self.net = nn.Sequential(*layers)

    def forward(self, z, y_oh):
        return self.net(torch.cat([z, y_oh], dim=1))

class CriticC(nn.Module):
    def __init__(self, x_dim: int, y_dim: int, hidden=256, depth=3):
        super().__init__()
        in_dim = x_dim + y_dim
        layers = []
        h = hidden
        for _ in range(depth):
            layers += [nn.Linear(in_dim, h), nn.LeakyReLU(0.2, inplace=True)]
            in_dim = h
            h = max(h // 1, 64)
        layers += [nn.Linear(in_dim, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, x, y_oh):
        return self.net(torch.cat([x, y_oh], dim=1))

class CWGAN_GP:
    def __init__(self, x_dim, y_dim, z_dim=64, g_hidden=256, d_hidden=256, g_depth=3, d_depth=3,
                 lr=1e-4, betas=(0.0, 0.9), n_critic=5, gp_lambda=10.0, device=None, seed=42):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        torch.manual_seed(seed)
        np.random.seed(seed)

        self.z_dim = z_dim
        self.n_critic = n_critic
        self.gp_lambda = gp_lambda
        self.G = GenC(z_dim, y_dim, x_dim, hidden=g_hidden, depth=g_depth).to(self.device)
        self.D = CriticC(x_dim, y_dim, hidden=d_hidden, depth=d_depth).to(self.device)
        self.opt_G = torch.optim.Adam(self.G.parameters(), lr=lr, betas=betas)
        self.opt_D = torch.optim.Adam(self.D.parameters(), lr=lr, betas=betas)

    def gradient_penalty(self, x_real, x_fake, y_oh):
        bs = x_real.size(0)
        alpha = torch.rand(bs, 1, device=self.device).expand_as(x_real)
        inter = alpha * x_real + (1 - alpha) * x_fake
        inter.requires_grad_(True)
        out = self.D(inter, y_oh)
        grad_outputs = torch.ones_like(out, device=self.device)
        grads = autograd.grad(outputs=out, inputs=inter, grad_outputs=grad_outputs,
                              create_graph=True, retain_graph=True, only_inputs=True)[0]
        grads = grads.view(bs, -1)
        return ((grads.norm(2, dim=1) - 1) ** 2).mean()

    @torch.no_grad()
    def sample(self, n, y_idx=None, n_classes=None):
        device = self.device
        if y_idx is None:
            assert n_classes is not None, "n_classes required when y_idx not provided."
            y_idx = torch.randint(0, n_classes, (n,), device=device)
        else:
            y_idx = y_idx.to(device)
        y_oh = onehot(y_idx, n_classes if n_classes is not None else int(y_idx.max().item()+1))
        z = torch.randn(n, self.z_dim, device=device)
        x = self.G(z, y_oh).clamp(0, 1)
        return x.cpu().numpy(), y_idx.cpu().numpy()

    def train(self, loader, n_classes, epochs=2000, log_every=100):
        for ep in range(1, epochs+1):
            for x_real, y_idx in loader:
                x_real = x_real.to(self.device)
                y_idx = y_idx.to(self.device)
                y_oh = onehot(y_idx, n_classes)

                # Critic steps
                for _ in range(self.n_critic):
                    z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                    with torch.no_grad():
                        x_fake = self.G(z, y_oh)
                    d_real = self.D(x_real, y_oh).mean()
                    d_fake = self.D(x_fake, y_oh).mean()
                    gp = self.gradient_penalty(x_real, x_fake, y_oh)
                    d_loss = -(d_real - d_fake) + self.gp_lambda * gp

                    self.opt_D.zero_grad(set_to_none=True)
                    d_loss.backward()
                    self.opt_D.step()

                # Generator step
                z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                x_gen = self.G(z, y_oh)
                g_loss = -self.D(x_gen, y_oh).mean()

                self.opt_G.zero_grad(set_to_none=True)
                g_loss.backward()
                self.opt_G.step()

            if ep % log_every == 0 or ep == 1:
                print(f"[{ep:04d}/{epochs}] D_loss={d_loss.item():.4f}  G_loss={g_loss.item():.4f}  "
                      f"D(real)={d_real.item():.4f} D(fake)={d_fake.item():.4f}", flush=True)

# -----------------------------
# Data pipeline
# -----------------------------

def load_tabular(excel_path: Path, sheet: str, target: str, ignore_labels: str, return_full_df=False):
    df = pd.read_excel(excel_path, sheet_name=sheet).copy()
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found in sheet '{sheet}'.")

    y_raw = df[target].astype(str).str.strip()
    if ignore_labels:
        ignore = {s.strip().lower() for s in ignore_labels.split(",") if s.strip()}
        keep_mask = ~y_raw.str.lower().isin(ignore)
        df = df.loc[keep_mask]
        y_raw = y_raw.loc[keep_mask]

    # Only numeric features EXCLUDING target
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target in num_cols:
        num_cols.remove(target)
    X_df = df[num_cols].copy()

    # drop any rows with NaN in X
    nan_mask = X_df.isna().any(axis=1)
    if nan_mask.any():
        X_df = X_df.loc[~nan_mask]
        y_raw = y_raw.loc[X_df.index]

    X = np.clip(X_df.to_numpy(dtype=np.float32), 0.0, 1.0)
    classes = sorted(y_raw.unique().tolist())
    label_to_idx = {lbl: i for i, lbl in enumerate(classes)}
    y = y_raw.map(label_to_idx).to_numpy(dtype=np.int64)

    if return_full_df:
        return df, X_df.columns.tolist(), X, y, classes, label_to_idx
    else:
        return X_df.columns.tolist(), X, y, classes, label_to_idx


def per_class_half_split(df_filtered, target, seed=42):
    """Return train_mask (bool array) selecting 50% per class (ceil if odd)."""
    rng = np.random.RandomState(seed)
    y = df_filtered[target].astype(str).str.strip().to_numpy()
    idx_all = np.arange(len(df_filtered))
    train_mask = np.zeros(len(df_filtered), dtype=bool)
    # group by class
    classes = pd.Series(y).unique().tolist()
    for c in classes:
        cls_idx = idx_all[y == c]
        if len(cls_idx) == 0:
            continue
        rng.shuffle(cls_idx)
        k = len(cls_idx)//2 + (1 if len(cls_idx)%2==1 else 0)  # 50% (+1 if odd)
        sel = cls_idx[:k]
        train_mask[sel] = True
    return train_mask

def run_smote(X: np.ndarray, y: np.ndarray, n_classes: int,
              min_per_class: int, k_neighbors: int, random_state: int):
    """Upsample para pelo menos min_per_class por classe.
       1) Se alguma classe tiver só 1 amostra, faz bootstrap p/ 2 com RandomOverSampler.
       2) Depois aplica SMOTE nas classes elegíveis (>=2 amostras).
    """
    counts = np.bincount(y, minlength=n_classes)

    # 1) Pré-bootstrap: classes com 1 amostra
    need_bootstrap = {ci: 2 for ci, cnt in enumerate(counts)
                      if cnt == 1 and max(int(min_per_class), int(cnt)) > cnt}
    X_work, y_work = X, y
    if need_bootstrap:
        ros = RandomOverSampler(sampling_strategy=need_bootstrap, random_state=random_state)
        X_work, y_work = ros.fit_resample(X_work, y_work)
        counts = np.bincount(y_work, minlength=n_classes)

    # 2) Estratégia de SMOTE apenas p/ classes com >=2 amostras
    strategy = {}
    for ci, cnt in enumerate(counts):
        target_cnt = max(int(min_per_class), int(cnt))
        if cnt >= 2 and target_cnt > cnt:
            strategy[ci] = target_cnt

    if not strategy:
        return X_work.astype(np.float32), y_work.astype(np.int64)

    eligible_counts = [cnt for cnt in counts if cnt >= 2]
    min_class_count = int(min(eligible_counts)) if eligible_counts else 2
    k_eff = max(1, min(int(k_neighbors), min_class_count - 1))

    sm = SMOTE(sampling_strategy=strategy, k_neighbors=k_eff, random_state=random_state)
    X_sm, y_sm = sm.fit_resample(X_work, y_work)
    return X_sm.astype(np.float32), y_sm.astype(np.int64)

# -----------------------------
# Evaluation helpers
# -----------------------------

def ks_report(X_real: np.ndarray, X_syn: np.ndarray, feat_cols):
    rows = []
    for j, name in enumerate(feat_cols):
        ks = ks_2samp(X_real[:, j], X_syn[:, j])
        rows.append({"feature": name, "ks_stat": float(ks.statistic), "ks_pvalue": float(ks.pvalue)})
    return pd.DataFrame(rows)

def corr_gap(X_real: np.ndarray, X_syn: np.ndarray):
    # Pearson correlation gap (Frobenius norm of difference)
    if X_real.shape[1] < 2:
        return np.nan
    C_r = np.corrcoef(X_real, rowvar=False)
    C_s = np.corrcoef(X_syn, rowvar=False)
    gap = np.linalg.norm(C_r - C_s, ord='fro')
    return float(gap)

def c2st_auc(X_real: np.ndarray, X_syn: np.ndarray, seed=42):
    # Classifier Two-Sample Test using Logistic Regression
    rng = check_random_state(seed)
    n_r = len(X_real); n_s = len(X_syn)
    n = min(n_r, n_s)
    if n < 50:
        return np.nan
    Xr = X_real[rng.choice(n_r, n, replace=False)]
    Xs = X_syn[rng.choice(n_s, n, replace=False)]
    X_all = np.vstack([Xr, Xs])
    y_all = np.hstack([np.zeros(n), np.ones(n)])
    Xtr, Xte, ytr, yte = train_test_split(X_all, y_all, test_size=0.3, random_state=seed, stratify=y_all)
    scaler = StandardScaler().fit(Xtr)
    Xtr = scaler.transform(Xtr); Xte = scaler.transform(Xte)
    clf = LogisticRegression(max_iter=200)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:,1]
    return float(roc_auc_score(yte, proba))

# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    # Parâmetros principais
    ap.add_argument("--excel", type=str, default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx",
                    help="Caminho do arquivo Excel de entrada (padrão: Banco_dados.xlsx).")
    ap.add_argument("--sheet", type=str, default="TDados",
                    help="Nome da planilha (aba) no Excel a ser usada (padrão: TDados).")
    ap.add_argument("--target", type=str, default="Alvo",
                    help="Nome da coluna alvo (classe) usada para condicionamento (padrão: Alvo).")
    ap.add_argument("--ignore-labels", type=str, default="nao,não,desconhecido",
                    help="Lista de rótulos a ignorar no treino, separados por vírgula (padrão: 'nao,não,desconhecido').")
    ap.add_argument("--epochs", type=int, default=5000,
                    help="Número de épocas de treinamento do modelo GAN (padrão: 15000).")
    ap.add_argument("--batch-size", type=int, default=256,
                    help="Tamanho do lote (batch) para treinamento (padrão: 256).")
    ap.add_argument("--z-dim", type=int, default=64,
                    help="Dimensão do vetor de ruído latente usado pelo gerador (padrão: 64).")
    ap.add_argument("--g-hidden", type=int, default=256,
                    help="Número de neurônios na camada oculta do gerador (padrão: 256).")
    ap.add_argument("--d-hidden", type=int, default=256,
                    help="Número de neurônios na camada oculta do discriminador/critic (padrão: 256).")
    ap.add_argument("--g-depth", type=int, default=3,
                    help="Número de camadas ocultas no gerador (padrão: 3).")
    ap.add_argument("--d-depth", type=int, default=3,
                    help="Número de camadas ocultas no discriminador/critic (padrão: 3).")
    ap.add_argument("--n-critic", type=int, default=10,
                    help="Número de passos de treino do critic por passo do gerador (padrão: 5).")
    ap.add_argument("--gp-lambda", type=float, default=10.0,
                    help="Coeficiente da penalização de gradiente (Gradient Penalty) no WGAN-GP (padrão: 10.0).")
    ap.add_argument("--log-every", type=int, default=100,
                    help="Frequência (em épocas) para exibir logs durante o treinamento (padrão: 100).")

    # Divisão de treino/holdout
    ap.add_argument("--no-half-split", action="store_false", dest="half_split",
                    help="Desativa o uso padrão do half-split (que é 50%+1 por classe).")
    ap.set_defaults(half_split=True)

    ap.add_argument("--save-excel-report", action="store_true",
                    help="Inclui o relatório de métricas (KS, correlação, privacidade) como aba extra no Excel de saída.")

    # Controle do SMOTE
    ap.add_argument("--smote-min-per-class", type=int, default=400,
                    help="Número mínimo de amostras por classe após SMOTE para estabilizar o treino do GAN (padrão: 200).")
    ap.add_argument("--smote-k", type=int, default=5,
                    help="Número de vizinhos para o SMOTE; reduzido automaticamente se necessário (padrão: 5).")
    ap.add_argument("--seed", type=int, default=42,
                    help="Semente aleatória para reprodutibilidade (padrão: 42).")

    # Controle da geração
    ap.add_argument("--per-class-count", type=int, default=50,
                    help="Número de amostras sintéticas a gerar por classe (padrão: 50).")
    ap.add_argument("--cdf-match", action="store_true",
                    help="Aplica ajuste marginal (CDF matching) por feature para alinhar com a distribuição original.")
    ap.add_argument("--min-nn-distance", type=float, default=0.07,
                    help="Distância mínima (L2) de cada amostra sintética para as reais, garantindo privacidade (padrão: 0.10).")
    ap.add_argument("--max-gen-tries", type=int, default=50,
                    help="Número máximo de tentativas de reamostragem por classe para atingir a contagem desejada (padrão: 10).")
    ap.add_argument("--balance", action="store_true",
                    help="Ativa balanceamento de classes no DataLoader durante o treino (útil para classes desbalanceadas).")
    args = ap.parse_args()

    excel_path = find_excel_case_insensitive(args.excel)
    print(f"[INFO] Reading: {excel_path} (sheet='{args.sheet}') target='{args.target}'")
    df_full, feat_cols, X_all, y_all, classes, label_to_idx = load_tabular(excel_path, args.sheet, args.target, args.ignore_labels, return_full_df=True)
        # --- tentar carregar a aba "Pontuação" do Excel original (opcional) ---
    try:
        df_pontuacao = pd.read_excel(excel_path, sheet_name="Pontuação")
        print("[INFO] Aba 'Pontuação' encontrada e será copiada para o arquivo de saída.")
    except Exception:
        df_pontuacao = None
        print("[INFO] Aba 'Pontuação' não encontrada no arquivo de entrada; ignorando cópia.")
    n_classes = len(classes)
    print(f"[INFO] Found {n_classes} classes: {classes}")

    # ------------- per-class 50% (+1) split -------------
    if args.half_split:
        train_mask = per_class_half_split(df_full, args.target, seed=args.seed)
        df_train = df_full.loc[train_mask].reset_index(drop=True)
        df_holdout = df_full.loc[~train_mask].reset_index(drop=True)
        # rebuild X,y from df_train to keep alignment after filtering
        num_cols = df_train.select_dtypes(include=[np.number]).columns.tolist()
        if args.target in num_cols:
            num_cols.remove(args.target)
        X = np.clip(df_train[num_cols].to_numpy(dtype=np.float32), 0.0, 1.0)
        y_series = df_train[args.target].astype(str).str.strip()
        y = y_series.map({lbl:i for i,lbl in enumerate(sorted(y_series.unique().tolist()))})
        # remap to original label_to_idx to keep class order consistent
        y = df_train[args.target].map(label_to_idx).to_numpy(dtype=np.int64)
        print(f"[INFO] Half-split: train={len(df_train)}  holdout={len(df_holdout)}")
    else:
        # use all filtered
        X = X_all; y = y_all
        df_holdout = None

    # ----- SMOTE upsample on training only -----
    X_sm, y_sm = run_smote(X, y, n_classes, min_per_class=args.smote_min_per_class,
                           k_neighbors=args.smote_k, random_state=args.seed)
    print(f"[INFO] SMOTE: {X.shape[0]} -> {X_sm.shape[0]} rows (training set)")

    # DataLoader
    X_t = torch.tensor(X_sm, dtype=torch.float32)
    y_t = torch.tensor(y_sm, dtype=torch.long)
    if args.balance:
        counts = np.bincount(y_sm, minlength=n_classes).astype(float)
        class_weights = (counts.sum() / np.maximum(counts, 1.0))
        weights = class_weights[y_sm]
        sampler = WeightedRandomSampler(weights=weights, num_samples=len(weights), replacement=True)
        loader = DataLoader(TensorDataset(X_t, y_t), batch_size=args.batch_size, sampler=sampler)
    else:
        loader = DataLoader(TensorDataset(X_t, y_t), batch_size=args.batch_size, shuffle=True)

    # ----- Train cWGAN-GP -----
    model = CWGAN_GP(
        x_dim=X.shape[1], y_dim=n_classes, z_dim=args.z_dim,
        g_hidden=args.g_hidden, d_hidden=args.d_hidden,
        g_depth=args.g_depth, d_depth=args.d_depth,
        n_critic=args.n_critic, gp_lambda=args.gp_lambda, seed=args.seed
    )
    model.train(loader, n_classes=n_classes, epochs=args.epochs, log_every=args.log_every)

    # ----- Generate per class with privacy filter & optional CDF match -----
    all_Xs = []
    all_Ys = []
    for name in classes:
        target_idx = label_to_idx[name]
        needed = int(args.per_class_count)
        got = 0
        tries = 0
        col_buffer = []

        # Real subset for this class for CDF match (marginal)
        idx_this = (y == target_idx)
        X_real_cls = X[idx_this] if idx_this.any() else X

        while got < needed and tries < args.max_gen_tries:
            # sample batch for this class
            batch = max(needed - got, args.batch_size)
            y_idx_tensor = torch.full((batch,), target_idx, dtype=torch.long)
            Xs, Ys = model.sample(batch, y_idx=y_idx_tensor, n_classes=n_classes)

            # privacy filter vs ORIGINAL X (not SMOTE)
            keep_mask = privacy_filter(Xs, X, min_nn_dist=args.min_nn_distance)
            Xs = Xs[keep_mask]
            Ys = Ys[keep_mask]
            if len(Xs) == 0:
                tries += 1
                continue

            # optional CDF match per feature, using real of same class (fallback all real)
            if args.cdf_match:
                Xs_adj = Xs.copy()
                for j in range(Xs.shape[1]):
                    Xs_adj[:, j] = cdf_match_column(
                        Xs[:, j],
                        X_real_cls[:, j] if len(X_real_cls) > 0 else X[:, j]
                    )
                Xs = np.clip(Xs_adj, 0, 1)


            # accumulate
            take = min(needed - got, len(Xs))
            col_buffer.append(Xs[:take])
            got += take
            tries += 1

        if got < needed:
            print(f"[WARN] Could only produce {got}/{needed} for class '{name}' with current filters.")
        if col_buffer:
            X_final = np.vstack(col_buffer)
            Y_final = np.full((X_final.shape[0],), target_idx, dtype=np.int64)
            all_Xs.append(X_final)
            all_Ys.append(Y_final)

    if not all_Xs:
        raise RuntimeError("No synthetic rows produced; try relaxing --min-nn-distance or increasing --max-gen-tries.")

    X_syn = np.vstack(all_Xs)
    Y_syn = np.concatenate(all_Ys)
    idx_to_label = {v:k for k,v in label_to_idx.items()}
    labels = [idx_to_label[int(i)] for i in Y_syn]

    df_out = pd.DataFrame(X_syn, columns=feat_cols)
    df_out.insert(0, args.target, labels)
    timestamp_str = ts()
    out_xlsx = Path(f"saida_modelo\\banco_dados_vt{timestamp_str}.xlsx").absolute()
    # garantir diretório de saída
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)

    # Build report
    ks_df = ks_report(X, X_syn, feat_cols)
    ks_df['metric'] = 'KS'
    gap = corr_gap(X, X_syn)
    auc = c2st_auc(X, X_syn)
    rep = ks_df.copy()
    rep.loc[len(rep.index)] = {"feature": "__summary_corr_gap__", "ks_stat": gap, "ks_pvalue": np.nan, "metric":"corr_gap_fro"}
    rep.loc[len(rep.index)] = {"feature": "__summary_c2st_auc__", "ks_stat": auc, "ks_pvalue": np.nan, "metric":"c2st_auc"}
    nbrs = NearestNeighbors(n_neighbors=1).fit(X)
    dists, _ = nbrs.kneighbors(X_syn)
    rep.loc[len(rep.index)] = {"feature": "__privacy_nn_mean__", "ks_stat": float(np.mean(dists)), "ks_pvalue": np.nan, "metric":"privacy_nn_mean"}
    rep.loc[len(rep.index)] = {"feature": "__privacy_nn_std__",  "ks_stat": float(np.std(dists)),  "ks_pvalue": np.nan, "metric":"privacy_nn_std"}

    # Save to Excel with multiple sheets
    with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
        # 3.1) Sintéticos (mantive o nome de aba 'TDados' como estava no seu script;
        #     se preferir, pode trocar para 'SYNTH')
        df_out.to_excel(writer, index=False, sheet_name='TDados')

        # 3.2) HOLDOUT (a metade que NÃO foi usada no treino)
        if df_holdout is not None:
            df_holdout.to_excel(writer, index=False, sheet_name='DATA_UNUSED')

        # 3.3) Cópia literal da aba 'Pontuação' do Excel original, se existir
        if 'df_pontuacao' in locals() and df_pontuacao is not None:
            df_pontuacao.to_excel(writer, index=False, sheet_name='Pontuação')

        # 3.4) Relatório (opcional)
        if args.save_excel_report:
            rep.to_excel(writer, index=False, sheet_name='REPORT')

    print(f"[OK] Excel saved: {out_xlsx}  (synthetic_rows={len(df_out)})")

    # Exporta CSV do relatório na mesma pasta de saída do Excel
    out_csv = out_xlsx.parent / f"hybrid_aug_report_{timestamp_str}.csv"
    rep.to_csv(out_csv, index=False)
    print(f"[OK] Report saved: {out_csv}")

if __name__ == "__main__":
    main()
