import logging

from prometheus_client import start_http_server

from . import __version__
from .config import Config
from .poller import Poller

log = logging.getLogger("lantiq_onu_exporter")


def main():
    config = Config.from_env()
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(message)s")
    start_http_server(config.listen_port)
    log.info("lantiq-onu-exporter %s listening on :%d, polling %s@%s:%d every %ss", __version__,
             config.listen_port, config.user, config.host, config.port, config.poll_interval)
    Poller(config).run_forever()


if __name__ == "__main__":
    main()
