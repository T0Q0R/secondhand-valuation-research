"""Strategic withholding, mask-aware valuation and hard-cap verification.

No source-price column is allowed in predictor or action-head input. Candidate
reveals and full-report prices are used only to construct training targets or
to replay the stipulated seller/verification environment.
"""
from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from torch import nn


ACTIONS = ("mileage_km", "transmission", "fuel_type", "feat_body_condition")
FORBIDDEN = {"mileage_text", "engine_type", "target_log", "listing_id", "source_row_number"}
FEATURES = {
    "synthetic": ["make", "model", "year", *ACTIONS, "fiscal_power", "location"],
    "jucars": ["make", "model", "year", *ACTIONS, "body_type", "color", "interior_color", "seats", "city", "feat_insurance", "feat_carcustoms", "feat_license", "feat_paintcondition", "feat_battery_capacity", "feat_battery_range"],
    "mucars": ["make", "model", "year", *ACTIONS, "fiscal_power", "number_of_doors", "origin", "first_owner", "location", "sector", "equipment_count"],
}


def price_features(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if FORBIDDEN.intersection(columns) or any("price" in c.lower() for c in columns):
        raise ValueError("Outcome, identifier or reveal alias in predictor features")
    return frame.loc[:, columns].copy()


def stable_rank(identifier: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{identifier}".encode()).hexdigest()


@dataclass
class StateSpace:
    masks: np.ndarray
    reveal: np.ndarray

    @classmethod
    def build(cls, maximum_hidden: int = 2) -> "StateSpace":
        if not 0 <= maximum_hidden <= len(ACTIONS):
            raise ValueError("Invalid maximum hidden-field count")
        masks = np.array([
            [a in group for a in range(len(ACTIONS))]
            for size in range(maximum_hidden + 1)
            for group in itertools.combinations(range(len(ACTIONS)), size)
        ], dtype=bool)
        lookup = {tuple(mask): i for i, mask in enumerate(masks)}
        reveal = np.full((len(masks), len(ACTIONS)), -1, dtype=int)
        for s, mask in enumerate(masks):
            for a in np.flatnonzero(mask):
                after = mask.copy()
                after[a] = False
                reveal[s, a] = lookup[tuple(after)]
        return cls(masks, reveal)

    def materialize(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        # item-major order: record 0 / all states, then record 1 / all states.
        n, s = len(frame), len(self.masks)
        flat = frame.iloc[np.repeat(np.arange(n), s)].reset_index(drop=True).copy()
        for a, field in enumerate(ACTIONS):
            flat.loc[np.tile(self.masks[:, a], n), field] = np.nan
        eligible = frame.loc[:, ACTIONS].notna().to_numpy()
        valid = ~(self.masks[None, :, :] & ~eligible[:, None, :]).any(axis=2)
        return flat, valid

    def reported_missing(self, frame: pd.DataFrame) -> np.ndarray:
        """Public missingness; deliberately hidden and absent values look alike."""
        natural = frame.loc[:, list(ACTIONS)].isna().to_numpy()
        return natural[:, None, :] | self.masks[None, :, :]

    @property
    def query_next(self) -> np.ndarray:
        """Environment transition; unsuccessful queries leave state unchanged."""
        return np.where(self.reveal >= 0, self.reveal, np.arange(len(self.masks))[:, None])


class Encoder:
    def fit(self, frame: pd.DataFrame) -> "Encoder":
        self.columns = list(frame.columns)
        self.numeric = [c for c in self.columns if pd.api.types.is_numeric_dtype(frame[c])]
        self.categorical = [c for c in self.columns if c not in self.numeric]
        self.transformer = ColumnTransformer([
            ("numeric", make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler()), self.numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False, min_frequency=5), self.categorical),
        ])
        self.transformer.fit(self._prepare(frame))
        return self

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.loc[:, self.columns].copy()
        for c in self.numeric:
            out[c] = pd.to_numeric(out[c], errors="coerce")
            if c in {"mileage_km", "feat_battery_range", "feat_battery_capacity"}:
                out[c] = np.log1p(out[c].clip(lower=0))
        for c in self.categorical:
            out[c] = out[c].fillna("<MISSING>").astype(str)
        return out

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        return self.transformer.transform(self._prepare(frame)).astype(np.float32)

    def tree_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self._prepare(frame)


def fit_backbone(frame: pd.DataFrame, y: np.ndarray, space: StateSpace, config: dict, seed: int, *, augment: bool = True):
    original = frame.copy()
    for field in ACTIONS:
        if pd.api.types.is_numeric_dtype(original[field]):
            original[field] = original[field].astype(float)
    states, valid = space.materialize(original)
    encoder = Encoder().fit(states)
    n, s = valid.shape
    if augment:
        mask = valid.ravel()
        training = states.loc[mask]
        labels = np.repeat(y, s)[mask]
        weights = np.repeat(1.0 / valid.sum(axis=1), s)[mask]
    else:
        training, labels, weights = original, y, None
    model = CatBoostRegressor(iterations=config["catboost_iterations"], depth=6,
        learning_rate=0.06, loss_function="RMSE", random_seed=seed,
        thread_count=4, verbose=False, allow_writing_files=False)
    model.fit(encoder.tree_frame(training), labels,
        cat_features=encoder.categorical, sample_weight=weights)
    return Valuator(model, encoder, space, config["residual_hidden_width"])


class Valuator:
    def __init__(self, backbone, encoder: Encoder, space: StateSpace, width: int):
        self.backbone, self.encoder, self.space = backbone, encoder, space
        self.width = width
        self.residual = None

    def arrays(self, frame: pd.DataFrame):
        states, valid = self.space.materialize(frame)
        n, s = valid.shape
        x = self.encoder.transform(states).reshape(n, s, -1)
        base = self.backbone.predict(self.encoder.tree_frame(states)).reshape(n, s)
        return x, base.astype(np.float32), valid

    def predict(self, frame: pd.DataFrame):
        x, base, valid = self.arrays(frame)
        return self.predict_arrays(x, base), x, valid

    def predict_arrays(self, x: np.ndarray, base: np.ndarray):
        if self.residual is None:
            return base.astype(float)
        self.residual.eval()
        with torch.no_grad():
            correction = self.residual(torch.from_numpy(x.reshape(-1, x.shape[-1]))).reshape(base.shape).numpy()
        return (base + correction).astype(float)

    def train_residual(self, frame: pd.DataFrame, y: np.ndarray, config: dict,
                       seed: int, policy: "ActionHeads | None", *, gap_weight: float | None = None,
                       policy_aware: bool = True, policy_kind: str = "suppression",
                       epochs: int | None = None):
        torch.manual_seed(seed)
        x, base, valid = self.arrays(frame)
        reported_missing = self.space.reported_missing(frame)
        if self.residual is None:
            self.residual = nn.Sequential(nn.Linear(x.shape[-1], self.width), nn.ReLU(),
                nn.Linear(self.width, self.width), nn.ReLU(), nn.Linear(self.width, 1))
            nn.init.zeros_(self.residual[-1].weight)
            nn.init.zeros_(self.residual[-1].bias)
        optimizer = torch.optim.AdamW(self.residual.parameters(), lr=config["learning_rate"], weight_decay=1e-4)
        rng = np.random.default_rng(seed)
        beta = config["gap_penalty_weight"] if gap_weight is None else gap_weight
        tensor_x, tensor_base = torch.from_numpy(x), torch.from_numpy(base)
        tensor_y = torch.tensor(y, dtype=torch.float32)
        logs = []
        steps = config["residual_epochs"] if epochs is None else epochs
        for epoch in range(steps):
            total = 0.0
            # Refresh action scores once per epoch from the current model.
            # Scores are a frozen surrogate within an epoch; gradients flow
            # through the selected final-price state, not a discrete allocator.
            score_epoch = None
            if policy is not None:
                epoch_pred = self.predict_arrays(x, base)
                score_epoch = policy.score(x, epoch_pred, self.space, policy_kind, reported_missing=reported_missing)
            for start in range(0, len(frame), config["batch_size"]):
                # Order is reshuffled every epoch, independent of prices.
                if start == 0:
                    order = rng.permutation(len(frame))
                idx = order[start:start + config["batch_size"]]
                bx, bb, by = tensor_x[idx], tensor_base[idx], tensor_y[idx]
                self.residual.train()
                predicted = bb + self.residual(bx.reshape(-1, bx.shape[-1])).reshape(bb.shape)
                detached = predicted.detach().numpy().astype(float)
                if policy is not None and policy_aware:
                    attack = strategic_response(detached, score_epoch[idx], valid[idx], self.space,
                        budget=config.get("training_budget", 0.1),
                        sweeps=config.get("training_attacker_sweeps", 2), restarts=1,
                        cost=config["concealment_cost_log"])
                    final_states = attack["final_state"]
                else:
                    final_states = np.argmax(np.where(valid[idx], detached, -np.inf), axis=1)
                    if policy is not None:
                        final_states = allocate(score_epoch[idx], final_states, self.space,
                            int(np.floor(config.get("training_budget", 0.1) * len(idx))))[0]
                rows = torch.arange(len(idx))
                attacked = predicted[rows, torch.as_tensor(final_states)]
                honest = predicted[:, 0]
                natural = ((honest - by) ** 2).mean()
                adversarial = ((attacked - by) ** 2).mean()
                # Honest anchor is detached in the gap term; supervised and
                # fixed-backbone anchor losses prevent moving that anchor freely.
                gap = torch.relu(attacked - honest.detach() - config["gap_tolerance_log"]).mean()
                anchoring = ((honest - bb[:, 0]) ** 2).mean()
                valid_tensor = torch.as_tensor(valid[idx])
                augmented = (((predicted - by[:, None]) ** 2) * valid_tensor).sum(dim=1) / valid_tensor.sum(dim=1)
                loss = natural + 0.25 * augmented.mean() + config["attack_loss_weight"] * adversarial + beta * gap + config["anchor_weight"] * anchoring
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.residual.parameters(), 5.0)
                optimizer.step()
                total += float(loss.detach()) * len(idx)
            logs.append({"epoch": epoch + 1, "loss": total / len(frame)})
        return logs


