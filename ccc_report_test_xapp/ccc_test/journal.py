import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import (
    CccIndicationHeader,
    CccIndicationMessage,
    ReportedStructure,
)


class Outcome(Enum):
    PENDING = "pending"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    NOT_SENT = "not sent"


class AckKind(Enum):
    ACK = "RIC Control Acknowledge"
    FAILURE = "RIC Control Failure"


@dataclass(frozen=True)
class Indication:
    arrival_s: float
    reason: Optional[str]
    event_time: Optional[str]
    event_time_ntp: Optional[int]
    format: Optional[int]
    reported: Tuple[ReportedStructure, ...]
    raw_header: bytes
    raw_message: bytes

    def structures(self, nr_cell_id: Optional[int] = None) -> List[ReportedStructure]:
        if nr_cell_id is None:
            return list(self.reported)
        return [r for r in self.reported if r.nr_cell_id == nr_cell_id]

    def cell_ids(self) -> List[Optional[int]]:
        return sorted({r.nr_cell_id for r in self.reported}, key=lambda c: -1 if c is None else c)


def make_indication(hdr: CccIndicationHeader, msg: CccIndicationMessage, arrival_s: float) -> Indication:
    return Indication(arrival_s, hdr.indication_reason, hdr.event_time, hdr.event_time_ntp, msg.format,
                      tuple(msg.reported()), hdr.raw, msg.raw)


class Journal:
    """Everything the RIC tells the xApp, recorded from any thread.

    Subscriptions are known by the key of their plan entry. submgr names a subscription by its SubscriptionId and
    the RMR messages carry its E2EventInstanceId. The journal joins both in whatever order they arrive.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._cond = threading.Condition(threading.RLock())
        self._submgr_id: Dict[str, Optional[str]] = {}
        self._instance_id: Dict[str, int] = {}
        self._rejected: Dict[str, str] = {}
        self._by_instance: Dict[int, List[Indication]] = {}
        self._acks: List[Tuple[AckKind, float]] = []
        self._aborted = False

    def on_subscribed(self, key: str, submgr_id: Optional[str]) -> None:
        with self._cond:
            self._submgr_id[key] = submgr_id
            self._cond.notify_all()

    def on_resolved(self, submgr_id: str, instance_id: int) -> None:
        with self._cond:
            self._instance_id[submgr_id] = int(instance_id)
            self._cond.notify_all()

    def on_rejected(self, submgr_id: str, cause: str) -> None:
        with self._cond:
            self._rejected[submgr_id] = cause
            self._cond.notify_all()

    def on_indication(self, instance_id: int, indication: Indication) -> None:
        with self._cond:
            self._by_instance.setdefault(int(instance_id), []).append(indication)
            self._cond.notify_all()

    def on_control_ack(self, kind: AckKind) -> None:
        with self._cond:
            self._acks.append((kind, self.clock()))
            self._cond.notify_all()

    def abort(self) -> None:
        with self._cond:
            self._aborted = True
            self._cond.notify_all()

    @property
    def aborted(self) -> bool:
        with self._cond:
            return self._aborted

    def outcome(self, key: str) -> Outcome:
        with self._cond:
            if key not in self._submgr_id:
                return Outcome.PENDING
            submgr_id = self._submgr_id[key]
            if submgr_id is None:
                return Outcome.NOT_SENT
            if submgr_id in self._rejected:
                return Outcome.REJECTED
            if submgr_id in self._instance_id:
                return Outcome.ADMITTED
            return Outcome.PENDING

    def rejection_cause(self, key: str) -> Optional[str]:
        with self._cond:
            submgr_id = self._submgr_id.get(key)
            return None if submgr_id is None else self._rejected.get(submgr_id)

    def indications(self, key: str, since_s: float = float("-inf")) -> List[Indication]:
        with self._cond:
            submgr_id = self._submgr_id.get(key)
            instance_id = None if submgr_id is None else self._instance_id.get(submgr_id)
            if instance_id is None:
                return []
            return [i for i in self._by_instance.get(instance_id, []) if i.arrival_s >= since_s]

    def unknown_instances(self) -> List[int]:
        """E2EventInstanceIds of indications that no subscription of this run owns."""
        with self._cond:
            known = set(self._instance_id.values())
            return sorted(i for i in self._by_instance if i not in known)

    def acks(self, since_s: float = float("-inf")) -> List[AckKind]:
        with self._cond:
            return [kind for kind, t in self._acks if t >= since_s]

    def wait_until(self, predicate: Callable[[], bool], deadline_s: float) -> bool:
        """Wait until ``predicate`` holds or the clock reaches ``deadline_s``. Returns the last value of it."""
        with self._cond:
            while True:
                if predicate():
                    return True
                remaining = deadline_s - self.clock()
                if remaining <= 0 or self._aborted:
                    return False
                self._cond.wait(remaining)
