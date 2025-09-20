
"""
Híbrido SMOTE + cWGAN-GP para dados clínicos tabulares (condicionado por classe)
- Half-split por classe (50% ou 50%+1) ATIVADO POR PADRÃO (desligável com --no-half-split)
- SMOTE com bootstrap (RandomOverSampler) para classes com 1 amostra
- Treino cWGAN-GP condicional
- Geração de N amostras por classe com filtro de privacidade e CDF matching (opcional)
- Excel final com:
    * 'TDados' (sintéticos)
    * 'HOLDOUT_UNUSED' (originais não usados no treino)
    * 'Pontuação' (cópia literal da aba original, se existir)
    * 'REPORT' (métricas, se --save-excel-report)
- Descarta das FEATURES toda coluna que, na aba "Pontuação", for totalmente ZERO (para aliviar o modelo)

Uso rápido (sem args pega defaults úteis):
    python 03_hybrid_smote_cwgan_final.py
equivale a:
    python 03_hybrid_smote_cwgan_final.py --excel Banco_dados.xlsx --sheet TDados --target Alvo \
      --per-class-count 50 --smote-min-per-class 200 --balance --cdf-match --save-excel-report
"""

import os
import argparse
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from sklearn.neighbors import NearestNeighbors
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

import torch
import torch.nn as nn
import torch.autograd as autograd
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from imblearn.over_sampling import SMOTE, RandomOverSampler

# -----------------------------------------------------
# Utilitários
# -----------------------------------------------------

def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def find_excel_case_insensitive(path_str: str) -> Path:
    p = Path(path_str)
    if p.exists():
        return p
    # tenta achar por case-insensitive na mesma pasta
    if p.parent.exists():
        for child in p.parent.iterdir():
            if child.suffix.lower() in ('.xlsx', '.xls') and child.stem.lower() == p.stem.lower():
                return child
    # fallback
    return p

def onehot(idx: torch.Tensor, n_classes: int) -> torch.Tensor:
    oh = torch.zeros((idx.size(0), n_classes), device=idx.device)
    oh.scatter_(1, idx.view(-1,1), 1.0)
    return oh

# -----------------------------------------------------
# Modelos condicionais (cWGAN-GP)
# -----------------------------------------------------

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
        layers += [nn.Linear(in_dim, out_dim), nn.Sigmoid()]  # garante [0,1]
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
                 lr=1e-4, betas=(0.0, 0.9), n_critic=5, gp_lambda=10.0, seed=42, device=None):
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
            assert n_classes is not None, "Defina n_classes ao amostrar sem y_idx."
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

                # passos do crítico
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

                # passo do gerador
                z = torch.randn(x_real.size(0), self.z_dim, device=self.device)
                x_gen = self.G(z, y_oh)
                g_loss = -self.D(x_gen, y_oh).mean()

                self.opt_G.zero_grad(set_to_none=True)
                g_loss.backward()
                self.opt_G.step()

            if ep % log_every == 0 or ep == 1:
                print(f"[{ep:04d}/{epochs}] D_loss={d_loss.item():.4f}  G_loss={g_loss.item():.4f}  "
                      f"D(real)={d_real.item():.4f} D(fake)={d_fake.item():.4f}", flush=True)

# -----------------------------------------------------
# Dados e utilitários específicos
# -----------------------------------------------------

def load_tabular(excel_path: Path, sheet: str, target: str, ignore_labels: str, return_full_df=False):
    df = pd.read_excel(excel_path, sheet_name=sheet).copy()
    if target not in df.columns:
        raise ValueError(f"Coluna alvo '{target}' não encontrada na aba '{sheet}'.")
    y_raw = df[target].astype(str).str.strip()

    if ignore_labels:
        ignore = {s.strip().lower() for s in ignore_labels.split(",") if s.strip()}
        keep_mask = ~y_raw.str.lower().isin(ignore)
        df = df.loc[keep_mask]
        y_raw = y_raw.loc[keep_mask]

    # apenas colunas numéricas (exceto target)
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target in num_cols:
        num_cols.remove(target)
    X_df = df[num_cols].copy()

    # ALVO: não alteramos NaNs aqui; trataremos no treino (após split)
    X = np.clip(X_df.to_numpy(dtype=np.float32), 0.0, 1.0)
    classes = sorted(y_raw.unique().tolist())
    label_to_idx = {lbl: i for i, lbl in enumerate(classes)}
    y = y_raw.map(label_to_idx).to_numpy(dtype=np.int64)

    if return_full_df:
        return df, X_df.columns.tolist(), X, y, classes, label_to_idx
    else:
        return X_df.columns.tolist(), X, y, classes, label_to_idx

