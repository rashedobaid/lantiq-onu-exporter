# lantiq-onu-exporter

Prometheus exporter for Lantiq Falcon based GPON SFP ONU sticks. It logs into the stick over SSH, reads the optical,
PLOAM, link and line-error status with the stick's own `onu` and `otop` tools, and exposes everything as Prometheus
metrics.

## Supported hardware

All Lantiq Falcon based GPON SFP sticks with SSH access and the `onu` / `otop` tools:

| Stick | Status | Notes |
|---|---|---|
| Alcatel-Lucent / Nokia **G-010S-P** | Tested (OpenWrt SFP 7.5.3) | Full shell, often passwordless root |
| Nokia **G-010S-A** | Supported, not yet tested on hardware | Set `GPON_USER` / `GPON_PASSWORD` to your firmware's login |
| Huawei **MA5671A** (and FS.com GPON-ONU-34-20BI) | Supported, not yet tested on hardware | Some firmware only offers a restricted shell, see below |

Default logins, firmware variants and how to reach the stick are documented on hack-gpon.org:
[G-010S-P](https://hack-gpon.org/ont-nokia-g-010s-p/), [G-010S-A](https://hack-gpon.org/ont-nokia-g-010s-a/),
[MA5671A](https://hack-gpon.org/ont-huawei-ma5671a/). Reports from other sticks are welcome.

Firmware differences are detected automatically on connect:

- **Command names:** some builds only accept the long `onu` command names (`ploam_state_get` instead of `ploamsg`,
  `lan_port_status_get`, `gtc_total_counter_get`). The exporter tries the short name first, then the long one.
- **Restricted shells:** some MA5671A firmware logs into a "minishell" that only runs a few whitelisted commands, with
  no pipes or `/proc`. The exporter then runs each command on its own (single mode). The system metrics (uptime,
  load, CPU, memory) are not available in that mode.
- **Tool location:** without a full shell, the tools are tried by name and then in each directory of
  `GPON_TOOLS_PATH`.
- **`otop` without batch mode:** if only plain `otop -g s` is allowed, it is run in a pseudo-terminal (it refuses to
  start without one) and the first complete screen is parsed.
- **Old SSH servers:** these sticks run old Dropbear versions. The bundled paramiko still offers the legacy algorithms
  they need (`diffie-hellman-group1-sha1`, `ssh-rsa`, `ssh-dss`, CBC ciphers), so no extra setup is required.

The chosen mode and commands are logged once per connection, e.g.
`command mode: shell, onu: onu ploamsg, onu lanpsg 0, onu gtctcg, otop: otop -b -g s`.

## How it works

The exporter keeps one SSH connection open and polls the stick every `POLL_INTERVAL` seconds. With a full shell all
of this runs as one command per poll:

| Command | Provides |
|---|---|
| `onu ploamsg` | PLOAM state (O1–O7, O5 = operational) |
| `onu lanpsg 0` | Link speed and duplex between the stick and the host |
| `onu gtctcg` | GTC line error and dropped-frame counters |
| `otop -b -g s` | RX/TX optical power, temperatures, laser bias/modulation current, supply and APD voltage, signal detect, PLL lock |
| `/proc/uptime`, `/proc/loadavg`, `/proc/stat`, `/proc/meminfo` | Uptime, load, CPU usage, memory |

One poll costs the stick roughly 0.2 s of CPU time, about 2 % CPU at a 10 s interval. Metrics are served on
`http://<host>:9877/metrics`.

SSH is used rather than the stick's LuCI web endpoints on purpose: those endpoints run the same commands behind an
HTTPS request and a Lua runtime, which is much heavier on the stick's CPU, they expose less data (no error counters),
and their login sessions expire.

## Quick start

With Docker Compose:

```sh
cp .env.example .env    # set GPON_HOST (and credentials if your stick needs them)
docker compose up -d
curl -s localhost:9877/metrics | grep '^gpon_up'
```

With plain Docker:

```sh
docker build -t lantiq-onu-exporter .
docker run -d --name lantiq-onu-exporter -p 9877:9877 --env-file .env lantiq-onu-exporter
```

Without Docker (Python 3.9+):

```sh
pip install .
GPON_HOST=192.168.1.10 lantiq-onu-exporter
```

or straight from a checkout: `pip install -r requirements.txt && GPON_HOST=192.168.1.10 python -m lantiq_onu_exporter`.

To log in with an SSH key, mount it into the container and point `GPON_KEY_FILE` at the path inside it, e.g. add
`volumes: ["./id_ed25519:/keys/id_ed25519:ro"]` to the service in `compose.yml` and set
`GPON_KEY_FILE=/keys/id_ed25519` in `.env`.

The machine running the exporter must be able to reach the stick's management IP. Behind a router this usually means
an IP alias on the WAN interface in the stick's subnet and an outbound NAT rule for it.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GPON_HOST` | (required) | IP or hostname of the stick |
| `GPON_PORT` | `22` | SSH port |
| `GPON_USER` | `root` | SSH user |
| `GPON_PASSWORD` | (empty) | SSH password. Leave empty for firmware with a passwordless root account |
| `GPON_KEY_FILE` | (empty) | Path to an SSH private key, as an alternative to a password |
| `POLL_INTERVAL` | `30` | Seconds between polls |
| `LISTEN_PORT` | `9877` | Port for the `/metrics` endpoint |
| `LOG_LEVEL` | `INFO` | Python log level |
| `GPON_COMMAND_MODE` | `auto` | `auto` detects the shell, `shell` forces one combined command per poll, `single` forces one command at a time (restricted shells) |
| `GPON_TOOLS_PATH` | `/opt/lantiq/bin:/usr/bin:/usr/sbin:/bin:/sbin` | Where to look for `onu` and `otop` |

With neither a password nor a key, the exporter uses SSH's `none` authentication method and falls back to an empty
password, which is what stock firmware with a passwordless root account expects.

## Metrics

| Metric | Unit / values |
|---|---|
| `gpon_up` | 1 if the last poll succeeded |
| `gpon_last_success_timestamp_seconds` | Unix time of the last successful poll |
| `gpon_collect_duration_seconds` | Duration of the last poll |
| `gpon_ploam_state` | 1–7 (5 = O5 operational) |
| `gpon_rx_power_dbm`, `gpon_rx_power_milliwatts` | Received optical power (1490 nm) |
| `gpon_tx_power_dbm`, `gpon_tx_power_milliwatts` | Transmitted optical power (1310 nm) |
| `gpon_laser_temperature_celsius`, `gpon_die_temperature_celsius` | Laser and chip temperature |
| `gpon_laser_bias_current_milliamps`, `gpon_laser_modulation_current_milliamps` | Laser currents |
| `gpon_laser_bias_errors`, `gpon_laser_modulation_errors` | Laser regulation error counts |
| `gpon_supply_voltage_volts` | 3.3 V supply rail |
| `gpon_apd_voltage_volts` | Avalanche photodiode bias voltage |
| `gpon_signal_detect`, `gpon_pll_locked` | 1 / 0 |
| `gpon_laser_active_seconds` | Time the laser has been transmitting |
| `gpon_lan_link_speed_mbps`, `gpon_lan_full_duplex` | Stick-to-host link (1000 or 2500 Mbit/s) |
| `gpon_gtc_errors_total{type}` | Line errors since boot: `bip`, `hec_corrected`, `hec_uncorrected`, `bwmap_corrected`, `bwmap_uncorrected`, `fec_corrected`, `fec_uncorrected`, `allocations_lost` |
| `gpon_gtc_dropped_frames_total{reason}` | Dropped frames since boot: `rx_gem`, `omci`, `other` |
| `gpon_uptime_seconds` | Stick uptime |
| `gpon_load1`, `gpon_load5`, `gpon_load15` | Load averages |
| `gpon_cpu_usage_ratio` | CPU busy share between two polls (0–1) |
| `gpon_memory_total_bytes`, `gpon_memory_available_bytes` | Memory |

When a poll fails, every value metric is set to `NaN` and `gpon_up` to 0, so dashboards show a gap instead of stale
values.

## Prometheus

```yaml
scrape_configs:
  - job_name: gpon
    scrape_interval: 10s
    static_configs:
      - targets: ["lantiq-onu-exporter:9877"]
```

Match `scrape_interval` to `POLL_INTERVAL`. Metric names keep the `gpon_` prefix, since they describe the GPON link
rather than this exporter.

## Notes

- **Link speed:** `onu lanpsg 0` reports a `link_status` code. 4 means 1000 Mbit/s and 5 means 2500 Mbit/s, the same
  mapping the stick's own web UI uses. Other codes are exported as `NaN`.
- **Laser active time:** `otop` reports it as `days:hours:minutes`. The laser transmits in bursts, so it grows slower
  than uptime.
- **Memory:** kernel 3.10 has no `MemAvailable`, so available memory is `MemFree + Buffers + Cached`.
- **CPU usage** includes the exporter's own SSH session. Interactive SSH logins cause short spikes, because the key
  exchange is expensive on the stick's CPU.
- **Load average** on these sticks often sits around 1 even when idle, because kernel threads waiting on hardware count
  towards it.
- **`otop` output** is piped through `head`, so a batch-mode `otop` that keeps printing can never block a poll.
- **FEC counters** stay at 0 if the OLT has downstream FEC disabled.
- **Counters** (`*_total`) reset when the stick reboots. Prometheus `rate()` and `increase()` handle that.

## Project layout

```
lantiq_onu_exporter/
├── __main__.py   entry point (python -m lantiq_onu_exporter, or the lantiq-onu-exporter command)
├── config.py     settings from environment variables, validated at startup
├── ssh.py        SSH connection, timeouts, reading command output (optionally through a pseudo-terminal)
├── commands.py   command tables, firmware detection, running one poll
├── parsers.py    pure functions turning command output into values
├── metrics.py    Prometheus metric definitions and publishing
└── poller.py     the polling loop
tests/
├── fixtures/     real output captured from a G-010S-P
├── test_parsers.py
└── test_config.py
```

## Development

```sh
pip install -e ".[test]"
pytest
```

The parser tests run against real output in `tests/fixtures/`. To add support for another stick, capture one poll
(the commands listed under "How it works") into a new fixture and add tests for it.

## License

[MIT](LICENSE)
