import math

from prometheus_client import REGISTRY, Gauge
from prometheus_client.core import CounterMetricFamily

VALUE_METRICS = {
    "gpon_ploam_state": "PLOAM state number (1-7, 5 = O5 operational)",
    "gpon_rx_power_dbm": "Received optical power at 1490nm (dBm)",
    "gpon_rx_power_milliwatts": "Received optical power at 1490nm (mW)",
    "gpon_tx_power_dbm": "Transmitted optical power (dBm)",
    "gpon_tx_power_milliwatts": "Transmitted optical power (mW)",
    "gpon_laser_temperature_celsius": "Laser temperature (external sensor)",
    "gpon_die_temperature_celsius": "Chip die temperature (internal sensor)",
    "gpon_laser_bias_current_milliamps": "Actual laser bias current",
    "gpon_laser_modulation_current_milliamps": "Actual laser modulation current",
    "gpon_laser_bias_errors": "Bias regulation error count",
    "gpon_laser_modulation_errors": "Modulation regulation error count",
    "gpon_supply_voltage_volts": "DDMI supply voltage",
    "gpon_apd_voltage_volts": "APD bias voltage (DCDC regulated)",
    "gpon_signal_detect": "1 if optical signal is detected",
    "gpon_pll_locked": "1 if the PLL is locked",
    "gpon_laser_active_seconds": "Laser active time as reported by otop",
    "gpon_lan_link_speed_mbps": "Host-side (SFP to router) link speed",
    "gpon_lan_full_duplex": "1 if the host-side link is full duplex",
    "gpon_uptime_seconds": "Stick uptime",
    "gpon_load1": "1-minute load average",
    "gpon_load5": "5-minute load average",
    "gpon_load15": "15-minute load average",
    "gpon_cpu_usage_ratio": "CPU busy fraction since the previous poll (0-1)",
    "gpon_memory_total_bytes": "Total RAM",
    "gpon_memory_available_bytes": "Available RAM (MemAvailable, or free + buffers + cached)",
}
GTC_ERRORS = {
    "bip": "bip",
    "hec_error_corr": "hec_corrected",
    "hec_error_uncorr": "hec_uncorrected",
    "bwmap_error_corr": "bwmap_corrected",
    "bwmap_error_uncorr": "bwmap_uncorrected",
    "fec_words_corr": "fec_corrected",
    "fec_words_uncorr": "fec_uncorrected",
    "allocations_lost": "allocations_lost",
}
GTC_DROPS = {"rx_gem_frames_dropped": "rx_gem", "omci_drop": "omci", "drop": "other"}

UP = Gauge("gpon_up", "1 if the last SSH collection succeeded")
LAST_SUCCESS = Gauge("gpon_last_success_timestamp_seconds", "Unix time of the last successful collection")
DURATION = Gauge("gpon_collect_duration_seconds", "Duration of the last collection")
GAUGES = {name: Gauge(name, description) for name, description in VALUE_METRICS.items()}


class GtcCounters:
    def __init__(self):
        self.fields = {}

    def collect(self):
        if not self.fields:
            return
        errors = CounterMetricFamily("gpon_gtc_errors", "GTC line errors since boot", labels=["type"])
        for key, label in GTC_ERRORS.items():
            if key in self.fields:
                errors.add_metric([label], self.fields[key])
        drops = CounterMetricFamily("gpon_gtc_dropped_frames", "GTC frames dropped since boot", labels=["reason"])
        for key, label in GTC_DROPS.items():
            if key in self.fields:
                drops.add_metric([label], self.fields[key])
        yield errors
        yield drops


GTC = GtcCounters()
REGISTRY.register(GTC)


def publish(values, gtc):
    for name, gauge in GAUGES.items():
        value = values.get(name)
        gauge.set(math.nan if value is None else value)
    GTC.fields = gtc


def clear():
    for gauge in GAUGES.values():
        gauge.set(math.nan)
    GTC.fields = {}
