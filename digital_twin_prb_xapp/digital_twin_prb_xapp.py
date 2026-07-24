import argparse
import collections
import json
import signal
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
from mdclogpy import Level

from xdevsm.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp
from xdevsm.decorators.kpm.kpm_frame import XappKpmFrame
from xdevsm.decorators.rc.rc_radio_resource_alloc_control import RadioResourceAllocationControl

from xdevsm.utils.utility import decode_meid

from xdevsm.sm_framework.py_oran.kpm.enums import format_action_def_e
from xdevsm.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xdevsm.sm_framework.py_oran.kpm.enums import meas_type_enum
from xdevsm.sm_framework.py_oran.kpm.enums import meas_value_e


string_to_level = {"DEBUG": Level.DEBUG,
                   "INFO": Level.INFO,
                   "WARNING": Level.WARNING,
                   "ERROR": Level.ERROR}


MAX_SLICES = 2
SLICE_CONTROL_ACTION_ID = 6  # Slice-level PRB quota


def _normalize_plmn(plmn):
    """
    Convert whatever the RIC's E2 manager hands us for `plmnId` into the
    3-byte BCD hex string that `PLMN.from_hex()` expects.

    The encoder calls `bytes.fromhex(plmn)` and feeds the result as the octet
    string PLMN Identity inside the RC slice-level PRB quota control. OAI's
    decoder (ran_func_rc.c:~1294) then walks the resulting RRM Policy Member
    and asserts a fixed shape - any mis-encoded PLMN can leave the inner
    struct count off and trigger the
        "RRM Policy Member size not valid"
    assertion.

    Accepts three shapes:
      - 6-char hex string ("00F110") -> used as-is (lowercased to canonicalize)
      - digit string "00101" / "001001" (MCC+MNC, 5 or 6 digits) -> BCD
      - dict {"mcc": "001", "mnc": "01"} -> BCD
    """
    def _bcd(mcc, mnc):
        if len(mcc) != 3 or len(mnc) not in (2, 3):
            raise ValueError("Invalid MCC/MNC lengths mcc={}, mnc={}".format(mcc, mnc))
        # TS 24.501 / TS 23.003 BCD encoding, 3 bytes -> 6 hex chars.
        # Per byte, high nibble is written first in hex.
        #   byte 1: MCC[2] | MCC[1]
        #   byte 2: (MNC[3] or F filler if MNC is 2-digit) | MCC[3]
        #   byte 3: MNC[2] | MNC[1]
        if len(mnc) == 2:
            return "{}{}F{}{}{}".format(mcc[1], mcc[0], mcc[2], mnc[1], mnc[0]).upper()
        return "{}{}{}{}{}{}".format(mcc[1], mcc[0], mnc[2], mcc[2], mnc[1], mnc[0]).upper()

    if isinstance(plmn, dict):
        return _bcd(str(plmn["mcc"]), str(plmn["mnc"]))
    if isinstance(plmn, int):
        plmn = str(plmn)
    if isinstance(plmn, str):
        s = plmn.strip()
        # Already hex? (only [0-9a-f], even length, 3 bytes)
        if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
            return s.upper()
        # MCC+MNC digits, 2-digit MNC -> 5 chars; 3-digit MNC -> 6 chars.
        if s.isdigit() and len(s) in (5, 6):
            mcc = s[:3]
            mnc = s[3:]
            return _bcd(mcc, mnc)
    raise ValueError("Unsupported PLMN format: {!r}".format(plmn))


# A pending control attempt waiting to be sent (or already in flight) on a gNB.
# We do not carry a ue_id here: the RC encoder uses the mock UE id configured
# on rc_func (matches prb_control_xapp). target_min_prb / target_max_prb are
# tracked per-control so we can independently follow how each PRB ratio
# evolves on the DT and on the real gNB.
PendingControl = collections.namedtuple(
    "PendingControl", ["control_action_id", "target_max_prb", "target_min_prb"])


def load_config(path):
    """
    Load and validate the PRB control configuration. Returns a dict:
      {
        "sst": int,
        "slices": { sd: {min_prb, max_prb, ded_prb, prb_step, max_down, max_up} }
      }
    """
    with open(path, "r") as f:
        raw = json.load(f)

    sst = raw["sst"]
    slices_in = raw["slices"]
    if not isinstance(slices_in, list) or not (1 <= len(slices_in) <= MAX_SLICES):
        raise ValueError("config: 'slices' must contain between 1 and {} entries".format(MAX_SLICES))

    slices = {}
    for entry in slices_in:
        sd = entry["sd"]
        if sd in slices:
            raise ValueError("config: duplicate sd {}".format(sd))
        slices[sd] = {
            "min_prb": entry["min_prb_policy_ratio"],
            "max_prb": entry["max_prb_policy_ratio"],
            "ded_prb": entry["dedicated_prb_policy_ratio"],
            "prb_step": entry.get("prb_step", 5),
            "max_down": entry["max_down_throughput_mbps"],
            "max_up": entry.get("max_up_throughput_mbps"),
            # Adaptive PRB exploration knobs (see README). Same units as
            # max_down_throughput_mbps for `under_threshold_gap` /
            # `improvement_epsilon`. `convergence_indications` is the number of
            # consecutive stable KPM ticks required before propagating any DT
            # setting to the real gNB.
            "under_threshold_gap": entry.get("under_threshold_gap", 10),
            "prb_step_up": entry.get("prb_step_up", 2),
            "improvement_epsilon": entry.get("improvement_epsilon", 1),
            "convergence_indications": entry.get("convergence_indications", 5),
        }
    # Optional static PLMN overrides. When provided they bypass whatever the
    # E2 manager reports for `globalNbId.plmnId` - matches what prb_control_xapp
    # does with its `--plmn` flag.
    return {
        "sst": sst,
        "slices": slices,
        "plmn_real": raw.get("plmn_real"),
        "plmn_dt": raw.get("plmn_dt"),
    }


