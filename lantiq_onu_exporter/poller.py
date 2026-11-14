import logging
import threading
import time

from . import metrics
from .commands import Commands
from .parsers import cpu_usage, parse
from .ssh import Connection

log = logging.getLogger(__name__)


class Poller:
    def __init__(self, config):
        self.config = config
        self.connection = Connection(config)
        self.commands = Commands(self.connection, config)
        self.previous_cpu = None
        self.stop = threading.Event()

    def poll_once(self):
        start = time.time()
        try:
            if not self.connection.active:
                self.connection.open()
                self.commands.reset()
            output = self.commands.poll()
            reading = parse(output)
            values = dict(reading.values)
            if values.get("gpon_ploam_state") is None and values.get("gpon_rx_power_dbm") is None:
                raise RuntimeError(f"unrecognised output: {output[:200]!r}")
            values["gpon_cpu_usage_ratio"] = cpu_usage(self.previous_cpu, reading.cpu)
            self.previous_cpu = reading.cpu
            metrics.publish(values, reading.gtc)
            metrics.UP.set(1)
            metrics.LAST_SUCCESS.set(time.time())
        except Exception as e:
            log.warning("collection failed: %s", e)
            self.connection.close()
            self.commands.reset()
            metrics.clear()
            metrics.UP.set(0)
        finally:
            metrics.DURATION.set(time.time() - start)

    def run_forever(self):
        interval = self.config.poll_interval
        next_run = time.monotonic()
        while not self.stop.is_set():
            self.poll_once()
            next_run += interval
            self.stop.wait(max(0.0, next_run - time.monotonic()))
            next_run = max(next_run, time.monotonic() - interval)
