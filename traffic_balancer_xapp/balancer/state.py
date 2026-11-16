"""In-memory state for the traffic_balancer xApp.

Per-UE KPM samples flow in from `kpm_ingest.py` keyed by slice id (sd).
The slice is determined at indication time by which subscription delivered
the IND (sub_id routing), not by guessing from the UE id — that mapping
is fragile under attach order and UE mobility.

The original convention of calling sd=16777215 "LOS" and sd=1 "NLOS" was
a property of the *experimental setup* (the LOS UE happened to sit on
the first slice), not of the slices themselves. Once UEs move, those
labels stop matching the physical reality. We keep the LOS/NLOS
terminology in the report for the static-sweep narrative, but in the
code the slices are identified by their `sd` only.

Slice ids used by the demo (must match `kpm_ingest.SST_SD_PAIRS` and
the gNB's NSSAI configuration):
    sd = 16777215    # "S1" in the report — first slice
    sd = 1           # "S2" in the report — second slice
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple


# ---- Slice identifiers -----------------------------------------------------

SST: int = 1
SD_S1: int = 16777215   # "S1" — first slice (was labelled LOS in prior runs)
SD_S2: int = 1          # "S2" — second slice (was labelled NLOS in prior runs)

#: Tuple of all sd values the xApp tracks. Iteration order matters only for
#: deterministic logging; lookups use dict semantics elsewhere.
SDS: Tuple[int, ...] = (SD_S1, SD_S2)


# KPM measurement names we care about (per UE).
KPM_COLS = (
    "DRB.PdcpSduVolumeDL",
    "DRB.PdcpSduVolumeUL",
    "DRB.RlcSduDelayDl",
    "DRB.UEThpDl",
    "DRB.UEThpUl",
)


# ---- Sample / snapshot ----------------------------------------------------

@dataclass
class Sample:
    """One KPM record for one UE at one timestamp, attributed to a slice
    via the subscription it arrived on."""
    timestamp_ms: int
    ue_id: str           # "ue_<int>" label, used for display / CSV
    ran_ue_id: int       # raw int from KPM; needed by RC controls (the RC SM
                         # format requires a UE-id field even for slice-level
                         # actions — see RcSender.send)
    sd: int              # the slice's sd (network-stable; replaces the
                         # earlier los/nlos string label)
    gnb_id: str
    metrics: Dict[str, float] = field(default_factory=dict)

    def get(self, key: str, default: float = 0.0) -> float:
        return self.metrics.get(key, default)


@dataclass
class StateSnapshot:
    """Latest sample per slice, keyed by `sd` (int)."""
    timestamp_ms: int
    per_sd: Dict[int, Optional[Sample]]

    def has_all_slices(self) -> bool:
        return all(self.per_sd.get(sd) is not None for sd in SDS)

    def thp(self, sd: int) -> float:
        s = self.per_sd.get(sd)
        return 0.0 if s is None else float(s.get("DRB.UEThpDl"))

    def pdcp_dl(self, sd: int) -> float:
        s = self.per_sd.get(sd)
        return 0.0 if s is None else float(s.get("DRB.PdcpSduVolumeDL"))

    def delay_dl(self, sd: int) -> float:
        """Latest RLC DL delay for the slice (units: 0.01 ms per 3GPP)."""
        s = self.per_sd.get(sd)
        return 0.0 if s is None else float(s.get("DRB.RlcSduDelayDl"))

    def ran_ue_id_for(self, sd: int) -> Optional[int]:
        """Return the raw int UE-id last reported for this slice, or None
        if the slice hasn't reported yet. Callers should check
        `has_all_slices()` before relying on this."""
        s = self.per_sd.get(sd)
        return None if s is None else s.ran_ue_id


# ---- Sample ring buffer ---------------------------------------------------

class SampleBuffer:
    """Thread-safe ring buffer of `Sample`s. Producers (the KPM ingest
    threads) push; the controller pulls snapshots."""

    def __init__(self, maxlen: int = 600) -> None:
        self._buf: Deque[Sample] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._has_data = threading.Event()

    def push(self, sample: Sample) -> None:
        with self._lock:
            self._buf.append(sample)
        self._has_data.set()

    def wait_for_data(self, timeout: Optional[float] = None) -> bool:
        """Block until at least one sample has arrived. Returns False on timeout."""
        return self._has_data.wait(timeout=timeout)

    def snapshot(self) -> StateSnapshot:
        """Most recent sample per slice."""
        with self._lock:
            latest: Dict[int, Optional[Sample]] = {sd: None for sd in SDS}
            # iterate from newest backward so the first hit per sd wins
            for sample in reversed(self._buf):
                if sample.sd in latest and latest[sample.sd] is None:
                    latest[sample.sd] = sample
                if all(latest[sd] is not None for sd in SDS):
                    break
            ts = max((s.timestamp_ms for s in latest.values() if s is not None),
                     default=int(time.time() * 1000))
        return StateSnapshot(timestamp_ms=ts, per_sd=latest)

    def recent(self, n: int = 5) -> List[Sample]:
        """Last n samples (any slice). For debugging / GUI."""
        with self._lock:
            return list(self._buf)[-n:]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)