def per_class_split(df_filtered, target, perc=50.0, seed=42):
    """Seleciona ceil(perc% de N_c) por classe para treino; retorna máscara booleana.
       Ex.: perc=50 -> ~metade (para N_c ímpar vira 50%+1).
    """
    rng = np.random.RandomState(seed)
    y = df_filtered[target].astype(str).str.strip().to_numpy()
    idx_all = np.arange(len(df_filtered))
    train_mask = np.zeros(len(df_filtered), dtype=bool)
    classes = pd.Series(y).unique().tolist()
    frac = float(perc) / 100.0
    for c in classes:
        cls_idx = idx_all[y == c]
        if len(cls_idx) == 0:
            continue
        rng.shuffle(cls_idx)
        # ceil(N_c * perc/100). Para N_c ímpar em 50%, vira 50%+1; generaliza o mesmo comportamento
        k = int(np.ceil(len(cls_idx) * frac))
        sel = cls_idx[:k]
        train_mask[sel] = True
    return train_mask


def run_smote(X: np.ndarray, y: np.ndarray, n_classes: int,
              min_per_class: int, k_neighbors: int, random_state: int):
    """Upsample para pelo menos min_per_class por classe.
       1) Se classe com 1 amostra: bootstrap p/ 2 com RandomOverSampler.
       2) Depois, SMOTE nas classes elegíveis (>=2 amostras) com k ajustado.
    """
    counts = np.bincount(y, minlength=n_classes)

    # 1) Bootstrap prévio
    need_bootstrap = {ci: 2 for ci, cnt in enumerate(counts)
                      if cnt == 1 and max(int(min_per_class), int(cnt)) > cnt}
    X_work, y_work = X, y
    if need_bootstrap:
        ros = RandomOverSampler(sampling_strategy=need_bootstrap, random_state=random_state)
        X_work, y_work = ros.fit_resample(X_work, y_work)
        counts = np.bincount(y_work, minlength=n_classes)

    # 2) SMOTE apenas para classes com >=2 amostras
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

# -----------------------------------------------------
# Métricas
# -----------------------------------------------------

def ks_report(X_real: np.ndarray, X_syn: np.ndarray, feat_cols):
    rows = []
    for j, name in enumerate(feat_cols):
        ks = ks_2samp(X_real[:, j], X_syn[:, j])
        rows.append({"feature": name, "ks_stat": float(ks.statistic), "ks_pvalue": float(ks.pvalue)})
    return pd.DataFrame(rows)

def corr_gap(X_real: np.ndarray, X_syn: np.ndarray):
    if X_real.shape[1] < 2:
        return np.nan
    C_r = np.corrcoef(X_real, rowvar=False)
    C_s = np.corrcoef(X_syn, rowvar=False)
    gap = np.linalg.norm(C_r - C_s, ord='fro')
    return float(gap)

def c2st_auc(X_real: np.ndarray, X_syn: np.ndarray, seed=42):
    n_r = len(X_real); n_s = len(X_syn)
    n = min(n_r, n_s)
    if n < 50:
        return np.nan
    rng = np.random.RandomState(seed)
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

