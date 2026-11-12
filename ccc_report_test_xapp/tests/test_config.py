import json

import pytest

from ccc_test.config import RunConfig, load


def _descriptor(tmp_path, section):
    path = tmp_path / "config-file.json"
    path.write_text(json.dumps({"controls": {"ccc_report_test": section}}))
    return str(path)


def test_defaults_without_descriptor():
    cfg, args, path = load([], None)
    assert cfg == RunConfig()
    assert path is None
    assert args.route_file == "./config/uta_rtg.rt"


def test_cli_overrides_the_descriptor(tmp_path):
    path = _descriptor(tmp_path, {"period_ms": 500, "nci": "0x00066C000", "sst": 1})
    cfg, _, used = load(["--period-ms", "200", "--sd", "000001"], path)
    assert used == path
    assert (cfg.period_ms, cfg.nci, cfg.sst, cfg.sd) == (200, 0x00066C000, 1, "000001")
    assert cfg.period_s == pytest.approx(0.2)


@pytest.mark.parametrize("text", ["00066C000", "0x66C000", "6733824"])
def test_nci_accepts_the_ccc_json_hex_and_decimal_forms(text):
    cfg, _, _ = load(["--nci", text], None)
    assert cfg.nci == 0x00066C000


@pytest.mark.parametrize("section", [{"unknown": 1}, {"period_ms": 5}, {"control_max_ratio": 0}, {"sd": "1"},
                                     {"resource_type": "PRB"}, {"indication_timeout_s": 0}])
def test_invalid_settings_raise(tmp_path, section):
    with pytest.raises(ValueError):
        load([], _descriptor(tmp_path, section))
