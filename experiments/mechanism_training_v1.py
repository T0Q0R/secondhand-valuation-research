"""Controlled epoch/batch score refresh and training response search intervention.
Derived from frozen savval.Valuator.train_residual; original module never patched.
Same loss, RNG, optimizer resets and epochs. Head parameters fixed within a round;
only current quote inputs refresh per epoch or per minibatch. No gradient through scores.
Search remains heuristic even at20sweeps/4starts; log residual regret explicitly.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import torch
from torch import nn
from savval import ActionHeads, strategic_response, allocate

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
    refresh = config.get("mechanism_score_refresh", "epoch")
    assert refresh in ("epoch", "batch")
    steps = config["residual_epochs"] if epochs is None else epochs
    for epoch in range(steps):
        total = 0.0
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
            augmented = (((predicted - by[:, None]) ** 2) * valid_tensor).sum(dim=1) / valid_tensor.sum(dim=1)
            loss = natural + 0.25 * augmented.mean() + config["attack_loss_weight"] * adversarial + beta * gap + config["anchor_weight"] * anchoring
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.residual.parameters(), 5.0)
            optimizer.step()
            total += float(loss.detach()) * len(idx)
        logs.append({"epoch": epoch + 1, "loss": total / len(frame),
            "response_batches": len(diagnostics),
            "response_rows": sum(d["n"] for d in diagnostics),
            "mean_training_regret": sum(d["regret_sum"] for d in diagnostics) / max(1,sum(d["n"] for d in diagnostics)),
            "max_training_regret": max((d["max_regret"] for d in diagnostics),default=0.),
            "nonconverged_batches": sum(not d["converged"] for d in diagnostics),
            "cycle_batches": sum(d["cycle"] for d in diagnostics),
            "total_search_sweeps": sum(d["sweeps"] for d in diagnostics)})
    return logs
