"""KPM ingestion with sub_id routing.

We subscribe twice — once per (sst, sd) — and remember the submgr_sub_id
returned by each `kpm_func.subscribe()` call. When each subscription
resolves asynchronously (`sub_resolved_callback` fires with the
E2EventInstanceId), we bridge the two ids so the indication callback can
look up the slice via the `sub_id` arg the framework stamps on every IND.

This is robust to:
  - UE attach order (no UE_TO_SLICE hardcode);
  - UE mobility (sub_id is bound at subscribe time and stays with the
    slice, not the UE);
  - new UEs attaching mid-run (they inherit the slice of whichever
    subscription delivers their IND).

If an indication arrives before its sub has been resolved, we log a
warning and drop the sample. The race is rare in practice because the
RIC completes the subscription handshake before the gNB starts streaming.
"""

from __future__ import annotations

import time
from typing import Dict, Optional

import numpy as np

from xdevsm.sm_framework.py_oran.kpm.enums import format_action_def_e
from xdevsm.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xdevsm.sm_framework.py_oran.kpm.enums import meas_type_enum
from xdevsm.sm_framework.py_oran.kpm.enums import meas_value_e

from .state import SDS, SST, Sample, SampleBuffer


def _decode_meas_type(meas_info) -> Optional[str]:
    """Decode the meas type name (a C ByteArray) to a Python str."""
    if meas_info.meas_type.type.value != meas_type_enum.NAME_MEAS_TYPE:
        return None
    name = meas_info.meas_type.value.name
    raw = bytes(np.ctypeslib.as_array(name.buf, shape=(name.len,)))
    return raw.decode("utf-8")


def _record_value(record) -> Optional[float]:
    """Decode an integer/real meas record value to a Python float."""
    v = record.value.value
    if v == meas_value_e.INTEGER_MEAS_VALUE:
        return float(record.union.int_val)
    if v == meas_value_e.REAL_MEAS_VALUE:
        return float(record.union.real_val)
    return None


