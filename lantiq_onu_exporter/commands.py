import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger(__name__)

ONU_COMMANDS = {
    "ploam": ("onu ploamsg", "onu ploam_state_get"),
    "lan": ("onu lanpsg 0", "onu lan_port_status_get 0"),
    "gtc": ("onu gtctcg", "onu gtc_total_counter_get"),
}
OTOP_COMMANDS = ("otop -b -g s", "otop -g s")
OTOP_LAST_FIELD = "DCDC APD voltage"
OTOP_SIGNATURE = "RSSI 1490 power"
SYS_COMMAND = "cat /proc/uptime /proc/loadavg; head -n 1 /proc/stat; cat /proc/meminfo"
SYS_MARKER = "@@sys\n"
REJECTED = re.compile(r"unknown command|not found|invalid|not allowed|permission denied|assertion", re.I)


def works(output):
    return bool(output.strip()) and not REJECTED.search(output)


@dataclass
class Plan:
    shell: bool
    onu: Dict[str, str] = field(default_factory=dict)
    otop: Optional[str] = None

    @property
    def otop_in_shell(self):
        return bool(self.shell and self.otop and "-b" in self.otop)

    def describe(self):
        return (f"command mode: {'shell' if self.shell else 'single'}, "
                f"onu: {', '.join(self.onu.values()) or 'none'}, otop: {self.otop or 'none'}")


class Commands:
    def __init__(self, connection, config):
        self.connection = connection
        self.config = config
        self.plan = None

    def reset(self):
        self.plan = None

    def _prefix(self, shell):
        return f"export PATH={self.config.tools_path}; " if shell else ""

    def _variants(self, command, shell):
        if shell:
            return [command]
        return [command] + [f"{directory.rstrip('/')}/{command}"
                            for directory in self.config.tools_path.split(":") if directory]

    def _run_otop(self, command, shell):
        if shell and "-b" in command:
            return self.connection.run(f"{self._prefix(True)}{command} 2>&1 | head -n 60")
        return self.connection.run(self._prefix(shell) + command, timeout=15, pty="-b" not in command,
                                   stop=OTOP_LAST_FIELD)

    def _detect_shell(self):
        if self.config.command_mode != "auto":
            return self.config.command_mode == "shell"
        return "@@probe" in self.connection.run(f"{self._prefix(True)}echo @@probe", timeout=10)

    def detect(self):
        shell = self._detect_shell()
        plan = Plan(shell=shell)
        for key, candidates in ONU_COMMANDS.items():
            for command in (v for c in candidates for v in self._variants(c, shell)):
                suffix = " 2>&1" if shell else ""
                if works(self.connection.run(self._prefix(shell) + command + suffix, timeout=10)):
                    plan.onu[key] = command
                    break
        for command in (v for c in OTOP_COMMANDS for v in self._variants(c, shell)):
            output = self._run_otop(command, shell)
            if works(output) and OTOP_SIGNATURE in output:
                plan.otop = command
                break
        log.info(plan.describe())
        self.plan = plan
        return plan

    def poll(self):
        plan = self.plan or self.detect()
        if plan.shell:
            parts = [f"{command} 2>&1" for command in plan.onu.values()]
            if plan.otop_in_shell:
                parts.append(f"{plan.otop} 2>&1 | head -n 60")
            output = self.connection.run(self._prefix(True) + "; ".join(parts + [f"echo @@sys; {SYS_COMMAND}"]))
        else:
            output = "\n".join(self.connection.run(command) for command in plan.onu.values()) + "\n" + SYS_MARKER
        if plan.otop and not plan.otop_in_shell:
            output = self._run_otop(plan.otop, plan.shell) + "\n" + output
        return output