class xAppMonControlContainer():
    """
    Manages KPM monitoring and RC PRB control across a real gNB and its
    digital twin, with one subscription per (gNB, slice).

    Control flow: throughput on a slice of the DT exceeds the configured
    threshold -> a PRB-reduction control is sent to the DT; only after that
    control is acknowledged successfully, the same policy is replayed on the
    real gNB. Controls are serialized per gNB (at most one in flight); when a
    slot is busy, further attempts are queued per (gNB, slice).
    """

    def __init__(self, xapp_gen: xDevSMRMRXapp, gnb_target, gnb_dt_target,
                 csv_file, event_trigger, config, ack_timeout=5.0):
        self.xapp_gen = xapp_gen
        self.logger = xapp_gen.logger
        self.gnb_target = gnb_target
        self.gnb_dt_target = gnb_dt_target
        self.csv_file = csv_file
        self.event_trigger = event_trigger * 1000
        self.config = config
        self.sst = config["sst"]
        self.slices_cfg = config["slices"]  # sd -> per-slice config dict
        # Seconds to wait for an ACK before resending a control. Mirrors the
        # working prb_control_xapp's --ack_timeout behaviour.
        self.ack_timeout = ack_timeout

        # Resolved gNB info populated in start().
        self.selected_gnb = None         # real
        self.selected_gnb_dt = None      # digital twin
        self.rc_func_desc = None         # RC descriptor for real
        self.rc_func_desc_dt = None      # RC descriptor for DT
        self.plmn_id_real = None
        self.plmn_id_dt = None

        # Per-(gnb_inv_name, sd) runtime state: current PRB ratio + outgoing
        # queue. Populated once gNBs are resolved.
        self.slice_runtime = {}

        # gnb_inv_name -> currently in-flight PendingControl (or None). Used to
        # serialize controls per gNB and to correlate ACKs (option A: by meid).
        self.in_flight_per_gnb = {}
        # gnb_inv_name -> threading.Timer instance armed when a control is
        # dispatched. Fired after `ack_timeout` seconds; cancelled when the
        # matching ACK / FAILURE arrives. Resends the in-flight control.
        self.pending_timers = {}
        # Serializes mutations of in_flight_per_gnb + pending_timers between
        # the RMR receive thread (indications / ACKs) and the timer threads.
        self._ctrl_lock = threading.Lock()

        # RMR sub_id (int, E2EventInstanceId) -> (gnb_inv_name, sd). Populated
        # only when the submgr's async subscription response arrives carrying
        # the resolved E2EventInstanceId.
        self.sub_to_slice = {}
        # submgr SubscriptionId (string) -> (gnb_inv_name, sd). Populated
        # immediately at subscribe time; consumed by the async resolve
        # callback to translate to RMR sub_id.
        self.submgr_to_slice = {}
        # Both maps are updated from the async HTTP server thread and read
        # from the RMR receive thread, so guard them.
        self._sub_lock = threading.Lock()

        # Build RC and KPM decorators. Per-slice parameters are pushed onto
        # rc_func right before each send(), so the constructor values here
        # are placeholders. We deliberately use the mock UE id (ue_id_type=False
        # + ue_id=1) the way prb_control_xapp does - feeding a ue_id_struct
        # extracted from a KPM indication into the RC encoder produced PDUs
        # that crashed the gNB.
        self.rc_func = RadioResourceAllocationControl(
            xapp_gen,
            logger=xapp_gen.logger,
            server=xapp_gen.server,
            xapp_name=xapp_gen.get_xapp_name(),
            rmr_port=xapp_gen.rmr_port,
            http_port=xapp_gen.http_port,
            mrc=xapp_gen._mrc,
            pltnamespace=xapp_gen.get_pltnamespace(),
            app_namespace=xapp_gen.get_app_namespace(),
            sst=self.sst,
            sd=next(iter(self.slices_cfg)),
            ue_id_type=False,
            ue_id=1,
        )
        self.kpm_func = XappKpmFrame(
            self.rc_func,
            xapp_gen.logger,
            xapp_gen.server,
            xapp_gen.get_xapp_name(),
            xapp_gen.rmr_port,
            xapp_gen.http_port,
            xapp_gen.get_pltnamespace(),
            xapp_gen.get_app_namespace())

        self.xapp_gen.register_handler(self.kpm_func.handle)

        self.kpm_func.register_ind_msg_callback(self.ind_msg_handler)
        self.kpm_func.register_sub_fail_callback(self.sub_failed_callback)
        self.kpm_func.register_sub_resolved_callback(self.sub_resolved_callback)

        self.rc_func.register_control_ack_suc_callback(self.control_ack_success_callback)
        self.rc_func.register_control_ack_fail_callback(self.control_ack_failure_callback)

        signal.signal(signal.SIGINT, self.termination)
        signal.signal(signal.SIGTERM, self.termination)

        # KPM data accumulator (one row per UE-measurement). The leading
        # timestamp_ms lets us align KPM rows with control events on the same
        # timeline at CSV-export time.
        self.df_dict = {
            "timestamp_ms": [],
            "ue_id": [],
            "gnb_id": [],
            "sst": [],
            "sd": [],
            "MAX_PRB": [],
            "MIN_PRB": [],
        }

        # Control events accumulator. One row is appended every time a control
        # PDU is dispatched (event='sent') and another whenever its ACK or
        # FAILURE arrives ('ack_suc' / 'ack_fail'). Same gnb/slice schema as
        # the KPM CSV so the two can be joined on (timestamp_ms, gnb_id, sd).
        self.control_df_dict = {
            "timestamp_ms": [],
            "gnb_id": [],
            "is_dt": [],
            "sst": [],
            "sd": [],
            "target_max_prb": [],
            "target_min_prb": [],
            "ded_prb": [],
            "event": [],
        }

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def termination(self, signum, frame):
        self.logger.info("[xAppMonControlContainer] terminating")
        # Stop any outstanding ACK-timeout timers so daemon threads don't
        # outlive the xApp.
        with self._ctrl_lock:
            timers = list(self.pending_timers.values())
            self.pending_timers.clear()
        for t in timers:
            t.cancel()
        if self.csv_file is not None:
            df = pd.DataFrame.from_dict(self.df_dict, orient='index').transpose()
            df.to_csv(self.csv_file, index=False)
            self.logger.info("[xAppMonControlContainer] KPM data saved to {}".format(self.csv_file))
            p = Path(self.csv_file)
            controls_path = str(p.with_name(p.stem + "_controls" + p.suffix))
            df_ctrl = pd.DataFrame.from_dict(self.control_df_dict, orient='index').transpose()
            df_ctrl.to_csv(controls_path, index=False)
            self.logger.info("[xAppMonControlContainer] Control events saved to {}".format(controls_path))
        self.kpm_func.terminate(signum, frame)

    def sub_failed_callback(self, json_data):
        self.logger.info("[xAppMonControlContainer] subscription failed: {}".format(json_data))

    def _append_control_event(self, gnb_inv, sd, entry, event):
        """Record a control sent / acked / failed for later offline analysis."""
        slice_cfg = self.slices_cfg[sd]
        is_dt = (self.selected_gnb_dt is not None
                 and gnb_inv == self.selected_gnb_dt.inventory_name)
        self.control_df_dict["timestamp_ms"].append(int(time.time() * 1000))
        self.control_df_dict["gnb_id"].append(gnb_inv)
        self.control_df_dict["is_dt"].append(is_dt)
        self.control_df_dict["sst"].append(self.sst)
        self.control_df_dict["sd"].append(sd)
        self.control_df_dict["target_max_prb"].append(entry.target_max_prb)
        self.control_df_dict["target_min_prb"].append(entry.target_min_prb)
        self.control_df_dict["ded_prb"].append(slice_cfg["ded_prb"])
        self.control_df_dict["event"].append(event)

    # ------------------------------------------------------------------ #
    # KPM indications
    # ------------------------------------------------------------------ #

    def ind_msg_handler(self, ind_hdr, ind_msg, meid, sub_id):
        """
        Process a KPM indication. The (gnb, slice) it refers to is identified
        via the RMR `sub_id` of the subscription that produced it.
        """
        gnbid = meid.decode('utf-8')
        with self._sub_lock:
            route = self.sub_to_slice.get(sub_id)
        if route is None:
            self.logger.warning(
                "[xAppMonControlContainer] indication from {} on unknown sub_id {} - ignoring".format(gnbid, sub_id))
            return
        route_gnb, sd = route
        if route_gnb != gnbid:
            self.logger.warning(
                "[xAppMonControlContainer] sub_id {} routed for {} but indication meid is {}".format(sub_id, route_gnb, gnbid))
        is_dt = (gnbid == self.selected_gnb_dt.inventory_name)
        slice_cfg = self.slices_cfg[sd]
        runtime = self.slice_runtime[(gnbid, sd)]

        sender_name = None
        if ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name:
            buf = ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents
            sender_name = bytes(np.ctypeslib.as_array(buf.buf, shape=(buf.len,))).decode('utf-8')

        if ind_msg.type.value != format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
            self.logger.debug("[xAppMonControlContainer] unsupported indication format {}".format(ind_msg.type.value))
            return

        downlink_bw = 0.0
        uplink_bw = 0.0
        saw_any_ue = False
        for i in range(ind_msg.data.frm_3.ue_meas_report_lst_len):
            meas_report_ue = ind_msg.data.frm_3.meas_report_per_ue[i]
            ue_id_value = self.kpm_func.get_ue_id(meas_report_ue.ue_meas_report_lst)
            saw_any_ue = True
            self.logger.info(
                "[xAppMonControlContainer] gnb: {}, sender: {}, slice: (sst={}, sd={}), ue: {}".format(
                    gnbid, sender_name, self.sst, sd, ue_id_value))
            ind_msg_format_1 = meas_report_ue.ind_msg_format_1
            self.df_dict["timestamp_ms"].append(int(time.time() * 1000))
            self.df_dict["ue_id"].append(ue_id_value)
            self.df_dict["gnb_id"].append(gnbid)
            self.df_dict["sst"].append(self.sst)
            self.df_dict["sd"].append(sd)
            self.df_dict["MAX_PRB"].append(runtime["current_max_prb"])
            self.df_dict["MIN_PRB"].append(slice_cfg["min_prb"])

            for j in range(ind_msg_format_1.meas_data_lst_len):
                meas_data_lst = ind_msg_format_1.meas_data_lst
                for k in range(meas_data_lst[j].meas_record_len):
                    meas_record_lst_el = meas_data_lst[j].meas_record_lst[k]
                    if ind_msg_format_1.meas_info_lst[k].meas_type.type.value != meas_type_enum.NAME_MEAS_TYPE:
                        self.logger.info("[xAppMonControlContainer] Not supported meas type {}".format(
                            ind_msg_format_1.meas_info_lst[k].meas_type.type.value))
                        continue
                    meas_type_name = ind_msg_format_1.meas_info_lst[k].meas_type.value.name
                    self.store_to_csv(meas_type=meas_type_name, meas_record=meas_record_lst_el)
                    d, u = self.compute_bandwidth(meas_type=meas_type_name, meas_record=meas_record_lst_el)
                    downlink_bw += d
                    uplink_bw += u

        self.logger.info(
            "[xAppMonControlContainer] gnb={} sd={} dl={} ul={} current_max_prb={}".format(
                gnbid, sd, downlink_bw, uplink_bw, runtime["current_max_prb"]))

        # Indications from the real gNB are purely observational.
        if not is_dt:
            return

        if not saw_any_ue:
            return

        over_down = downlink_bw > slice_cfg["max_down"]
        over_up = (slice_cfg["max_up"] is not None and uplink_bw > slice_cfg["max_up"])
        over_threshold = over_down or over_up

        # DT-only state machine: decreasing -> (stability window) -> exploring_up -> settled.
        self._dt_state_machine(gnbid, sd, downlink_bw, over_threshold, runtime, slice_cfg)

    # ------------------------------------------------------------------ #
    # DT state machine
    # ------------------------------------------------------------------ #

    def _dt_queue_step(self, gnbid, sd, runtime, new_max):
        """Enqueue a DT control that sets max_prb to `new_max`."""
        runtime["queue"].append(PendingControl(
            control_action_id=SLICE_CONTROL_ACTION_ID,
            target_max_prb=new_max,
            target_min_prb=runtime["current_min_prb"]))
        self._try_send_to_gnb(gnbid, prefer_sd=sd)

    def _propagate_to_real(self, sd, target_max_prb, target_min_prb):
        """Enqueue a real-gNB control with the validated (max, min) pair if it
        differs from what's currently committed there."""
        real_inv = self.selected_gnb.inventory_name
        real_runtime = self.slice_runtime[(real_inv, sd)]
        if (real_runtime["current_max_prb"] == target_max_prb
                and real_runtime["current_min_prb"] == target_min_prb):
            return
        self.logger.info(
            "[xAppMonControlContainer] propagating to real gNB sd={}: max={}, min={} (was max={}, min={})".format(
                sd, target_max_prb, target_min_prb,
                real_runtime["current_max_prb"], real_runtime["current_min_prb"]))
        real_runtime["queue"].append(PendingControl(
            control_action_id=SLICE_CONTROL_ACTION_ID,
            target_max_prb=target_max_prb,
            target_min_prb=target_min_prb))
        self._try_send_to_gnb(real_inv, prefer_sd=sd)

    def _dt_state_machine(self, gnbid, sd, dl, over_threshold, runtime, slice_cfg):
        """Implements the per-(DT, sd) phase transitions described in the plan."""
        phase = runtime["phase"]
        n = slice_cfg["convergence_indications"]
        prb_step = slice_cfg["prb_step"]
        prb_step_up = slice_cfg["prb_step_up"]
        gap_thresh = slice_cfg["under_threshold_gap"]
        eps = slice_cfg["improvement_epsilon"]
        min_floor = slice_cfg["min_prb"] + prb_step
        cur_max = runtime["current_max_prb"]
        cur_min = runtime["current_min_prb"]

        # -------- decreasing --------
        if phase == "decreasing":
            if over_threshold:
                runtime["stable_count"] = 0
                new_max = cur_max - prb_step
                if new_max < min_floor:
                    self.logger.error(
                        "[xAppMonControlContainer] gnb={} sd={} decreasing: cannot step below min ({}); staying at {}".format(
                            gnbid, sd, slice_cfg["min_prb"], cur_max))
                    return
                self.logger.info(
                    "[xAppMonControlContainer] decreasing sd={}: dl={} > th={}; stepping DT max_prb {}->{}".format(
                        sd, dl, slice_cfg["max_down"], cur_max, new_max))
                self._dt_queue_step(gnbid, sd, runtime, new_max)
                return
            # dl <= threshold
            runtime["stable_count"] += 1
            self.logger.info(
                "[xAppMonControlContainer] decreasing sd={}: dl={} <= th={} ({}/{} stable)".format(
                    sd, dl, slice_cfg["max_down"], runtime["stable_count"], n))
            if runtime["stable_count"] < n:
                return
            # Stability window reached.
            gap = slice_cfg["max_down"] - dl
            if gap > gap_thresh and cur_max < 100:
                self.logger.info(
                    "[xAppMonControlContainer] convergence confirmed after {} indications sd={} max={}; "
                    "entering exploring_up (gap={} > {} and max<100); stepping up by {}".format(
                        n, sd, cur_max, gap, gap_thresh, prb_step_up))
                runtime["phase"] = "exploring_up"
                runtime["safe_max_prb"] = cur_max
                runtime["last_dl"] = dl
                runtime["stable_count"] = 0
                new_max = min(cur_max + prb_step_up, 100)
                self._dt_queue_step(gnbid, sd, runtime, new_max)
                return
            # No exploration warranted; settle and propagate.
            self.logger.info(
                "[xAppMonControlContainer] convergence confirmed after {} indications sd={} max={} (gap={} <= {} or max=100); settling".format(
                    n, sd, cur_max, gap, gap_thresh))
            runtime["phase"] = "settled"
            runtime["stable_count"] = 0
            self._propagate_to_real(sd, cur_max, cur_min)
            return

        # -------- exploring_up --------
        if phase == "exploring_up":
            safe = runtime["safe_max_prb"]
            if over_threshold:
                self.logger.warning(
                    "[xAppMonControlContainer] exploring_up sd={}: overshoot dl={} > th={}; reverting DT max_prb {}->{} and propagating".format(
                        sd, dl, slice_cfg["max_down"], cur_max, safe))
                runtime["phase"] = "settled"
                runtime["stable_count"] = 0
                if cur_max != safe:
                    self._dt_queue_step(gnbid, sd, runtime, safe)
                self._propagate_to_real(sd, safe, cur_min)
                return
            last_dl = runtime["last_dl"] if runtime["last_dl"] is not None else dl
            delta = dl - last_dl
            if delta >= eps:
                runtime["stable_count"] = 0
                runtime["last_dl"] = dl
                if cur_max >= 100:
                    self.logger.info(
                        "[xAppMonControlContainer] exploring_up sd={}: max already at 100; settling".format(sd))
                    runtime["phase"] = "settled"
                    self._propagate_to_real(sd, cur_max, cur_min)
                    return
                new_max = min(cur_max + prb_step_up, 100)
                self.logger.info(
                    "[xAppMonControlContainer] exploring_up sd={}: dl improved by {} (>= eps={}); stepping max {}->{}".format(
                        sd, delta, eps, cur_max, new_max))
                self._dt_queue_step(gnbid, sd, runtime, new_max)
                return
            # No improvement.
            runtime["stable_count"] += 1
            self.logger.info(
                "[xAppMonControlContainer] exploring_up sd={}: no improvement (delta={} < eps={}) ({}/{} stable)".format(
                    sd, delta, eps, runtime["stable_count"], n))
            if runtime["stable_count"] < n:
                return
            self.logger.info(
                "[xAppMonControlContainer] exploring_up sd={}: confirmed no improvement after {} ticks; "
                "reverting DT max_prb {}->{} and propagating to real gNB".format(
                    sd, n, cur_max, safe))
            runtime["phase"] = "settled"
            runtime["stable_count"] = 0
            if cur_max != safe:
                self._dt_queue_step(gnbid, sd, runtime, safe)
            self._propagate_to_real(sd, safe, cur_min)
            return

        # -------- settled --------
        if phase == "settled":
            if over_threshold:
                self.logger.info(
                    "[xAppMonControlContainer] settled sd={}: dl={} > th={}; re-entering decreasing".format(
                        sd, dl, slice_cfg["max_down"]))
                runtime["phase"] = "decreasing"
                runtime["stable_count"] = 0
                # Fall through to handle this tick in the decreasing phase.
                self._dt_state_machine(gnbid, sd, dl, over_threshold, runtime, slice_cfg)
            return

    # ------------------------------------------------------------------ #
    # Control sending / ACK handling
    # ------------------------------------------------------------------ #

    def _try_send_to_gnb(self, gnb_inv, prefer_sd=None):
        """
        If `gnb_inv` has no control in flight, drain one entry from one of its
        per-slice queues. `prefer_sd` is tried first; otherwise iterate the
        configured slices in deterministic order. Slot reservation happens
        under `_ctrl_lock` so concurrent ACKs / timer-fires cannot race.
        """
        candidate_sds = list(self.slices_cfg.keys())
        if prefer_sd is not None and prefer_sd in candidate_sds:
            candidate_sds = [prefer_sd] + [sd for sd in candidate_sds if sd != prefer_sd]

        with self._ctrl_lock:
            if self.in_flight_per_gnb.get(gnb_inv) is not None:
                return
            picked = None
            for sd in candidate_sds:
                runtime = self.slice_runtime.get((gnb_inv, sd))
                if runtime is None or not runtime["queue"]:
                    continue
                entry = runtime["queue"].popleft()
                self.in_flight_per_gnb[gnb_inv] = (sd, entry)
                picked = (sd, entry)
                break

        if picked is None:
            return
        sd, entry = picked
        self._encode_and_send(gnb_inv, sd, entry)

    def _encode_and_send(self, gnb_inv, sd, entry):
        """Configure rc_func for (gnb_inv, sd) and dispatch the control."""
        is_dt = (gnb_inv == self.selected_gnb_dt.inventory_name)
        plmn_id = self.plmn_id_dt if is_dt else self.plmn_id_real
        rc_func_desc = self.rc_func_desc_dt if is_dt else self.rc_func_desc
        slice_cfg = self.slices_cfg[sd]

        self.rc_func.set_plmn_identity(plmn_id)
        self.rc_func.set_sst(self.sst)
        self.rc_func.set_sd(sd)
        self.rc_func.set_max_prb_policy_ratio(entry.target_max_prb)
        self.rc_func.set_min_prb_policy_ratio(entry.target_min_prb)
        # dedicated_prb_policy_ratio is not tuned by the control loop today; we
        # keep it pinned to the configured value.
        self.rc_func.set_dedicated_prb_policy_ratio(slice_cfg["ded_prb"])

        self.logger.info(
            "[xAppMonControlContainer] sending control to {} sst={} sd={} target_max_prb={} target_min_prb={}".format(
                gnb_inv, self.sst, sd, entry.target_max_prb, entry.target_min_prb))
        # ue_id_struct=None forces the encoder to use the mock UE id configured
        # at constructor time. This matches prb_control_xapp; passing the UE
        # struct from a KPM indication produced PDUs that crashed the gNB.
        self.rc_func.send(
            e2_node_id=gnb_inv,
            ran_func_dsc=rc_func_desc,
            ue_id_struct=None,
            control_action_id=entry.control_action_id)
        self._append_control_event(gnb_inv, sd, entry, "sent")
        self._arm_ack_timer(gnb_inv, sd, entry)

    def _arm_ack_timer(self, gnb_inv, sd, entry):
        """Start (or restart) the per-gNB ACK-timeout timer for `entry`."""
        timer = threading.Timer(self.ack_timeout, self._ack_timeout_fired,
                                args=(gnb_inv, sd, entry))
        timer.daemon = True
        with self._ctrl_lock:
            old = self.pending_timers.pop(gnb_inv, None)
            self.pending_timers[gnb_inv] = timer
        if old is not None:
            old.cancel()
        timer.start()

    def _ack_timeout_fired(self, gnb_inv, sd, entry):
        """
        Resend the in-flight control if it is still the one we armed this
        timer for. If an ACK / FAILURE has already cleared (or replaced) the
        slot, do nothing.
        """
        with self._ctrl_lock:
            in_flight = self.in_flight_per_gnb.get(gnb_inv)
            if in_flight is None or in_flight[1] is not entry:
                return
            # The slot is still ours; drop the timer handle so _arm_ack_timer
            # doesn't try to cancel the very timer we are running on.
            self.pending_timers.pop(gnb_inv, None)
        self.logger.warning(
            "[xAppMonControlContainer] gnb={} sd={} ack timeout ({}s) - resending control "
            "(target max={} min={})".format(
                gnb_inv, sd, self.ack_timeout, entry.target_max_prb, entry.target_min_prb))
        self._encode_and_send(gnb_inv, sd, entry)

    def control_ack_success_callback(self, summary):
        """
        ACK from gNB X. With option-A serialization, that ACK belongs to
        whatever is in `in_flight_per_gnb[X]`. We commit the validated PRB
        ratios to that gNB's slice runtime; real-gNB propagation happens
        from `ind_msg_handler` once DT throughput drops under the threshold.
        """
        meid = decode_meid(summary)
        if meid is None:
            return
        with self._ctrl_lock:
            in_flight = self.in_flight_per_gnb.pop(meid, None)
            timer = self.pending_timers.pop(meid, None)
        if timer is not None:
            timer.cancel()
        if in_flight is None:
            self.logger.warning(
                "[xAppMonControlContainer] ACK from {} with no in-flight control".format(meid))
            return
        sd, entry = in_flight
        self._append_control_event(meid, sd, entry, "ack_suc")

        runtime = self.slice_runtime[(meid, sd)]
        runtime["current_max_prb"] = entry.target_max_prb
        runtime["current_min_prb"] = entry.target_min_prb
        kind = "DT" if meid == self.selected_gnb_dt.inventory_name else "real-gNB"
        self.logger.info(
            "[xAppMonControlContainer] {} ack for sd={}: committed max={} min={}".format(
                kind, sd, entry.target_max_prb, entry.target_min_prb))

        self._try_send_to_gnb(meid)

    def control_ack_failure_callback(self, summary):
        meid = decode_meid(summary)
        if meid is None:
            return
        with self._ctrl_lock:
            in_flight = self.in_flight_per_gnb.pop(meid, None)
            timer = self.pending_timers.pop(meid, None)
        if timer is not None:
            timer.cancel()
        if in_flight is None:
            self.logger.warning(
                "[xAppMonControlContainer] failure ACK from {} with no in-flight control".format(meid))
            return
        sd, entry = in_flight
        self._append_control_event(meid, sd, entry, "ack_fail")
        self.logger.warning(
            "[xAppMonControlContainer] control failed on {} sd={} - not propagating; draining queue".format(meid, sd))
        # Do NOT replay to the real gNB; just drain whatever is next on this gNB.
        self._try_send_to_gnb(meid)

    # ------------------------------------------------------------------ #
    # KPM utility helpers
    # ------------------------------------------------------------------ #

    def compute_bandwidth(self, meas_type, meas_record):
        downlink_bandwidth = 0.0
        up_link_bandwidth = 0.0
        meas_type_str = bytes(np.ctypeslib.as_array(meas_type.buf, shape=(meas_type.len,))).decode('utf-8')
        if meas_type_str == "DRB.UEThpDl":
            if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
                downlink_bandwidth = meas_record.union.int_val / 1024
            elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
                downlink_bandwidth = meas_record.union.real_val / 1024
        elif meas_type_str == "DRB.UEThpUl":
            if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
                up_link_bandwidth = meas_record.union.int_val / 1024
            elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
                up_link_bandwidth = meas_record.union.real_val / 1024
        return downlink_bandwidth, up_link_bandwidth

    def store_to_csv(self, meas_type, meas_record):
        meas_type_str = bytes(np.ctypeslib.as_array(meas_type.buf, shape=(meas_type.len,))).decode('utf-8')
        if meas_type_str not in self.df_dict:
            self.df_dict[meas_type_str] = []
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            self.df_dict[meas_type_str].append(meas_record.union.int_val)
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            self.df_dict[meas_type_str].append(meas_record.union.real_val)

    # ------------------------------------------------------------------ #
    # Setup / subscription
    # ------------------------------------------------------------------ #

    def _build_subscription_func_def(self, gnb_info, label):
        """
        Resolve KPM action-definition dict and RC descriptor for `gnb_info`.
        Returns (func_def_sub_dict, rc_func_desc) or (None, None) if the gNB
        does not support a usable format.
        """
        ran_function_description = self.kpm_func.get_ran_function_description(json_ran_info=gnb_info)
        func_def_dict = ran_function_description.get_dict_of_values()

        rc_func_desc = self.rc_func.get_ran_function_description(json_ran_info=gnb_info)
        rc_func_desc.print_rc_functions()

        if len(func_def_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION]) == 0:
            selected_format = format_action_def_e.FORMAT_1_ACTION_DEFINITION
        else:
            selected_format = format_action_def_e.FORMAT_4_ACTION_DEFINITION

        if selected_format == format_action_def_e.END_ACTION_DEFINITION:
            self.logger.error("[xAppMonControlContainer] {}: no supported action definition format".format(label))
            return None, None
        if "DRB.UEThpDl" not in func_def_dict[selected_format] or "DRB.UEThpUl" not in func_def_dict[selected_format]:
            self.logger.error(
                "[xAppMonControlContainer] {}: action definition format lacks DRB.UEThpDl / DRB.UEThpUl".format(label))
            return None, None
        return {selected_format: func_def_dict[selected_format]}, rc_func_desc

    def _init_slice_runtime(self, gnb_inv):
        is_dt = (self.selected_gnb_dt is not None
                 and gnb_inv == self.selected_gnb_dt.inventory_name)
        for sd, cfg in self.slices_cfg.items():
            entry = {
                # Mirror the current min/max PRB ratios on this (gNB, slice).
                # Both start at the configured initial values and follow the
                # validated controls dispatched to this gNB.
                "current_max_prb": cfg["max_prb"],
                "current_min_prb": cfg["min_prb"],
                "queue": collections.deque(),
            }
            if is_dt:
                # DT-only state machine for the decrease -> explore-up flow.
                # `safe_max_prb` is the last max_prb that produced dl <=
                # threshold; `last_dl` is the most recent throughput sample
                # we compare against for improvement; `stable_count` counts
                # the consecutive stable KPM ticks before we propagate.
                entry["phase"] = "decreasing"
                entry["safe_max_prb"] = None
                entry["last_dl"] = None
                entry["stable_count"] = 0
            self.slice_runtime[(gnb_inv, sd)] = entry
        self.in_flight_per_gnb[gnb_inv] = None

    def _subscribe_per_slice(self, gnb, func_def_sub_dict, label):
        ev_trigger_tuple = (0, self.event_trigger)
        for sd in self.slices_cfg.keys():
            submgr_sub_id = self.kpm_func.subscribe(
                gnb=gnb,
                ev_trigger=ev_trigger_tuple,
                func_def=func_def_sub_dict,
                ran_period_ms=1000,
                sst=self.sst,
                sd=sd)
            if submgr_sub_id is None:
                self.logger.error(
                    "[xAppMonControlContainer] {}: subscribe returned no submgr sub_id for sd={}".format(label, sd))
                continue
            with self._sub_lock:
                self.submgr_to_slice[submgr_sub_id] = (gnb.inventory_name, sd)
            self.logger.info(
                "[xAppMonControlContainer] {}: subscribed sd={} -> submgr_sub_id={} (awaiting async resolve)".format(
                    label, sd, submgr_sub_id))

    def sub_resolved_callback(self, submgr_sub_id, e2_event_instance_id, gnb_inv):
        """
        Called by the framework when an async subscription response resolves a
        submgr SubscriptionId to its RMR-side E2EventInstanceId. Finalize the
        sub_id -> (gnb, sd) mapping that the indication handler routes on.
        """
        with self._sub_lock:
            route = self.submgr_to_slice.pop(submgr_sub_id, None)
            if route is None:
                self.logger.warning(
                    "[xAppMonControlContainer] resolve for unknown submgr_sub_id {} - ignoring".format(submgr_sub_id))
                return
            self.sub_to_slice[e2_event_instance_id] = route
        self.logger.info(
            "[xAppMonControlContainer] resolved submgr={} -> rmr_sub_id={} for gnb={} sd={}".format(
                submgr_sub_id, e2_event_instance_id, route[0], route[1]))

    def start(self):
        time.sleep(5)  # wait for RMR rule registration (no callback in the OSC framework)

        self.selected_gnb, gnb_info = self.xapp_gen.get_selected_e2node_info(self.gnb_target)
        if not self.selected_gnb:
            self.logger.error("[Main] real gNB '{}' not available - terminating xapp".format(self.gnb_target))
            self.kpm_func.terminate(signal.SIGTERM, None)
            return

        self.selected_gnb_dt, gnb_info_dt = self.xapp_gen.get_selected_e2node_info(self.gnb_dt_target)
        if not self.selected_gnb_dt:
            self.logger.error("[Main] DT gNB '{}' not available - terminating xapp".format(self.gnb_dt_target))
            self.kpm_func.terminate(signal.SIGTERM, None)
            return

        # Static PLMN overrides from the JSON config take priority over what
        # the E2 manager reports; this matches prb_control_xapp's --plmn flag.
        plmn_real_raw = self.config.get("plmn_real") or gnb_info["globalNbId"]["plmnId"]
        plmn_dt_raw = self.config.get("plmn_dt") or gnb_info_dt["globalNbId"]["plmnId"]
        plmn_real_source = "config" if self.config.get("plmn_real") else "e2-manager"
        plmn_dt_source = "config" if self.config.get("plmn_dt") else "e2-manager"
        try:
            self.plmn_id_real = _normalize_plmn(plmn_real_raw)
            self.plmn_id_dt = _normalize_plmn(plmn_dt_raw)
        except ValueError as e:
            self.logger.error("[xAppMonControlContainer] PLMN normalization failed: {}".format(e))
            self.kpm_func.terminate(signal.SIGTERM, None)
            return
        self.logger.info(
            "[xAppMonControlContainer] plmn real: raw={!r} ({}) -> hex={}, "
            "plmn dt: raw={!r} ({}) -> hex={}".format(
                plmn_real_raw, plmn_real_source, self.plmn_id_real,
                plmn_dt_raw, plmn_dt_source, self.plmn_id_dt))

        func_def_sub_dict, self.rc_func_desc = self._build_subscription_func_def(gnb_info, "real-gnb")
        if func_def_sub_dict is None:
            self.kpm_func.terminate(signal.SIGTERM, None)
            return
        func_def_sub_dict_dt, self.rc_func_desc_dt = self._build_subscription_func_def(gnb_info_dt, "dt-gnb")
        if func_def_sub_dict_dt is None:
            self.kpm_func.terminate(signal.SIGTERM, None)
            return

        self._init_slice_runtime(self.selected_gnb.inventory_name)
        self._init_slice_runtime(self.selected_gnb_dt.inventory_name)

        # Subscribe DT first so its indications can immediately drive control.
        self._subscribe_per_slice(self.selected_gnb_dt, func_def_sub_dict_dt, "dt-gnb")
        self._subscribe_per_slice(self.selected_gnb, func_def_sub_dict, "real-gnb")

        self.xapp_gen.run()


