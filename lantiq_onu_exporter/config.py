import os
from dataclasses import dataclass

COMMAND_MODES = ("auto", "shell", "single")


@dataclass(frozen=True)
class Config:
    host: str
    port: int = 22
    user: str = "root"
    password: str = ""
    key_file: str = ""
    poll_interval: float = 30.0
    listen_port: int = 9877
    log_level: str = "INFO"
    command_mode: str = "auto"
    tools_path: str = "/opt/lantiq/bin:/usr/bin:/usr/sbin:/bin:/sbin"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        host = env.get("GPON_HOST", "").strip()
        if not host:
            raise SystemExit("GPON_HOST is required")
        mode = env.get("GPON_COMMAND_MODE", "auto").strip().lower()
        if mode not in COMMAND_MODES:
            raise SystemExit(f"GPON_COMMAND_MODE must be one of {', '.join(COMMAND_MODES)}, not {mode!r}")
        return cls(
            host=host,
            port=int(env.get("GPON_PORT", "22")),
            user=env.get("GPON_USER", "root"),
            password=env.get("GPON_PASSWORD", ""),
            key_file=env.get("GPON_KEY_FILE", ""),
            poll_interval=float(env.get("POLL_INTERVAL", "30")),
            listen_port=int(env.get("LISTEN_PORT", "9877")),
            log_level=env.get("LOG_LEVEL", "INFO").upper(),
            command_mode=mode,
            tools_path=env.get("GPON_TOOLS_PATH", cls.tools_path),
        )