class ActionHeads:
    """Head inputs never contain hidden fields, after-reveal prices or labels."""
    def __init__(self, trees: int, seed: int):
        self.model = ExtraTreesRegressor(n_estimators=trees, max_depth=12,
            min_samples_leaf=12, random_state=seed, n_jobs=4)

    @staticmethod
    def matrix(x: np.ndarray, pred: np.ndarray):
        n, s, d = x.shape
        a = len(ACTIONS)
        state = np.repeat(x.reshape(n * s, d), a, axis=0)
        before = np.repeat(pred.reshape(-1), a)[:, None]
        action = np.tile(np.eye(a, dtype=np.float32), (n * s, 1))
        return np.column_stack([state, before, action])

    def fit(self, x, pred, valid, y, space: StateSpace, *, reported_missing: np.ndarray):
        n, s = pred.shape
        a = len(ACTIONS)
        available = valid[:, :, None] & reported_missing
        after = pred[:, space.query_next]
        anchor = pred[:, 0, None, None]
        before = pred[:, :, None]
        suppression = np.maximum(before - anchor, 0) - np.maximum(after - anchor, 0)
        loss_before = (before - y[:, None, None]) ** 2
        loss_after = (after - y[:, None, None]) ** 2
        benefit = loss_before - loss_after
        risk = np.broadcast_to(loss_before, (n, s, a))
        targets = np.stack([suppression, benefit, risk], axis=-1)
        self.model.fit(self.matrix(x, pred)[available.ravel()], targets.reshape(-1, 3)[available.ravel()])
        self.fixed_field = int(np.nanargmax(np.nanmean(np.where(available, suppression, np.nan), axis=(0, 1))))
        self.fixed_benefit_field = int(np.nanargmax(np.nanmean(np.where(available, benefit, np.nan), axis=(0, 1))))
        self.target_summary = {
            "records": int(n), "action_states": int(available.sum()),
            "mean_suppression": float(suppression[available].mean()),
            "mean_benefit": float(benefit[available].mean()),
            "fixed_suppression_field": ACTIONS[self.fixed_field],
            "fixed_benefit_field": ACTIONS[self.fixed_benefit_field],
        }
        return self

    def score(self, x, pred, space: StateSpace, kind: str, *, reported_missing: np.ndarray):
        n, s = pred.shape
        outputs = self.model.predict(self.matrix(x, pred)).reshape(n, s, len(ACTIONS), 3)
        if reported_missing.shape != (n, s, len(ACTIONS)):
            raise ValueError("Reported-state missingness shape mismatch")
        available = reported_missing
        if kind == "suppression":
            scores = outputs[..., 0]
        elif kind == "benefit":
            scores = outputs[..., 1]
        elif kind == "risk":
            # Common fixed-field capability: do not grant a field-choice oracle.
            scores = np.where(np.arange(len(ACTIONS))[None, None, :] == self.fixed_benefit_field, outputs[..., 2], -np.inf)
        elif kind == "fixed":
            scores = np.where(np.arange(len(ACTIONS))[None, None, :] == self.fixed_field, outputs[..., 0], -np.inf)
        elif kind == "none":
            scores = np.full_like(outputs[..., 0], -np.inf)
        else:
            raise ValueError(kind)
        return np.where(available, scores, -np.inf)


