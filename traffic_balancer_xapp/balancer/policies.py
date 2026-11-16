"""Policy implementations for the traffic_balancer xApp.

A policy maps a `StateSnapshot` to an action `(min_S1, min_S2)`:
  - min_S1 is the PRB min ratio for slice SD_S1 (sd=16777215)
  - min_S2 is the PRB min ratio for slice SD_S2 (sd=1)
  - min_S1 + min_S2 <= 100  (gNB invariant; the controller also enforces)

v1 ships four policies:
  - EqualPolicy: always (50, 50). Sanity baseline.
  - StaticG6Policy: always (70, 30). The static-sweep oracle.
  - DemandProportionalPolicy: scale mins by recent PDCP-DL volume per slice.
  - LinUCBPolicy: 7-arm contextual bandit over the sweep grid.

Lifecycle the controller drives:
  step t:    action_t = policy.act(snap_t)
             [apply action_t]
  step t+1:  reward_t = log(thp_S1) + log(thp_S2)  measured on snap_(t+1)
             policy.update(reward_t)
             action_(t+1) = policy.act(snap_(t+1))
             ...

`update()` takes only the scalar reward — the policy is expected to have
stashed whatever state it needs about the previous action / features
during its `act()` call. This keeps the controller stateless wrt policy
internals.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np

from .state import SD_S1, SD_S2, StateSnapshot


Action = Tuple[int, int]


# ---- ABC ------------------------------------------------------------------

class Policy(ABC):
    """Base class for PRB-quota policies."""

    name: str = "abstract"

    @abstractmethod
    def act(self, snapshot: StateSnapshot) -> Action:
        """Return (min_S1, min_S2). Must satisfy min_S1 + min_S2 <= 100."""

    def update(self, reward: float) -> None:
        """Hook for learning policies. No-op for static / heuristic ones."""
        return None


# ---- Static policies ------------------------------------------------------

class StaticPolicy(Policy):
    """Always returns the same (min_S1, min_S2)."""

    def __init__(self, min_s1: int, min_s2: int, name: str = "static"):
        if min_s1 + min_s2 > 100:
            raise ValueError(
                "min_S1 + min_S2 must be <= 100; got {}+{}={}".format(
                    min_s1, min_s2, min_s1 + min_s2))
        if min_s1 < 0 or min_s2 < 0:
            raise ValueError("min_S1 and min_S2 must be non-negative")
        self._action: Action = (int(min_s1), int(min_s2))
        self.name = name

    def act(self, snapshot: StateSnapshot) -> Action:
        return self._action


class EqualPolicy(StaticPolicy):
    """Always (50, 50). The naive fairness baseline."""

    def __init__(self) -> None:
        super().__init__(min_s1=50, min_s2=50, name="equal")


class StaticG6Policy(StaticPolicy):
    """Static sweep oracle: (70, 30). PF utility peaks here per sweep_test."""

    def __init__(self) -> None:
        super().__init__(min_s1=70, min_s2=30, name="g6")


# ---- Heuristic policy -----------------------------------------------------

class DemandProportionalPolicy(Policy):
    """Scale min ratios by recent PDCP-DL volume per slice.

    Reads the latest sample's `DRB.PdcpSduVolumeDL` for each slice. If both
    slices have near-zero demand, falls back to (50, 50). Each min is
    clipped to `[min_floor, 100 - min_floor]` so neither slice is starved.

    Limitations (v1):
      - Single-sample read → jittery if demand is bursty.
      - No history weighting; bursts swing the action.
    """

    name = "demand_prop"

    def __init__(self, min_floor: int = 10):
        self.min_floor = int(min_floor)
        if self.min_floor < 0 or self.min_floor * 2 > 100:
            raise ValueError("min_floor must be in [0, 50]")

    def act(self, snapshot: StateSnapshot) -> Action:
        d1 = snapshot.pdcp_dl(SD_S1)
        d2 = snapshot.pdcp_dl(SD_S2)
        total = d1 + d2
        if total < 1.0:
            return (50, 50)

        m1 = int(round((d1 / total) * 100))
        m2 = 100 - m1

        # Clip each to [min_floor, 100 - min_floor], then re-balance so sum=100.
        lo, hi = self.min_floor, 100 - self.min_floor
        m1 = max(lo, min(hi, m1))
        m2 = 100 - m1
        m2 = max(lo, min(hi, m2))
        m1 = 100 - m2
        return (m1, m2)


# ---- LinUCB ----------------------------------------------------------------

class LinUCBPolicy(Policy):
    """7-arm contextual bandit over the static-sweep grid.

    Arms (the report's §5.3 grid):
        (20,80) (30,70) (40,60) (50,50) (60,40) (70,30) (80,20)

    Feature vector (d=7):
        φ = [thp_S1/1e5, thp_S2/1e5,
             pdcp_S1/1e5, pdcp_S2/1e5,
             delay_S1/1e6, delay_S2/1e6,
             1.0]   # bias

    Per-arm linear model:    r ≈ θ_a · φ
        A_a ← A_a + φφᵀ
        b_a ← b_a + r·φ
        θ̂_a = A_a⁻¹ b_a

    UCB selection:  argmax_a   θ̂_a · φ + α · √(φᵀ A_a⁻¹ φ)

    Round-robin warmup: before any UCB call, this policy pulls each arm
    `warmup_per_arm` times in a fixed sequence. With 7 arms × 5 = 35
    forced picks at 5 s decision period that's ~3 min of seed exploration
    where every arm gets equal evidence. Without this, the very first
    pick is always arm 0 (tie-breaking on equal UCB scores), and arms
    that draw unlucky early rewards never recover — that's the failure
    mode the first long run hit.

    Defaults tuned for the OAI/FlexRIC setup at saturating UDP traffic:
      alpha=5.0   — keeps the exploration bonus comparable to arm-mean
                    gaps (~0.5 nats) for longer
      lambda_=1.0 — slower posterior collapse than the textbook 0.1
      warmup_per_arm=5 — every arm is sampled at least 5 times before UCB
    """

    name = "linucb"

    ARMS: List[Action] = [
        (20, 80), (30, 70), (40, 60), (50, 50), (60, 40), (70, 30), (80, 20),
    ]

    def __init__(self, alpha: float = 5.0, lambda_: float = 1.0,
                 warmup_per_arm: int = 5):
        self.alpha = float(alpha)
        self.lambda_ = float(lambda_)
        self.warmup_per_arm = int(warmup_per_arm)
        self.d = 7
        self.A: List[np.ndarray] = [self.lambda_ * np.eye(self.d) for _ in self.ARMS]
        self.b: List[np.ndarray] = [np.zeros(self.d) for _ in self.ARMS]
        # Round-robin warmup queue: arm0,arm1,...,armN, arm0,arm1,...,armN, ...
        # Length = num_arms * warmup_per_arm.
        self._warmup_queue: List[int] = (
            list(range(len(self.ARMS))) * self.warmup_per_arm
        )
        self._warmup_idx: int = 0
        # Stashed by act(), consumed by update():
        self._last_arm: Optional[int] = None
        self._last_features: Optional[np.ndarray] = None
        # One-shot "warmup done" marker so we log the transition only once.
        self._warmup_logged_done: bool = False
        # Inject our own logger only when a host gives us one (via
        # set_logger); silent fallback otherwise so this stays importable
        # from tests without a logger.
        self._logger = None

    def set_logger(self, logger) -> None:
        self._logger = logger

    def _features(self, snap: StateSnapshot) -> np.ndarray:
        return np.array([
            snap.thp(SD_S1) / 1e5,
            snap.thp(SD_S2) / 1e5,
            snap.pdcp_dl(SD_S1) / 1e5,
            snap.pdcp_dl(SD_S2) / 1e5,
            snap.delay_dl(SD_S1) / 1e6,
            snap.delay_dl(SD_S2) / 1e6,
            1.0,
        ], dtype=np.float64)

    def _in_warmup(self) -> bool:
        return self._warmup_idx < len(self._warmup_queue)

    def act(self, snap: StateSnapshot) -> Action:
        phi = self._features(snap)

        # Round-robin warmup phase: pull arms in a fixed sequence regardless
        # of UCB scores. Guarantees every arm gets `warmup_per_arm` clean
        # samples before exploitation can lock in.
        if self._in_warmup():
            arm_idx = self._warmup_queue[self._warmup_idx]
            self._warmup_idx += 1
            self._last_arm = arm_idx
            self._last_features = phi
            if self._logger:
                self._logger.info(
                    "[LinUCB] warmup pick {}/{} arm={} action={}".format(
                        self._warmup_idx, len(self._warmup_queue),
                        arm_idx, self.ARMS[arm_idx]))
            return self.ARMS[arm_idx]

        # Warmup just completed — log once.
        if not self._warmup_logged_done and self._logger:
            self._logger.info(
                "[LinUCB] warmup complete; entering UCB phase. "
                "alpha={} lambda={}".format(self.alpha, self.lambda_))
            self._warmup_logged_done = True

        # Standard LinUCB selection.
        scores: List[float] = []
        for i in range(len(self.ARMS)):
            A_inv = np.linalg.inv(self.A[i])
            theta_hat = A_inv @ self.b[i]
            mean = float(theta_hat @ phi)
            var = float(phi @ A_inv @ phi)
            bonus = self.alpha * math.sqrt(max(0.0, var))
            scores.append(mean + bonus)
        best = int(np.argmax(scores))
        self._last_arm = best
        self._last_features = phi
        return self.ARMS[best]

    def update(self, reward: float) -> None:
        if self._last_arm is None or self._last_features is None:
            return
        phi = self._last_features
        i = self._last_arm
        self.A[i] = self.A[i] + np.outer(phi, phi)
        self.b[i] = self.b[i] + float(reward) * phi


# ---- Registry --------------------------------------------------------------

_REGISTRY = {
    "equal": EqualPolicy,
    "g6": StaticG6Policy,
    "demand_prop": DemandProportionalPolicy,
    "linucb": LinUCBPolicy,
}


def get_policy(name: str) -> Policy:
    """Look up a policy by short name. Raises KeyError on unknown name."""
    if name not in _REGISTRY:
        raise KeyError(
            "unknown policy '{}'. Available: {}".format(name, sorted(_REGISTRY.keys())))
    return _REGISTRY[name]()


def available_policies() -> Tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))