def main(args):
    config = load_config(args.config)
    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    xapp_gen.logger.set_level(string_to_level[args.log_level])
    xapp_container = xAppMonControlContainer(
        xapp_gen,
        args.gnb_target,
        args.gnb_dt_target,
        args.csv_file,
        args.event_trigger,
        config,
        ack_timeout=args.ack_timeout)
    xapp_container.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="digital twin prb xApp")

    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")
    parser.add_argument("-c", "--csv_file", metavar="<csv_file>",
                        help="path of csv file",
                        type=str)
    parser.add_argument("-e", "--event_trigger", metavar="<event_trigger_period>",
                        help="event trigger period in seconds",
                        type=int, default=1)
    parser.add_argument("-f", "--config", metavar="<config_file>",
                        help="path of the PRB control JSON config (see config/prb_control_conf.json)",
                        type=str, default="./config/prb_control_conf.json")
    parser.add_argument("-l", "--log_level", metavar="<log_level>",
                        help="Log level", type=str, default="INFO")
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="real gNB to subscribe to",
                        type=str, required=True)
    parser.add_argument("-G", "--gnb_dt_target", metavar="<gnb_dt_target>",
                        help="digital twin gNB to subscribe to (control is applied here first)",
                        type=str, required=True)
    parser.add_argument("--ack_timeout", metavar="<seconds>",
                        help="Seconds to wait for an ACK before resending a control. Default 5.0",
                        type=float, default=5.0)

    main(parser.parse_args())
