import pytest

from lantiq_onu_exporter.config import Config


def test_defaults():
    config = Config.from_env({"GPON_HOST": "192.168.1.10"})
    assert (config.port, config.user, config.password, config.command_mode) == (22, "root", "", "auto")
    assert config.poll_interval == 30
    assert config.tools_path.startswith("/opt/lantiq/bin")


def test_overrides():
    config = Config.from_env(
        {
            "GPON_HOST": "10.0.0.2",
            "GPON_USER": "ONTUSER",
            "GPON_PASSWORD": "secret",
            "POLL_INTERVAL": "10",
            "GPON_COMMAND_MODE": "Single",
        }
    )
    assert (config.user, config.password, config.poll_interval, config.command_mode) == (
        "ONTUSER",
        "secret",
        10,
        "single",
    )


def test_host_is_required():
    with pytest.raises(SystemExit):
        Config.from_env({})


def test_invalid_command_mode():
    with pytest.raises(SystemExit):
        Config.from_env({"GPON_HOST": "x", "GPON_COMMAND_MODE": "fast"})