# -----------------------------------------------------
# Main
# -----------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Híbrido SMOTE + cWGAN-GP para geração de pacientes virtuais condicionados por classe.")
    # Parâmetros principais
    ap.add_argument("--excel", type=str, default=r"c:\\SourceCode\\qip\\python\\banco_dados.xlsx",
                    help="Caminho do arquivo Excel de entrada (padrão: Banco_dados.xlsx).")
    ap.add_argument("--sheet", type=str, default="TDados",
                    help="Nome da planilha (aba) no Excel a ser usada (padrão: TDados).")
    ap.add_argument("--target", type=str, default="Alvo",
                    help="Nome da coluna alvo (classe) usada para condicionamento (padrão: Alvo).")
    ap.add_argument("--ignore-labels", type=str, default="nao,não,desconhecido",
                    help="Lista de rótulos a ignorar no treino, separados por vírgula (padrão: 'nao,não,desconhecido').")
    ap.add_argument("--epochs", type=int, default=50000,
                    help="Número de épocas de treinamento do modelo GAN (padrão: 15000).")
    ap.add_argument("--batch-size", type=int, default=256,
                    help="Tamanho do lote (batch) para treinamento (padrão: 256).")
    ap.add_argument("--z-dim", type=int, default=64,
                    help="Dimensão do vetor de ruído latente usado pelo gerador (padrão: 64).")
    ap.add_argument("--g-hidden", type=int, default=256,
                    help="Número de neurônios na camada oculta do gerador (padrão: 256).")
    ap.add_argument("--d-hidden", type=int, default=256,
                    help="Número de neurônios na camada oculta do critic (padrão: 256).")
    ap.add_argument("--g-depth", type=int, default=3,
                    help="Número de camadas ocultas no gerador (padrão: 3).")
    ap.add_argument("--d-depth", type=int, default=3,
                    help="Número de camadas ocultas no critic (padrão: 3).")
    ap.add_argument("--n-critic", type=int, default=5,
                    help="Número de passos de treino do critic por passo do gerador (padrão: 5).")
    ap.add_argument("--gp-lambda", type=float, default=10.0,
                    help="Coeficiente da penalização de gradiente (Gradient Penalty) no WGAN-GP (padrão: 10.0).")
    ap.add_argument("--log-every", type=int, default=100,
                    help="Frequência (em épocas) para exibir logs durante o treinamento (padrão: 100).")

    # Half-split: padrão ligado; pode desativar com --no-half-split
    ap.add_argument("--half-split", action=argparse.BooleanOptionalAction, default=True,
                    help="Por padrão, usa 50% (+1 se ímpar) por classe para treino e exporta o restante na aba HOLDOUT_UNUSED. Desligue com --no-half-split.")
    ap.add_argument("--split-perc", type=float, default=100.0,
                help="Porcentagem por classe destinada ao TREINO (0–100). Ex.: 60 usa ~60% por classe; para contagens ímpares, arredonda para cima.")
    ap.add_argument("--save-excel-report", action="store_true",
                    help="Inclui o relatório de métricas (KS, correlação, privacidade) como aba extra no Excel de saída.")

    # SMOTE
    ap.add_argument("--smote-min-per-class", type=int, default=400,
                    help="Número mínimo de amostras por classe após SMOTE (padrão: 200).")
    ap.add_argument("--smote-k", type=int, default=5,
                    help="k_neighbors do SMOTE; reduzido automaticamente conforme necessário (padrão: 5).")
    ap.add_argument("--seed", type=int, default=42,
                    help="Semente aleatória para reprodutibilidade (padrão: 42).")

    # Imputação de NaN no treino
    ap.add_argument("--impute", type=str, choices=["median", "mean", "zero", "drop"], default="median",
                    help="Tratamento de NaN nas features do treino antes do SMOTE: 'median' (padrão), 'mean', 'zero' (0.0) ou 'drop' (remove linhas com NaN).")

    # Geração
    ap.add_argument("--per-class-count", type=int, default=50,
                    help="Número de amostras sintéticas a gerar por classe (padrão: 50).")
    ap.add_argument("--cdf-match", action="store_true",
                    help="Aplica ajuste marginal (CDF matching) por feature para alinhar com a distribuição original.")
    ap.add_argument("--min-nn-distance", type=float, default=0.01,
                    help="Distância mínima (L2) de cada amostra sintética para as reais, garantindo privacidade (padrão: 0.10).")
    ap.add_argument("--max-gen-tries", type=int, default=50,
                    help="Número máximo de tentativas de reamostragem por classe para atingir a contagem desejada (padrão: 10).")
    ap.add_argument("--balance", action="store_true",
                    help="Ativa balanceamento de classes no DataLoader durante o treino (útil para classes desbalanceadas).")
    args = ap.parse_args()

    excel_path = find_excel_case_insensitive(args.excel)
    print(f"[INFO] Reading: {excel_path} (sheet='{args.sheet}') target='{args.target}'")

    # Tentar carregar "Pontuação" para copiar e detectar colunas zero
    try:
        df_pontuacao = pd.read_excel(excel_path, sheet_name="Pontuação")
        print("[INFO] Aba 'Pontuação' encontrada e será copiada para o arquivo de saída.")
        zero_cols = []
        for col in df_pontuacao.columns:
            if pd.api.types.is_numeric_dtype(df_pontuacao[col]):
                if df_pontuacao[col].fillna(0).abs().sum() == 0:
                    zero_cols.append(col)
        if zero_cols:
            print("[INFO] Colunas com todos os valores 0 na aba Pontuação (serão descartadas na geração):", zero_cols)
    except Exception:
        df_pontuacao = None
        zero_cols = []
        print("[INFO] Aba 'Pontuação' não encontrada no arquivo de entrada; ignorando cópia e descarte por zero.")

    # Carregar dados principais
    df_full, feat_cols, X_all, y_all, classes, label_to_idx = load_tabular(excel_path, args.sheet, args.target, args.ignore_labels, return_full_df=True)
    n_classes = len(classes)
    print(f"[INFO] Found {n_classes} classes: {classes}")

    # Remover features que são colunas zeradas em Pontuação
    if zero_cols:
        cols_to_drop = [c for c in zero_cols if c in feat_cols]
        if cols_to_drop:
            keep_idx = [i for i,c in enumerate(feat_cols) if c not in cols_to_drop]
            feat_cols = [feat_cols[i] for i in keep_idx]
            X_all = X_all[:, keep_idx]
            print(f"[INFO] Features descartadas por serem zero em Pontuação: {cols_to_drop}")

    # Split half-split (padrão ligado)
    if args.half_split:
        train_mask = per_class_split(df_full, args.target, seed=args.seed)
        df_train = df_full.loc[train_mask].reset_index(drop=True)
        df_holdout = df_full.loc[~train_mask].reset_index(drop=True)
        # reconstruir X,y de treino respeitando feat_cols atuais
        num_cols = df_train.select_dtypes(include=[np.number]).columns.tolist()
        if args.target in num_cols:
            num_cols.remove(args.target)
        if zero_cols:
            num_cols = [c for c in num_cols if c in feat_cols]  # mantem alinhado após prune
        X = np.clip(df_train[num_cols].to_numpy(dtype=np.float32), 0.0, 1.0)
        y_series = df_train[args.target].astype(str).str.strip()
        y = y_series.map(label_to_idx).to_numpy(dtype=np.int64)
        print(f"[INFO] Half-split: train={len(df_train)}  holdout={len(df_holdout)}")
    else:
        X = X_all; y = y_all
        df_holdout = None

    # Tratamento de NaN nas features do treino (antes do SMOTE)
    if np.isnan(X).any():
        print("[INFO] Foram encontrados NaNs no conjunto de treino. Aplicando estratégia de imputação:", args.impute)
        if args.impute == "drop":
            mask = ~np.isnan(X).any(axis=1)
            removed = int((~mask).sum())
            X = X[mask]; y = y[mask]
            print(f"[INFO] Linhas removidas por NaN no treino: {removed}  |  Restantes: {len(X)}")
        elif args.impute == "median":
            imputer = SimpleImputer(strategy="median")
            X = imputer.fit_transform(X)
        elif args.impute == "mean":
            imputer = SimpleImputer(strategy="mean")
            X = imputer.fit_transform(X)
        elif args.impute == "zero":
            X = np.nan_to_num(X, nan=0.0)

    # SMOTE no treino
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
        loader = DataLoader(TensorDataset(X_t, y_t), batch_size=args.batch_size,
                            sampler=WeightedRandomSampler(weights=weights, num_samples=len(weights), replacement=True))
    else:
        loader = DataLoader(TensorDataset(X_t, y_t), batch_size=args.batch_size, shuffle=True)

    # Treino do cWGAN-GP
    model = CWGAN_GP(
        x_dim=X_sm.shape[1], y_dim=n_classes, z_dim=args.z_dim,
        g_hidden=args.g_hidden, d_hidden=args.d_hidden,
        g_depth=args.g_depth, d_depth=args.d_depth,
        n_critic=args.n_critic, gp_lambda=args.gp_lambda, seed=args.seed
    )
    model.train(loader, n_classes=n_classes, epochs=args.epochs, log_every=args.log_every)

    # Geração por classe
    all_Xs = []; all_Ys = []
    for name in classes:
        target_idx = label_to_idx[name]
        needed = int(args.per_class_count)
        got = 0; tries = 0
        col_buffer = []

        # Real por classe (para CDF matching)
        idx_this = (y == target_idx)
        X_real_cls = X[idx_this] if idx_this.any() else X

        while got < needed and tries < args.max_gen_tries:
            batch = max(needed - got, args.batch_size)
            y_idx_tensor = torch.full((batch,), target_idx, dtype=torch.long)
            Xs, Ys = model.sample(batch, y_idx=y_idx_tensor, n_classes=n_classes)

            # filtro de privacidade vs X original do TREINO (não SMOTE)
            keep_mask = np.ones(len(Xs), dtype=bool)
            if len(X) > 0:
                nbrs = NearestNeighbors(n_neighbors=1).fit(X)
                dists, _ = nbrs.kneighbors(Xs)
                keep_mask = (dists.reshape(-1) >= float(args.min_nn_distance))
            Xs = Xs[keep_mask]; Ys = Ys[keep_mask]
            if len(Xs) == 0:
                tries += 1; continue

            # CDF match (opcional)
            if args.cdf_match:
                Xs_adj = Xs.copy()
                for j in range(Xs.shape[1]):
                    # ranks -> quantis reais (por classe; fallback para todo treino)
                    ranks = (pd.Series(Xs[:, j]).rank(method='average') - 0.5) / len(Xs)
                    ref = X_real_cls[:, j] if len(X_real_cls) > 0 else X[:, j]
                    q = np.quantile(ref, ranks, method='linear') if len(ref) > 0 else Xs[:, j]
                    Xs_adj[:, j] = q
                Xs = np.clip(Xs_adj, 0, 1)

            take = min(needed - got, len(Xs))
            col_buffer.append(Xs[:take]); got += take; tries += 1

        if got < needed:
            print(f"[WARN] Could only produce {got}/{needed} for class '{name}' with current filters.")
        if col_buffer:
            X_final = np.vstack(col_buffer)
            Y_final = np.full((X_final.shape[0],), target_idx, dtype=np.int64)
            all_Xs.append(X_final); all_Ys.append(Y_final)

    if not all_Xs:
        raise RuntimeError("Nenhuma linha sintética produzida; reduza --min-nn-distance ou aumente --max-gen-tries.")

    X_syn = np.vstack(all_Xs)
    Y_syn = np.concatenate(all_Ys)
    idx_to_label = {v:k for k,v in label_to_idx.items()}
    labels = [idx_to_label[int(i)] for i in Y_syn]

    df_out = pd.DataFrame(X_syn, columns=feat_cols)
    df_out.insert(0, args.target, labels)

    # Relatórios
    ks_df = ks_report(X, X_syn, feat_cols); ks_df["metric"] = "KS"
    gap = corr_gap(X, X_syn); auc = c2st_auc(X, X_syn, seed=args.seed)
    rep = ks_df.copy()
    rep.loc[len(rep.index)] = {"feature": "__summary_corr_gap__", "ks_stat": gap, "ks_pvalue": np.nan, "metric":"corr_gap_fro"}
    rep.loc[len(rep.index)] = {"feature": "__summary_c2st_auc__", "ks_stat": auc, "ks_pvalue": np.nan, "metric":"c2st_auc"}
    if len(X) > 0:
        nbrs_all = NearestNeighbors(n_neighbors=1).fit(X)
        dists_all, _ = nbrs_all.kneighbors(X_syn)
        rep.loc[len(rep.index)] = {"feature": "__privacy_nn_mean__", "ks_stat": float(np.mean(dists_all)), "ks_pvalue": np.nan, "metric":"privacy_nn_mean"}
        rep.loc[len(rep.index)] = {"feature": "__privacy_nn_std__",  "ks_stat": float(np.std(dists_all)),  "ks_pvalue": np.nan, "metric":"privacy_nn_std"}

    timestamp_str = ts()
    out_xlsx = Path(f"saida_modelo\\banco_dados_vt{timestamp_str}.xlsx").absolute()
    # garantir diretório de saída
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)

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
    # *Opcional* para evitar ruído do loky no Windows muito restrito:
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    main()
