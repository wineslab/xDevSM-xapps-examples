import argparse
import dataclasses
import json
from dataclasses import dataclass
from typing import Optional, Sequence

from xdevsm.sm_framework.py_oran.ccc.constants import (
    MIN_REPORT_PERIOD_MS,
    RESOURCE_TYPE_PRB_DL,
    RESOURCE_TYPE_PRB_UL,
)

# Section of the xApp descriptor `controls` that holds the test configuration.
CONTROLS_SECTION = "ccc_report_test"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
SD_HEX_DIGITS = 6
NCI_HEX_DIGITS = 9
MAX_PERCENT = 100


@dataclass(frozen=True)
class RunConfig:
    gnb_target: Optional[str] = None
    nci: Optional[int] = None
    sst: Optional[int] = None
    sd: Optional[str] = None
    resource_type: str = RESOURCE_TYPE_PRB_DL
    control_max_ratio: int = 50
    period_ms: int = 1000
    periodic_count: int = 2
    e2_node_timeout_s: float = 60.0
    subscription_timeout_s: float = 10.0
    indication_timeout_s: float = 5.0
    control_ack_timeout_s: float = 5.0
    log_level: str = "INFO"

    @property
    def period_s(self) -> float:
        return self.period_ms / 1000.0

    def validate(self) -> "RunConfig":
        if self.period_ms < MIN_REPORT_PERIOD_MS:
            raise ValueError("period_ms must be at least {}".format(MIN_REPORT_PERIOD_MS))
        if self.periodic_count < 1:
            raise ValueError("periodic_count must be at least 1")
        if not 1 <= self.control_max_ratio <= MAX_PERCENT:
            raise ValueError("control_max_ratio must be in 1..{}".format(MAX_PERCENT))
        if self.resource_type not in (RESOURCE_TYPE_PRB_DL, RESOURCE_TYPE_PRB_UL):
            raise ValueError("resource_type must be {} or {}".format(RESOURCE_TYPE_PRB_DL, RESOURCE_TYPE_PRB_UL))
        if self.sd is not None and (len(self.sd) != SD_HEX_DIGITS or not _is_hex(self.sd)):
            raise ValueError("sd must be {} hexadecimal digits".format(SD_HEX_DIGITS))
        if self.nci is not None and not 0 <= self.nci < 1 << 36:
            raise ValueError("nci must be a 36-bit NR Cell Identity")
        if self.log_level not in LOG_LEVELS:
            raise ValueError("log_level must be one of {}".format(", ".join(LOG_LEVELS)))
        for field in ("e2_node_timeout_s", "subscription_timeout_s", "indication_timeout_s", "control_ack_timeout_s"):
            if getattr(self, field) <= 0:
                raise ValueError("{} must be positive".format(field))
        return self


def _is_hex(text: str) -> bool:
    return all(c in "0123456789abcdefABCDEF" for c in text)


def _nci(text: str) -> int:
    """An NR Cell Identity as 9 hexadecimal digits (the CCC JSON form), as 0x-prefixed hex, or as decimal."""
    text = text.strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    if len(text) == NCI_HEX_DIGITS and _is_hex(text):
        return int(text, 16)
    return int(text, 10)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="E2SM-CCC REPORT end-to-end test xApp for OCUDU. The CLI options override the "
                    "controls.{} section of the xApp descriptor.".format(CONTROLS_SECTION))
    p.add_argument("--config", metavar="<path>", help="xApp descriptor; default: $CONFIG_FILE")
    p.add_argument("-r", "--route-file", default="./config/uta_rtg.rt", metavar="<path>",
                   help="static RMR route table")
    p.add_argument("-g", "--gnb-target", metavar="<inventory name>",
                   help="E2 node to test; default: the first connected E2 node")
    p.add_argument("--nci", type=_nci, metavar="<NCI>",
                   help="NR Cell Identity of the cell to control: 9 hex digits as in the CCC JSON (00066C000), "
                        "0x-prefixed hex, or decimal; default: the first cell")
    p.add_argument("--sst", type=int, help="SST of the RRM policy member to control; default: the first member")
    p.add_argument("--sd", metavar="<6 hex digits>", help="SD of the RRM policy member to control")
    p.add_argument("--resource-type", choices=(RESOURCE_TYPE_PRB_DL, RESOURCE_TYPE_PRB_UL),
                   help="resourceType of the O-RRMPolicyRatio control")
    p.add_argument("--control-max-ratio", type=int, metavar="<percent>",
                   help="rRMPolicyMaxRatio that the control sets before it restores the original value")
    p.add_argument("--period-ms", type=int, metavar="<ms>", help="period of the periodic event triggers")
    p.add_argument("--periodic-count", type=int, metavar="<n>",
                   help="periodic indications to receive before the control")
    p.add_argument("--e2-node-timeout-s", type=float, metavar="<s>", help="wait for a connected E2 node")
    p.add_argument("--subscription-timeout-s", type=float, metavar="<s>",
                   help="wait for the subscription responses")
    p.add_argument("--indication-timeout-s", type=float, metavar="<s>",
                   help="wait for an uponSubscription or uponChange indication")
    p.add_argument("--control-ack-timeout-s", type=float, metavar="<s>",
                   help="wait for the RIC Control Acknowledge")
    p.add_argument("--log-level", choices=LOG_LEVELS)
    return p


def load(argv: Optional[Sequence[str]], default_descriptor: Optional[str]):
    """Return (RunConfig, parsed arguments, descriptor path). Raises ValueError for an invalid or unknown setting,
    OSError if the descriptor cannot be read."""
    args = parser().parse_args(argv)
    path = args.config or default_descriptor
    descriptor = read_descriptor(path)
    fields = {f.name for f in dataclasses.fields(RunConfig)}
    section = ((descriptor or {}).get("controls") or {}).get(CONTROLS_SECTION) or {}
    unknown = sorted(set(section) - fields)
    if unknown:
        raise ValueError("unknown settings in controls.{}: {}".format(CONTROLS_SECTION, ", ".join(unknown)))
    values = dict(section)
    if isinstance(values.get("nci"), str):
        values["nci"] = _nci(values["nci"])
    for name in fields:
        cli_value = getattr(args, name, None)
        if cli_value is not None:
            values[name] = cli_value
    return RunConfig(**values).validate(), args, path


def read_descriptor(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    with open(path) as f:
        return json.load(f)