def allocate(scores: np.ndarray, states: np.ndarray, space: StateSpace, capacity: int):
    n = len(states)
    selected_scores = scores[np.arange(n), states]
    fields = np.argmax(selected_scores, axis=1)
    merit = selected_scores[np.arange(n), fields]
    eligible = np.isfinite(merit) & (merit > 0)
    ranking = np.lexsort((np.arange(n), -merit))
    selected = ranking[eligible[ranking]][:capacity]
    final = states.copy()
    chosen = np.full(n, -1, dtype=int)
    chosen[selected] = fields[selected]
    final[selected] = space.query_next[states[selected], fields[selected]]
    if np.any(final < 0):
        raise AssertionError("Cannot reveal an unhidden field")
    return final, chosen, merit


def _candidate_utility(i, states, pred, scores, valid, space, capacity, cost):
    n, s = pred.shape
    chosen_scores = scores[np.arange(n), states]
    current_merit = np.max(chosen_scores, axis=1)
    peers = np.arange(n) != i
    peer_merit = current_merit[peers]
    peer_ids = np.arange(n)[peers]
    best_field = np.argmax(scores[i], axis=1)
    candidate_merit = scores[i, np.arange(s), best_field]
    qualifies = np.zeros(s, dtype=bool)
    if capacity > 0:
        # Exact rank of each unilateral candidate against fixed peer reports.
        ahead = ((peer_merit[None] > candidate_merit[:, None]) |
            ((peer_merit[None] == candidate_merit[:, None]) & (peer_ids[None] < i)))
        qualifies = (ahead.sum(axis=1) < capacity) & np.isfinite(candidate_merit) & (candidate_merit > 0)
    finals = np.arange(s)
    finals[qualifies] = space.query_next[finals[qualifies], best_field[qualifies]]
    utility = pred[i, finals] - cost * space.masks.sum(axis=1)
    utility[~valid[i]] = -np.inf
    return utility


