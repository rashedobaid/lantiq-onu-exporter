from pathlib import Path

import pytest

from lantiq_onu_exporter import metrics
from lantiq_onu_exporter.commands import works
from lantiq_onu_exporter.parsers import cpu_usage, parse, parse_cpu, parse_lan, parse_laser_age, parse_otop, parse_ploam
from lantiq_onu_exporter.ssh import ANSI

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def reading():
    return parse((FIXTURES / "g010sp_shell_poll.txt").read_text())


def test_ploam_and_link(reading):
    assert reading.values["gpon_ploam_state"] == 5
    assert reading.values["gpon_lan_link_speed_mbps"] == 2500
    assert reading.values["gpon_lan_full_duplex"] == 1


def test_optics(reading):
    v = reading.values
    assert -30 < v["gpon_rx_power_dbm"] < -5
    assert v["gpon_rx_power_milliwatts"] == pytest.approx(10 ** (v["gpon_rx_power_dbm"] / 10), rel=0.05)
    assert 0 < v["gpon_tx_power_dbm"] < 6
    assert 0 < v["gpon_laser_bias_current_milliamps"] < v["gpon_laser_modulation_current_milliamps"]
    assert 3.1 < v["gpon_supply_voltage_volts"] < 3.5
    assert 30 < v["gpon_apd_voltage_volts"] < 60
    assert v["gpon_signal_detect"] == 1
    assert v["gpon_pll_locked"] == 1


def test_temperatures_converted_from_kelvin(reading):
    assert 0 < reading.values["gpon_laser_temperature_celsius"] < 100
    assert 0 < reading.values["gpon_die_temperature_celsius"] < 100


def test_laser_age_is_days_hours_minutes():
    assert parse_laser_age("1:02:03") == 86400 + 2 * 3600 + 3 * 60
    assert parse_laser_age("garbage") is None


def test_system_metrics(reading):
    v = reading.values
    assert v["gpon_uptime_seconds"] > 0
    assert 0 < v["gpon_memory_available_bytes"] < v["gpon_memory_total_bytes"]
    assert reading.cpu is not None


def test_gtc_counters(reading):
    assert {"bip", "hec_error_corr", "fec_words_uncorr", "rx_gem_frames_dropped"} <= set(reading.gtc)


def test_unknown_link_code_is_none():
    assert (
        parse_lan("errorcode=0 pport=0 mode=15 enable=1 link_status=3 phy_duplex=1")["gpon_lan_link_speed_mbps"] is None
    )


def test_long_command_name_output_parses():
    assert parse_ploam("errorcode=0 curr_state=2 previous_state=1 elapsed_msec=10")["gpon_ploam_state"] == 2


def test_otop_from_a_terminal_is_cleaned_and_parsed():
    raw = (
        "\x1b[28;1HDDMI voltage                                       3253.05mV   \x1b[K"
        "\x1b[29;1HRSSI 1490 power                                    18.36uW -17.24dBm \x1b[K"
        "\x1b[30;1Htx power (se*(bias+mod/2-ith))                     1.66mW 2.19dBm  \x1b[K"
    )
    values = parse_otop(ANSI.sub("\n", raw))
    assert values["gpon_rx_power_dbm"] == -17.24
    assert values["gpon_tx_power_dbm"] == 2.19
    assert values["gpon_supply_voltage_volts"] == pytest.approx(3.25305)


def test_cpu_usage_between_polls():
    first = parse_cpu("cpu  100 0 100 800 0 0 0 0 0 0")
    second = parse_cpu("cpu  110 0 110 880 0 0 0 0 0 0")
    assert cpu_usage(first, second) == pytest.approx(0.2)
    assert cpu_usage(None, second) is None
    assert cpu_usage(second, first) is None


@pytest.mark.parametrize(
    "output, expected",
    [
        ("errorcode=0 curr_state=5 previous_state=4", True),
        ("errorcode=-1 (unknown command)", False),
        ("ash: onu: not found", False),
        ("otop: ../libtop/top_linux.c: 29: console_cbreak: Assertion `res == 0' failed.", False),
        ("", False),
    ],
)
def test_command_rejection_detection(output, expected):
    assert works(output) is expected


def test_every_parsed_value_has_a_metric(reading):
    assert set(reading.values) <= set(metrics.VALUE_METRICS)
    assert "gpon_cpu_usage_ratio" in metrics.VALUE_METRICS
