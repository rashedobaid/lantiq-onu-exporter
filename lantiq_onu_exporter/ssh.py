import re
import socket
import time

import paramiko

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-Z0-9]|\r")
CONNECT_TIMEOUT = 10


class Connection:
    def __init__(self, config):
        self.config = config
        self.client = None

    @property
    def active(self):
        transport = self.client.get_transport() if self.client else None
        return bool(transport and transport.is_active())

    def open(self):
        config = self.config
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if config.password or config.key_file:
            client.connect(
                config.host, port=config.port, username=config.user, password=config.password or None,
                key_filename=config.key_file or None, look_for_keys=False, allow_agent=False,
                timeout=CONNECT_TIMEOUT, banner_timeout=CONNECT_TIMEOUT, auth_timeout=CONNECT_TIMEOUT,
            )
        else:
            transport = paramiko.Transport(socket.create_connection((config.host, config.port), timeout=CONNECT_TIMEOUT))
            transport.banner_timeout = CONNECT_TIMEOUT
            transport.connect()
            try:
                transport.auth_none(config.user)
            except paramiko.BadAuthenticationType:
                transport.auth_password(config.user, "")
            client._transport = transport
        self.client = client

    def close(self):
        if self.client:
            self.client.close()
        self.client = None

    def run(self, command, timeout=20, pty=False, stop=None, limit=262144):
        channel = self.client.get_transport().open_session(timeout=CONNECT_TIMEOUT)
        if pty:
            channel.get_pty(width=200, height=100)
        channel.settimeout(timeout)
        channel.exec_command(command)
        data = b""
        deadline = time.monotonic() + timeout
        try:
            while len(data) < limit and time.monotonic() < deadline:
                chunk = channel.recv(65536)
                if not chunk:
                    break
                data += chunk
                if stop and "\n" in self._clean(data.decode(errors="ignore"), pty).partition(stop)[2]:
                    break
        except socket.timeout:
            pass
        finally:
            channel.close()
        return self._clean(data.decode(errors="replace"), pty)

    @staticmethod
    def _clean(text, pty):
        return ANSI.sub("\n", text) if pty else text