def strategic_response(pred, scores, valid, space: StateSpace, *, budget: float,
                       sweeps: int = 5, restarts: int = 2, cost: float = 0.0):
    """Capacity-aware unilateral search, with explicit remaining regret.

    This is not asserted to solve the joint game globally. The audit rule is
    recomputed after every proposed disclosure change. Price labels are absent.
    """
    if not 0 <= budget <= 1 or cost < 0:
        raise ValueError("Invalid budget or concealment cost")
    n, s = pred.shape
    if valid.shape != (n, s) or not valid[:, 0].all():
        raise ValueError("Every record needs a valid honest state")
    capacity = int(np.floor(budget * n))
    starts = [np.zeros(n, dtype=int)]
    if restarts > 1:
        starts.append(np.argmax(np.where(valid, pred - cost * space.masks.sum(axis=1)[None], -np.inf), axis=1))
    for k in range(2, restarts):
        rng = np.random.default_rng(1931 + k)
        starts.append(np.array([rng.choice(np.flatnonzero(v)) for v in valid]))
    runs = []
    for initial in starts:
        states = initial.copy()
        count = 0
        visited = {tuple(states)}
        cycle_detected = False
        for sweep in range(sweeps):
            changes = 0
            for i in range(n):
                values = _candidate_utility(i, states, pred, scores, valid, space, capacity, cost)
                # Keep the current report under ties: avoid cost-free oscillation.
                best = int(np.argmax(values))
                if values[best] > values[states[i]] + 1e-8:
                    states[i], changes = best, changes + 1
            count = sweep + 1
            if changes == 0:
                break
            signature = tuple(states)
            if signature in visited:
                cycle_detected = True
                break
            visited.add(signature)
        final, chosen, _ = allocate(scores, states, space, capacity)
        utility = pred[np.arange(n), final] - cost * space.masks[states].sum(axis=1)
        regret = np.array([
            max(0.0, _candidate_utility(i, states, pred, scores, valid, space, capacity, cost).max() - utility[i])
            for i in range(n)
        ])
        runs.append({"states": states, "final_state": final, "action": chosen,
            "utility": utility, "regret": regret, "sweeps": count,
            "cycle_detected": cycle_detected})
    result = max(runs, key=lambda run: float(run["utility"].sum()))
    result["capacity"] = capacity
    result["best_response_converged"] = bool((result["regret"] < 1e-7).all())
    if (result["action"] >= 0).sum() > capacity:
        raise AssertionError("Hard capacity exceeded")
    return result