class KpmIngest:
    """Owns the KPM subscriptions, the sub_id↔sd bridges, and the IND
    callback. Pushes per-UE `Sample`s into the shared `SampleBuffer`."""

    def __init__(self, kpm_func, buffer: SampleBuffer, logger) -> None:
        self.kpm_func = kpm_func
        self.buffer = buffer
        self.logger = logger
        self._sds_seen: set = set()
        # submgr_sub_id (str, returned by subscribe()) -> sd (int).
        self._submgr_to_sd: Dict[str, int] = {}
        # E2EventInstanceId (int, stamped on every IND) -> sd (int).
        self._evt_to_sd: Dict[int, int] = {}

    # ---- Sub-resolved bridge ------------------------------------------------

    def on_sub_resolved(self, submgr_sub_id, e2_event_instance_id, gnb_inv: str) -> None:
        """Framework hook: called once the RIC has set up the subscription.
        Bridges the submgr id we stored at subscribe() time to the
        E2EventInstanceId the gNB stamps on every subsequent IND."""
        sd = self._submgr_to_sd.get(submgr_sub_id)
        if sd is None:
            self.logger.warning(
                "[KpmIngest] sub_resolved for unknown submgr_id={} (gnb={}, e2evt={})".format(
                    submgr_sub_id, gnb_inv, e2_event_instance_id))
            return
        try:
            evt_id = int(e2_event_instance_id)
        except (TypeError, ValueError):
            self.logger.warning(
                "[KpmIngest] sub_resolved e2evt={} not an int; dropping bridge".format(
                    e2_event_instance_id))
            return
        self._evt_to_sd[evt_id] = sd
        self.logger.info(
            "[KpmIngest] sub_resolved: submgr={} -> e2evt={} -> sd={}".format(
                submgr_sub_id, evt_id, sd))

    # ---- Indication handling ------------------------------------------------

    def indication_callback(self, ind_hdr, ind_msg, meid, sub_id=None) -> None:
        """Single callback for ALL KPM subscriptions. Routes by sub_id."""
        gnbid = meid.decode("utf-8") if isinstance(meid, (bytes, bytearray)) else str(meid)

        sd = None
        if sub_id is not None:
            try:
                sd = self._evt_to_sd.get(int(sub_id))
            except (TypeError, ValueError):
                sd = None
        if sd is None:
            self.logger.warning(
                "[KpmIngest] IND with unresolved sub_id={} (gnb={}); dropping. "
                "Bridge size={}".format(sub_id, gnbid, len(self._evt_to_sd)))
            return

        if ind_msg.type.value == format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
            self._handle_format_3(ind_msg, gnbid, sd)
        elif ind_msg.type.value == format_ind_msg_e.FORMAT_1_INDICATION_MESSAGE:
            self.logger.debug(
                "[KpmIngest] cell-wide IND from {} sd={} (skipped in v1)".format(gnbid, sd))
        else:
            self.logger.info(
                "[KpmIngest] unsupported indication format {}".format(ind_msg.type.value))

    def _handle_format_3(self, ind_msg, gnbid: str, sd: int) -> None:
        frm = ind_msg.data.frm_3
        ts_ms = int(time.time() * 1000)
        for i in range(frm.ue_meas_report_lst_len):
            ue_report = frm.meas_report_per_ue[i]
            ue_id_value = self.kpm_func.get_ue_id(ue_report.ue_meas_report_lst)
            ue_id_label = "ue_" + str(ue_id_value)
            metrics = self._extract_metrics(ue_report.ind_msg_format_1)
            if not metrics:
                continue
            sample = Sample(
                timestamp_ms=ts_ms,
                ue_id=ue_id_label,
                ran_ue_id=int(ue_id_value),
                sd=sd,
                gnb_id=gnbid,
                metrics=metrics,
            )
            self.buffer.push(sample)
            if sd not in self._sds_seen:
                self._sds_seen.add(sd)
                self.logger.info(
                    "[KpmIngest] first IND for sd={} (ue={}, gnb={})".format(
                        sd, ue_id_label, gnbid))

    def _extract_metrics(self, ind_msg_format_1) -> dict:
        out: dict = {}
        # PROBE: collect any sliceID values found in label_info_lst. Static
        # analysis of ran_func_kpm.c says the gNB never populates these,
        # but we log empirically so it's obvious in the running pod
        # whether the assumption holds. Empirical confirmation on the
        # earlier run: PROBE silent → sliceID is NOT populated in this
        # fork. We keep the PROBE at INFO level for the time being so any
        # gNB build that *does* populate it gets surfaced fast.
        probed_slices: set = set()
        for j in range(ind_msg_format_1.meas_data_lst_len):
            meas_data_lst = ind_msg_format_1.meas_data_lst
            for k in range(meas_data_lst[j].meas_record_len):
                meas_info = ind_msg_format_1.meas_info_lst[k]
                name = _decode_meas_type(meas_info)
                if name is None:
                    continue
                try:
                    n_labels = int(meas_info.label_info_lst_len)
                except AttributeError:
                    n_labels = 0
                for li in range(n_labels):
                    label_el = meas_info.label_info_lst[li]
                    if not label_el.sliceID:
                        continue
                    nssai = label_el.sliceID.contents
                    sst_val = int(nssai.sST)
                    sd_val = (
                        int(nssai.sD.contents.value)
                        if nssai.sD else None
                    )
                    probed_slices.add((name, sst_val, sd_val))
                val = _record_value(meas_data_lst[j].meas_record_lst[k])
                if val is None:
                    continue
                out[name] = val
        if probed_slices:
            for meas_name, sst_val, sd_val in sorted(probed_slices):
                self.logger.info(
                    "[KpmIngest][PROBE] sliceID present on '{}': sst={} sd={}".format(
                        meas_name, sst_val, sd_val))
        else:
            self.logger.debug("[KpmIngest][PROBE] no sliceID in any label_info_lst")
        return out

    def sub_failed_callback(self, json_data) -> None:
        self.logger.error("[KpmIngest] subscription failed: {}".format(json_data))

    # ---- Subscription bring-up ---------------------------------------------

    def subscribe_all(self, gnb, gnb_info, ran_period_ms: int = 1000) -> bool:
        """Subscribe to Style 4 + Style 1 once per sd; track each
        submgr_sub_id -> sd. The framework's `sub_resolved_callback` (wired
        in `traffic_balancer.main`) bridges these to E2EventInstanceId so
        the IND callback can look up the slice via the `sub_id` arg.
        """
        ran_func_desc = self.kpm_func.get_ran_function_description(json_ran_info=gnb_info)
        func_def_dict = ran_func_desc.get_dict_of_values()

        fmt4 = func_def_dict.get(format_action_def_e.FORMAT_4_ACTION_DEFINITION, [])
        fmt1 = func_def_dict.get(format_action_def_e.FORMAT_1_ACTION_DEFINITION, [])
        if not fmt4 and not fmt1:
            self.logger.error("[KpmIngest] gNB advertises neither Style 4 nor Style 1 metrics")
            return False
        self.logger.debug("[KpmIngest] Style 4 metrics: {}".format(fmt4))
        self.logger.debug("[KpmIngest] Style 1 metrics: {}".format(fmt1))

        ev_trigger = (0, 1000)
        issued = 0
        for sd in SDS:
            if fmt4:
                self.logger.info(
                    "[KpmIngest] subscribing Style 4 (per-UE) sst={} sd={}".format(SST, sd))
                submgr_id = self.kpm_func.subscribe(
                    gnb=gnb,
                    ev_trigger=ev_trigger,
                    func_def={format_action_def_e.FORMAT_4_ACTION_DEFINITION: fmt4},
                    ran_period_ms=ran_period_ms,
                    sst=SST,
                    sd=sd,
                )
                self._register_submgr(submgr_id, sd, style="4")
                if submgr_id is not None:
                    issued += 1
            if fmt1:
                self.logger.info(
                    "[KpmIngest] subscribing Style 1 (cell-wide) sst={} sd={}".format(SST, sd))
                submgr_id = self.kpm_func.subscribe(
                    gnb=gnb,
                    ev_trigger=ev_trigger,
                    func_def={format_action_def_e.FORMAT_1_ACTION_DEFINITION: fmt1},
                    ran_period_ms=ran_period_ms,
                    sst=SST,
                    sd=sd,
                )
                self._register_submgr(submgr_id, sd, style="1")
                if submgr_id is not None:
                    issued += 1
        self.logger.info("[KpmIngest] issued {} subscriptions; submgr map: {}".format(
            issued, self._submgr_to_sd))
        return issued > 0

    def _register_submgr(self, submgr_id, sd: int, style: str) -> None:
        if submgr_id is None:
            self.logger.error("[KpmIngest] subscribe returned None for sd={} style={}".format(sd, style))
            return
        self._submgr_to_sd[submgr_id] = sd
        self.logger.info(
            "[KpmIngest] sd={} style={} -> submgr_sub_id={}".format(sd, style, submgr_id))
