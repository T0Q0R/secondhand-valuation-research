"""Recovery-gain edge regularization on the frozen residual training objective.
Derived from frozen savval.Valuator.train_residual; original module never patched.
Same loss, RNG, optimizer resets and epochs. Head parameters fixed within a round;
only current quote inputs refresh per epoch or per minibatch. No gradient through scores.
Search remains heuristic even at20sweeps/4starts; log residual regret explicitly.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn
from savval import ActionHeads, Valuator, strategic_response, allocate

def train_float64_residual(self, frame: pd.DataFrame, y: np.ndarray, config: dict,
                   seed: int, policy: "ActionHeads | None", *, gap_weight: float | None = None,
                   policy_aware: bool = True, policy_kind: str = "suppression",
                   epochs: int | None = None):
    torch.manual_seed(seed)
    x, base, valid = self.arrays(frame)
    if x.dtype != np.float64 or base.dtype != np.float64:
        raise TypeError('Use Float64Valuator so prediction and training share float64 residual inputs')
    reported_missing = self.space.reported_missing(frame)
    if self.residual is None:
        self.residual = nn.Sequential(nn.Linear(x.shape[-1], self.width, dtype=torch.float32), nn.ReLU(),
            nn.Linear(self.width, self.width, dtype=torch.float32), nn.ReLU(), nn.Linear(self.width, 1, dtype=torch.float32))
        nn.init.zeros_(self.residual[-1].weight)
        nn.init.zeros_(self.residual[-1].bias)
    self.residual = self.residual.to(dtype=torch.float64)
    optimizer = torch.optim.AdamW(self.residual.parameters(), lr=config["learning_rate"], weight_decay=1e-4, foreach=False, fused=False)
    rng = np.random.default_rng(seed)
    beta = config["gap_penalty_weight"] if gap_weight is None else gap_weight
    tensor_x, tensor_base = torch.from_numpy(x), torch.from_numpy(base)
    # Preserve the frozen trainer's original target rounding before promotion.
    tensor_y = torch.tensor(y, dtype=torch.float32).to(dtype=torch.float64)
    logs = []
    refresh = config.get("mechanism_score_refresh", "epoch")
    assert refresh in ("epoch", "batch")
    steps = config["residual_epochs"] if epochs is None else epochs
    for epoch in range(steps):
        total = 0.0
        total_path = 0.0
        diagnostics = []
        # Refresh action scores once per epoch from the current model.
        # Scores are a frozen surrogate within an epoch; gradients flow
        # through the selected final-price state, not a discrete allocator.
        score_epoch = None
        if policy is not None and refresh == "epoch":
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
            if policy is not None:
                selected_scores = (policy.score(x[idx], detached, self.space, policy_kind,
                    reported_missing=reported_missing[idx]) if refresh == "batch" else score_epoch[idx])
            if policy is not None and policy_aware:
                attack = strategic_response(detached, selected_scores, valid[idx], self.space,
                    budget=config.get("training_budget", 0.1),
                    sweeps=config.get("training_attacker_sweeps", 2), restarts=config.get("mechanism_restarts", 1),
                    cost=config["concealment_cost_log"])
                final_states = attack["final_state"]
                diagnostics.append(dict(n=len(idx), regret_sum=float(attack["regret"].sum()),
                    max_regret=float(attack["regret"].max()), converged=attack["best_response_converged"],
                    sweeps=attack["sweeps"], cycle=attack["cycle_detected"]))
            else:
                final_states = np.argmax(np.where(valid[idx], detached, -np.inf), axis=1)
                if policy is not None:
                    final_states = allocate(selected_scores, final_states, self.space,
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
            # Training-only recovery graph; no hidden value enters deployed prediction.
            before_gain = torch.relu(predicted - honest.detach()[:, None])
            after_gain = torch.relu(predicted[:, self.space.query_next] - honest.detach()[:, None, None])
            edges = valid_tensor[:, :, None] & torch.as_tensor(self.space.masks.astype(bool))[None, :, :]
            increments = torch.relu(after_gain - before_gain[:, :, None])
            path_loss = (increments * edges).sum() / edges.sum().clamp_min(1)
            augmented = (((predicted - by[:, None]) ** 2) * valid_tensor).sum(dim=1) / valid_tensor.sum(dim=1)
            loss = natural + 0.25 * augmented.mean() + config["attack_loss_weight"] * adversarial + beta * gap + config["anchor_weight"] * anchoring + config.get("recovery_path_weight", 0.) * path_loss
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.residual.parameters(), 5.0)
            optimizer.step()
            total += float(loss.detach()) * len(idx)
            total_path += float(path_loss.detach()) * len(idx)
        logs.append({"epoch": epoch + 1, "loss": total / len(frame), "mean_training_path_penalty": total_path / len(frame),
            "response_batches": len(diagnostics),
            "response_rows": sum(d["n"] for d in diagnostics),
            "mean_training_regret": sum(d["regret_sum"] for d in diagnostics) / max(1,sum(d["n"] for d in diagnostics)),
            "max_training_regret": max((d["max_regret"] for d in diagnostics),default=0.),
            "nonconverged_batches": sum(not d["converged"] for d in diagnostics),
            "cycle_batches": sum(d["cycle"] for d in diagnostics),
            "total_search_sweeps": sum(d["sweeps"] for d in diagnostics)})
    return logs


FROZEN_TRAINING_SHA256 = 'c19dad6d140ea3a43a068806e309cc2f6ca1c4a5070cb4ef594cbf167aae38f3'


class Float64Valuator(Valuator):
    """Preserve original encoded/base values, promote residual arithmetic only."""
    def arrays(self, frame):
        states, valid = self.space.materialize(frame)
        n, count = valid.shape
        x = self.encoder.transform(states).reshape(n, count, -1)
        base = self.backbone.predict(self.encoder.tree_frame(states), thread_count=1).reshape(n, count)
        # Preserve original backbone's float32 rounding, then promote.
        return x.astype(np.float64), base.astype(np.float32).astype(np.float64), valid

    @classmethod
    def from_frozen_backbone(cls, model):
        frozen_source = Path(__file__).resolve().parents[2] / 'experiments/recovery_path_training_v1.py'
        if hashlib.sha256(frozen_source.read_bytes()).hexdigest() != FROZEN_TRAINING_SHA256:
            raise RuntimeError('Frozen training source changed')
        return cls(copy.deepcopy(model.backbone), copy.deepcopy(model.encoder),
                   copy.deepcopy(model.space), model.width)