def audit_deviations(pred, scores, valid, states, space: StateSpace, capacity: int, cost: float):
    """Independent exhaustive check through the actual allocator.

    Holds peer reports fixed and re-runs allocation for each feasible report.
    The quote envelope is unilateral, not a simultaneous batch upper bound.
    """
    n = len(states)
    current_final, _, _ = allocate(scores, states, space, capacity)
    current_quote = pred[np.arange(n), current_final]
    current_net = current_quote - cost * space.masks[states].sum(axis=1)
    maximum_quote, maximum_net = current_quote.copy(), current_net.copy()
    for i in range(n):
        for candidate in np.flatnonzero(valid[i]):
            trial = states.copy()
            trial[i] = candidate
            final, _, _ = allocate(scores, trial, space, capacity)
            quote = pred[i, final[i]]
            maximum_quote[i] = max(maximum_quote[i], quote)
            maximum_net[i] = max(maximum_net[i], quote - cost * space.masks[candidate].sum())
    return {"regret": np.maximum(maximum_net - current_net, 0), "maximum_quote": maximum_quote}


def simulate_market(n: int, seed: int):
    """Stipulated synthetic market, not inferred seller behavior."""
    rng = np.random.default_rng(seed)
    make = rng.integers(0, 5, n)
    variant = rng.integers(0, 4, n)
    age = rng.integers(1, 19, n)
    mileage = np.maximum(100, age * rng.lognormal(np.log(15000), 0.4, n))
    condition = rng.choice(4, n, p=[0.12, 0.28, 0.42, 0.18])
    automatic = rng.binomial(1, 0.45 + 0.06 * (make > 2), n)
    diesel = rng.binomial(1, 0.4, n)
    power = 4 + make + 2 * variant + rng.integers(0, 3, n)
    # Price uses interactions and idiosyncratic noise, not the model's own output.
    log_price = (10.3 + 0.23 * make + 0.1 * variant - 0.072 * age
        - 0.20 * np.log1p(mileage / 50000) + 0.12 * condition
        + 0.08 * automatic + 0.04 * diesel + 0.02 * power
        - 0.06 * (condition == 0) * (age > 10) + rng.normal(0, 0.1, n))
    frame = pd.DataFrame({
        "listing_id": [f"syn-{seed}-{i:07d}" for i in range(n)],
        "make": [f"M{m}" for m in make],
        "model": [f"M{m}-V{v}" for m, v in zip(make, variant)],
        "year": 2024 - age,
        "mileage_km": mileage,
        "transmission": np.where(automatic, "Automatic", "Manual"),
        "fuel_type": np.where(diesel, "Diesel", "Petrol"),
        "feat_body_condition": np.array(["Poor", "Fair", "Good", "Excellent"])[condition],
        "fiscal_power": power.astype(float),
        "location": rng.choice(["A", "B", "C"], n),
        "target_log": log_price,
    })
    # Benign missingness already exists; it is never artificially revealed.
    for field in ACTIONS:
        frame.loc[rng.random(n) < 0.04, field] = np.nan
    return frame
