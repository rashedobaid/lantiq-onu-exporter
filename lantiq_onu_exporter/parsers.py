import re
from typing import NamedTuple, Optional

from .commands import SYS_MARKER

NUM = r"([-+]?\d+(?:\.\d+)?|[-+]?inf)"
POWER_TO_MW = {"nW": 1e-6, "uW": 1e-3, "mW": 1.0, "W": 1e3}
LINK_STATUS_MBPS = {4: 1000, 5: 2500}


class Reading(NamedTuple):
    values: dict[str, Optional[float]]
    gtc: dict[str, int]
    cpu: Optional[tuple[int, int]]


def parse(output):
    stick_output, _, sys_output = output.partition(SYS_MARKER)
    values = {}
    values.update(parse_sys(sys_output))
    values.update(parse_ploam(stick_output))
    values.update(parse_lan(stick_output))
    values.update(parse_otop(stick_output))
    return Reading(values=values, gtc=parse_gtc(stick_output), cpu=parse_cpu(sys_output))


def parse_ploam(text):
    m = re.search(r"curr_state=(\d+)", text)
    return {"gpon_ploam_state": int(m.group(1))} if m else {}


def parse_lan(text):
    m = re.search(r"link_status=(\d+) phy_duplex=(\d+)", text)
    if not m:
        return {}
    return {
        "gpon_lan_link_speed_mbps": LINK_STATUS_MBPS.get(int(m.group(1))),
        "gpon_lan_full_duplex": int(m.group(2) == "1"),
    }


def parse_gtc(text):
    m = re.search(r"^errorcode=0 bip=.*$", text, re.M)
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m.group(0))} if m else {}


def otop_fields(text):
    fields = {}
    for line in text.splitlines():
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) == 2:
            fields.setdefault(parts[0].rstrip(":").strip(), parts[1].strip())
    return fields


def field(fields, prefix):
    for label, value in fields.items():
        if label.startswith(prefix):
            return value
    return None


def parse_power(value):
    if value is None:
        return None, None
    mw = dbm = None
    m = re.search(NUM + r"\s*(nW|uW|mW|W)\b", value)
    if m:
        mw = float(m.group(1)) * POWER_TO_MW[m.group(2)]
    m = re.search(NUM + r"\s*dBm", value)
    if m:
        dbm = float(m.group(1))
    return mw, dbm


def first_number(value, unit):
    if value is None:
        return None
    m = re.search(NUM + re.escape(unit), value)
    return float(m.group(1)) if m else None


def parse_laser_age(value):
    m = re.match(r"(\d+):(\d+):(\d+)", value or "")
    if not m:
        return None
    days, hours, minutes = map(int, m.groups())
    return days * 86400 + hours * 3600 + minutes * 60


def parse_otop(text):
    f = otop_fields(text)
    if not f:
        return {}
    values = {}
    values["gpon_rx_power_milliwatts"], values["gpon_rx_power_dbm"] = parse_power(field(f, "RSSI 1490 power"))
    values["gpon_tx_power_milliwatts"], values["gpon_tx_power_dbm"] = parse_power(field(f, "tx power"))
    for name, prefix in (
        ("gpon_laser_temperature_celsius", "laser temperature"),
        ("gpon_die_temperature_celsius", "die temperature"),
    ):
        kelvin = first_number(field(f, prefix), "K")
        values[name] = None if kelvin is None else round(kelvin - 273.15, 2)
    currents = field(f, "actual bias / modulation current")
    m = re.search(NUM + r"mA\s*/\s*" + NUM + r"mA", currents or "")
    if m:
        values["gpon_laser_bias_current_milliamps"] = float(m.group(1))
        values["gpon_laser_modulation_current_milliamps"] = float(m.group(2))
    m = re.search(r"\((\d+)\s*/\s*(\d+)\)", field(f, "bias / modulation change") or "")
    if m:
        values["gpon_laser_bias_errors"], values["gpon_laser_modulation_errors"] = int(m.group(1)), int(m.group(2))
    millivolts = first_number(field(f, "DDMI voltage"), "mV")
    values["gpon_supply_voltage_volts"] = None if millivolts is None else millivolts / 1000
    values["gpon_apd_voltage_volts"] = first_number(field(f, "DCDC APD voltage"), "V")
    signal = field(f, "Signal detect")
    if signal is not None:
        values["gpon_signal_detect"] = int(signal.lower().startswith("true"))
    pll = field(f, "PLL lock status")
    if pll is not None:
        values["gpon_pll_locked"] = int(pll.lower().startswith("locked"))
    values["gpon_laser_active_seconds"] = parse_laser_age(field(f, "laser age"))
    return values


def parse_sys(text):
    values = {}
    lines = text.splitlines()
    if len(lines) >= 2:
        try:
            values["gpon_uptime_seconds"] = float(lines[0].split()[0])
            values["gpon_load1"], values["gpon_load5"], values["gpon_load15"] = map(float, lines[1].split()[:3])
        except (IndexError, ValueError):
            pass
    mem = {k: int(v) * 1024 for k, v in re.findall(r"^(\w+):\s+(\d+) kB", text, re.M)}
    if "MemTotal" in mem:
        values["gpon_memory_total_bytes"] = mem["MemTotal"]
        values["gpon_memory_available_bytes"] = mem.get(
            "MemAvailable", mem.get("MemFree", 0) + mem.get("Buffers", 0) + mem.get("Cached", 0)
        )
    return values


def parse_cpu(text):
    m = re.search(r"^cpu\s+([\d ]+)$", text, re.M)
    if not m:
        return None
    ticks = [int(t) for t in m.group(1).split()]
    idle = ticks[3] + (ticks[4] if len(ticks) > 4 else 0)
    return idle, sum(ticks)


def cpu_usage(previous, current):
    if not previous or not current or current[1] <= previous[1]:
        return None
    return 1 - (current[0] - previous[0]) / (current[1] - previous[1])
