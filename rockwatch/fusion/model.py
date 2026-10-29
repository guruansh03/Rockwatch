"""FuseGuard fusion (§8): one L2 logistic regression; each modality owns its coefficients and publishes
contribution = Σ coef·x (standardised x, clipped ±cap). logit = b0 + Σ w_q·contribution."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

RAW_GROUPS: dict[str, list[str]] = {
    "rain": ["P1", "P3", "P15", "P30", "API", "precip_hours", "intensity", "seattle_ct_margin_in", "rain_on_snow"],
    "thermal": ["ft_cycles_7d", "tmax_anom"],
    "seismic": ["eq_max_mag_3d", "eq_count_3d", "eq_min_dist_km_3d"],
    "susceptibility": ["susc"],
    "context": ["month_sin", "month_cos", "regional_extent"],
}
LOG1P = {"P1", "P3", "P15", "P30", "API", "intensity", "eq_count_3d"}
ABLATIONS: dict[str, list[str]] = {
    "rain": ["rain"],
    "rain+susc": ["rain", "susceptibility"],
    "rain+susc+thermal": ["rain", "susceptibility", "thermal"],
    "rain+susc+thermal+seismic": ["rain", "susceptibility", "thermal", "seismic"],
    "full": ["rain", "susceptibility", "thermal", "seismic", "context"],
}


def transform(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Deterministic per-feature transforms (log1p for heavy-tailed sums; distance → proximity in [0,1])."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        x = df[c].astype(float)
        if c in LOG1P:
            x = np.log1p(x.clip(lower=0))
        elif c == "eq_min_dist_km_3d":
            x = (1.0 - x / 100.0).clip(0, 1)
        out[c] = x
    return out


@dataclass
class FusionModel:
    """Serializable fitted fusion model."""
    groups: dict[str, list[str]]
    mean: dict[str, float]
    std: dict[str, float]
    coef: dict[str, float]
    intercept: float
    cap: float
    C: float
    platt_a: float = 1.0
    platt_b: float = 0.0
    thresholds: dict[str, Any] = field(default_factory=dict)
    train_info: dict[str, Any] = field(default_factory=dict)

    @property
    def features(self) -> list[str]:
        return [c for g in self.groups.values() for c in g]

    def standardise(self, df: pd.DataFrame) -> pd.DataFrame:
        X = transform(df, self.features)
        for c in self.features:
            X[c] = (X[c] - self.mean[c]) / self.std[c]
        return X.fillna(0.0)  # missing → train mean (neutral)

    def group_contribution(self, group: str, feats: dict[str, float]) -> float:
        """Fast scalar contribution for one modality (agents). Same transform/standardise/clip as batch."""
        tot = 0.0
        for c in self.groups[group]:
            x = feats.get(c)
            x = float("nan") if x is None else float(x)
            if c in LOG1P:
                x = float(np.log1p(max(x, 0.0))) if not np.isnan(x) else x
            elif c == "eq_min_dist_km_3d":
                x = min(max(1.0 - x / 100.0, 0.0), 1.0) if not np.isnan(x) else x
            z = (x - self.mean[c]) / self.std[c]
            tot += 0.0 if np.isnan(z) else self.coef[c] * z
        return float(min(max(tot, -self.cap), self.cap))

    def contributions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per-modality clipped log-odds contributions."""
        X = self.standardise(df)
        out = pd.DataFrame(index=df.index)
        for g, cols in self.groups.items():
            out[g] = (X[cols] * np.array([self.coef[c] for c in cols])).sum(axis=1).clip(-self.cap, self.cap)
        return out

    def logit(self, contrib: pd.DataFrame, quality: pd.DataFrame | None = None, qw: dict[str, float] | None = None) -> pd.Series:
        """intercept + Σ w_q·contribution. quality: same columns with ok|degraded|missing."""
        if quality is None:
            return self.intercept + contrib.sum(axis=1)
        qw = qw or {"ok": 1.0, "degraded": 0.5, "missing": 0.0}
        w = quality[contrib.columns].replace(qw).astype(float)
        return self.intercept + (contrib * w).sum(axis=1)

    def proba(self, logit: pd.Series | np.ndarray) -> np.ndarray:
        """Platt-calibrated probability."""
        z = self.platt_a * np.asarray(logit, float) + self.platt_b
        return 1.0 / (1.0 + np.exp(-z))

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.contributions(df)
        lg = self.logit(c)
        out = c.add_prefix("c_")
        out["logit"] = lg
        out["p"] = self.proba(lg)
        return out

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, default=float)

    @classmethod
    def from_json(cls, s: str) -> "FusionModel":
        return cls(**json.loads(s))


def fit_fusion(panel: pd.DataFrame, group_names: list[str], cfg: dict[str, Any], y_col: str = "y") -> FusionModel:
    """Fit LR on train (all positives + sampled negatives), choose C on val AP, Platt on full val."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score

    fc = cfg["fusion"]
    groups = {g: RAW_GROUPS[g] for g in group_names}
    feats = [c for g in groups.values() for c in g]
    tr = panel[panel["split"] == "train"]
    va = panel[panel["split"] == "val"]
    Xtr_all = transform(tr, feats)
    mean = Xtr_all.mean().to_dict()
    std = Xtr_all.std(ddof=0).replace(0, 1.0).fillna(1.0).to_dict()
    pos = tr[tr[y_col] > 0]
    neg = tr[tr[y_col] == 0]
    n_neg = min(len(neg), fc["neg_per_pos"] * len(pos))
    neg_s = neg.sample(n=n_neg, random_state=fc["seed"])
    fit_df = pd.concat([pos, neg_s])

    def std_x(df):
        X = transform(df, feats)
        return ((X - pd.Series(mean)) / pd.Series(std)).fillna(0.0)[feats].to_numpy()

    Xf, yf = std_x(fit_df), (fit_df[y_col] > 0).astype(int).to_numpy()
    Xv, yv = std_x(va), (va[y_col] > 0).astype(int).to_numpy()
    best = None
    for C in fc["C_grid"]:
        lr = LogisticRegression(C=C, max_iter=5000)
        lr.fit(Xf, yf)
        ap = average_precision_score(yv, lr.decision_function(Xv)) if yv.any() else float("nan")
        if best is None or ap > best[0]:
            best = (ap, C, lr)
    ap, C, lr = best
    m = FusionModel(groups=groups, mean=mean, std=std, coef=dict(zip(feats, lr.coef_[0].tolist())),
                    intercept=float(lr.intercept_[0]), cap=fc["cap"], C=C)
    # Platt on full (unsampled) validation using the clipped-contribution logit actually deployed
    lg = m.logit(m.contributions(va)).to_numpy().reshape(-1, 1)
    pl = LogisticRegression(C=1e6, max_iter=5000).fit(lg, yv)
    m.platt_a, m.platt_b = float(pl.coef_[0][0]), float(pl.intercept_[0])
    m.train_info = {"n_pos": int(len(pos)), "n_neg_sampled": int(n_neg), "neg_per_pos_actual": round(n_neg / max(len(pos), 1), 2),
                    "n_neg_available": int(len(neg)), "val_ap": float(ap), "groups": group_names, "y_col": y_col}
    return m
