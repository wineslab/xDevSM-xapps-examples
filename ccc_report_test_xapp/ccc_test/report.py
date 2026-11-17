import logging
from dataclasses import dataclass
from typing import Iterable, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check(name: str, problems: Iterable[str], ok_detail: str = "") -> CheckResult:
    """PASS if ``problems`` is empty, else FAIL with the problems as detail."""
    problems = list(problems)
    if problems:
        return CheckResult(name, False, "; ".join(problems))
    return CheckResult(name, True, ok_detail)


class Report:
    """Collects the check results and logs one PASS or FAIL line per check."""

    def __init__(self):
        self.results: List[CheckResult] = []

    def add(self, result: CheckResult) -> CheckResult:
        self.results.append(result)
        verdict = "PASS" if result.passed else "FAIL"
        line = "{} {}".format(verdict, result.name)
        if result.detail:
            line += ": " + result.detail
        if result.passed:
            logger.info(line)
        else:
            logger.error(line)
        return result

    @property
    def failed(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        failed = len(self.failed)
        return "SUMMARY {}: {} checks, {} PASS, {} FAIL".format(
            "FAIL" if failed or not self.results else "PASS", len(self.results), len(self.results) - failed, failed)

    def exit_code(self) -> int:
        return 1 if self.failed or not self.results else 0
