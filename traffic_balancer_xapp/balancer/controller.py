"""Decision loop for the traffic_balancer xApp.

Runs in its own daemon thread. Each iteration:

  1. Wait for fresh KPM data (`SampleBuffer.wait_for_data`).
  2. Take a `StateSnapshot`.
  3. Ask the active `Policy` for `(min_S1, min_S2)`.
  4. If the action differs from the last applied one, push two RC
     controls (decreasing slice first, then increasing) using the
     ACK-gated retry pattern lifted from `prb_control_xapp/rc_xapp.py`.
  5. Append one row to the per-run CSV.

Step 4 is the only place where the gNB state changes. The
`sum(min) > 100` guard runs before sending — both at policy registration
time (StaticPolicy validates) and again here as defence in depth — to
avoid the `assert(0)` in `ran_func_rc.c:1193`.
"""

from __future__ import annotations

import csv
import math
import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Optional

from .policies import Action, Policy
from .state import SD_S1, SD_S2, SampleBuffer, StateSnapshot


# `min_S1` from the policy goes to slice SD_S1; `min_S2` goes to SD_S2.
# These are stable code aliases for "first" / "second" slice — they don't
# track UE position, so LOS↔NLOS movement does not invalidate them.


@dataclass
class ControlOutcome:
    """Per-step record written to the run CSV."""
    timestamp_ms: int
    policy: str
    min_s1: int
    min_s2: int
    applied: bool
    thp_s1: float
    thp_s2: float
    pdcp_s1: float
    pdcp_s2: float
    reward: float        # PF utility computed from this snapshot


class RcSender:
    """Wraps `RadioResourceAllocationControl` with the ACK-gated retry pattern.

    The decision-loop calls `send(sd, min_ratio)` and blocks until the gNB
    ACKs, resending every `ack_timeout` seconds. Identical pattern to
    `prb_control_xapp/rc_xapp.py:_send_with_retry`.
    """

    def __init__(self, rc_func, gnb, ran_func_dsc, logger,
                 ack_timeout: float = 1.0, max_retries: Optional[int] = None) -> None:
        self.rc_func = rc_func
        self.gnb = gnb
        self.ran_func_dsc = ran_func_dsc
        self.logger = logger
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries  # None = retry forever (matches rc_xapp.py)
        self._ack_event = threading.Event()
        # Single callback shared across sends; clear() before each send so
        # late ACKs from a previous send can't satisfy the next wait.
        self.rc_func.register_control_ack_suc_callback(self._on_ack)

    def _on_ack(self, summary=None) -> None:
        self._ack_event.set()
        meid = ""
        if summary is not None:
            try:
                meid = summary.get("meid", "")
            except Exception:
                pass
        self.logger.info("[RcSender] ACK received from {}".format(meid))

    def send(self, sd: int, min_ratio: int, ran_ue_id: int, label: str = "") -> bool:
        """Set (sd, min), call send(), wait for ACK, retry on timeout.

        `ran_ue_id` is the int UE-id of a UE currently on the target slice.
        The RC SM format requires a UE-id field even for slice-level actions
        (control_action_id=6); we use the one most recently reported by KPM
        for that slice. Without it, the decorator's `get_mock_ue_id` chokes
        on `None` and the send dies.
        """
        self.rc_func.set_sd(sd)
        self.rc_func.set_min_prb_policy_ratio(min_ratio)
        # The decorator falls back to `self.ue_id` when `ue_id_struct` is None
        # in `generate_control_request` — set it to the slice's current UE.
        self.rc_func.ue_id = int(ran_ue_id)

        attempt = 0
        while True:
            attempt += 1
            self._ack_event.clear()
            self.logger.info(
                "[RcSender] {} sd={} min={} ue={} attempt {}".format(
                    label, sd, min_ratio, ran_ue_id, attempt
                )
            )
            self.rc_func.send(
                e2_node_id=self.gnb.inventory_name,
                ran_func_dsc=self.ran_func_dsc,
                ue_id_struct=None,
                control_action_id=6,
            )
            if self._ack_event.wait(timeout=self.ack_timeout):
                self.logger.info(
                    "[RcSender] {} sd={} min={} ACKed on attempt {}".format(
                        label, sd, min_ratio, attempt
                    )
                )
                return True
            if self.max_retries is not None and attempt >= self.max_retries:
                self.logger.error(
                    "[RcSender] {} sd={} min={} exhausted {} retries".format(
                        label, sd, min_ratio, self.max_retries
                    )
                )
                return False
            self.logger.warning(
                "[RcSender] {} sd={} min={} no ACK after {}s — resending".format(
                    label, sd, min_ratio, self.ack_timeout
                )
            )


class BalancerController:
    """Runs the policy/control loop in a background thread."""

    def __init__(self, buffer: SampleBuffer, policy: Policy, sender: RcSender, logger,
                 decision_period_s: float = 1.0,
                 csv_path: Optional[str] = None) -> None:
        self.buffer = buffer
        self.policy = policy
        self.sender = sender
        self.logger = logger
        self.decision_period_s = decision_period_s
        self.csv_path = csv_path

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_action: Optional[Action] = None
        # `_has_prev_action` tracks whether we owe the policy an update.
        # Set True after the first act(), cleared on policy swap so the
        # new policy doesn't get a reward for an arm it didn't choose.
        self._has_prev_action: bool = False
        self._policy_lock = threading.Lock()
        self._csv_fh = None
        self._csv_writer = None

    # ---- Policy swap (GUI hook for the follow-up pass) ---------------------

    def set_policy(self, policy: Policy) -> None:
        with self._policy_lock:
            self.policy = policy
            # Don't feed the new policy a reward for an action it didn't take.
            self._has_prev_action = False
            self.logger.info("[Controller] policy -> {}".format(policy.name))

    # ---- Lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self.csv_path:
            os.makedirs(os.path.dirname(self.csv_path) or ".", exist_ok=True)
            self._csv_fh = open(self.csv_path, "w", newline="")
            self._csv_writer = csv.writer(self._csv_fh)
            self._csv_writer.writerow([
                "timestamp_ms", "policy", "min_S1", "min_S2", "applied",
                "thp_S1", "thp_S2", "pdcp_S1", "pdcp_S2", "reward",
            ])
            self._csv_fh.flush()
            self.logger.info("[Controller] logging to {}".format(self.csv_path))

        self._thread = threading.Thread(target=self._loop, daemon=True, name="balancer-ctrl")
        self._thread.start()
        self.logger.info("[Controller] decision loop started (period {}s)".format(self.decision_period_s))

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        if self._csv_fh is not None:
            self._csv_fh.close()
            self._csv_fh = None

    # ---- Loop body ---------------------------------------------------------

    def _loop(self) -> None:
        # Wait for at least one sample before we start deciding.
        self.buffer.wait_for_data(timeout=60.0)
        self.logger.info("[Controller] first KPM sample observed, entering loop")

        while not self._stop.is_set():
            step_start = time.monotonic()
            try:
                self._step_once()
            except Exception as exc:
                # Log and keep going — a bad sample or transient failure shouldn't kill the loop.
                # mdclogpy.Logger has no .exception(); use .error() with the formatted traceback.
                self.logger.error(
                    "[Controller] step error: {}\n{}".format(exc, traceback.format_exc())
                )

            # Sleep the remainder of the decision period.
            elapsed = time.monotonic() - step_start
            sleep_for = self.decision_period_s - elapsed
            if sleep_for > 0:
                self._stop.wait(timeout=sleep_for)

    def _step_once(self) -> None:
        snap = self.buffer.snapshot()
        if not snap.has_all_slices():
            self.logger.debug("[Controller] waiting for both slices to report")
            return

        reward = self._compute_reward(snap)

        # If we picked an action last step, this snapshot is its reward —
        # feed it back to the policy BEFORE picking the next action. Static
        # policies treat update() as a no-op; LinUCB uses it.
        if self._has_prev_action:
            with self._policy_lock:
                try:
                    self.policy.update(reward)
                except Exception as exc:
                    self.logger.error(
                        "[Controller] policy.update failed: {}\n{}".format(
                            exc, traceback.format_exc()))

        with self._policy_lock:
            policy = self.policy
        action = policy.act(snap)
        action = self._validate_action(action)
        applied = self._maybe_apply(action, snap)
        self._has_prev_action = True

        self._log_row(ControlOutcome(
            timestamp_ms=snap.timestamp_ms,
            policy=policy.name,
            min_s1=action[0],
            min_s2=action[1],
            applied=applied,
            thp_s1=snap.thp(SD_S1),
            thp_s2=snap.thp(SD_S2),
            pdcp_s1=snap.pdcp_dl(SD_S1),
            pdcp_s2=snap.pdcp_dl(SD_S2),
            reward=reward,
        ))

    @staticmethod
    def _compute_reward(snap: StateSnapshot) -> float:
        """Proportional-fair utility:  log(thp_S1) + log(thp_S2).

        Floored at 1.0 kbps so a momentarily-idle slice doesn't push the
        reward to -inf. Result is in nats."""
        thp_s1 = max(snap.thp(SD_S1), 1.0)
        thp_s2 = max(snap.thp(SD_S2), 1.0)
        return math.log(thp_s1) + math.log(thp_s2)

    def _validate_action(self, action: Action) -> Action:
        """Clamp to a safe (sum <= 100, non-negative, <=100 each)."""
        m1, m2 = int(action[0]), int(action[1])
        m1 = max(0, min(100, m1))
        m2 = max(0, min(100, m2))
        if m1 + m2 > 100:
            # Scale both down proportionally so the sum is 100. This should
            # never be needed for well-behaved policies but guards against
            # bugs / GUI manual mode.
            scale = 100.0 / (m1 + m2)
            m1 = int(m1 * scale)
            m2 = int(m2 * scale)
            self.logger.warning("[Controller] clamped action: sum>100 -> ({}, {})".format(m1, m2))
        return (m1, m2)

    def _maybe_apply(self, action: Action, snap: StateSnapshot) -> bool:
        if self._last_action == action:
            self.logger.debug("[Controller] no-op: action unchanged ({}, {})".format(*action))
            return False

        prev_s1, prev_s2 = self._last_action if self._last_action is not None else (None, None)
        new_s1, new_s2 = action

        # Look up the int UE-id reported for each slice in the freshest KPM
        # sample. Required because the RC SM format demands a UE-id field
        # even for slice-level (action 6) controls — the decorator builds
        # the struct via get_mock_ue_id(self.ue_id), so a None blows up.
        ue_s1 = snap.ran_ue_id_for(SD_S1)
        ue_s2 = snap.ran_ue_id_for(SD_S2)
        if ue_s1 is None or ue_s2 is None:
            # _step_once already guards has_all_slices(), so reaching here
            # means a sample disappeared between the check and now — skip.
            self.logger.warning(
                "[Controller] missing ue_id (S1={}, S2={}); skipping apply".format(
                    ue_s1, ue_s2
                )
            )
            return False

        # Decide order: send the slice whose min is going DOWN first so the
        # running sum never exceeds 100 mid-transition. If both equal or
        # ambiguous, send S2 first by default (matches the convention used
        # in the prior sweep scripts).
        s2_decreasing = prev_s2 is not None and new_s2 < prev_s2
        s1_decreasing = prev_s1 is not None and new_s1 < prev_s1
        s2_first = s2_decreasing or (not s1_decreasing)

        if s2_first:
            self.sender.send(SD_S2, new_s2, ran_ue_id=ue_s2,
                             label="S2(sd={})".format(SD_S2))
            self.sender.send(SD_S1, new_s1, ran_ue_id=ue_s1,
                             label="S1(sd={})".format(SD_S1))
        else:
            self.sender.send(SD_S1, new_s1, ran_ue_id=ue_s1,
                             label="S1(sd={})".format(SD_S1))
            self.sender.send(SD_S2, new_s2, ran_ue_id=ue_s2,
                             label="S2(sd={})".format(SD_S2))

        self._last_action = action
        self.logger.info(
            "[Controller] applied action S1=(sd={}, min={}, ue={}) S2=(sd={}, min={}, ue={})".format(
                SD_S1, new_s1, ue_s1, SD_S2, new_s2, ue_s2,
            )
        )
        return True

    def _log_row(self, row: ControlOutcome) -> None:
        if self._csv_writer is None:
            return
        self._csv_writer.writerow([
            row.timestamp_ms, row.policy, row.min_s1, row.min_s2, int(row.applied),
            row.thp_s1, row.thp_s2, row.pdcp_s1, row.pdcp_s2, row.reward,
        ])
        self._csv_fh.flush()
