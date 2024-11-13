import logging
import socket
from logging.handlers import SysLogHandler


class ContextFilter(logging.Filter):
    hostname = socket.gethostname()

    def filter(self, record):
        record.hostname = ContextFilter.hostname
        return True


def get_logger(url, port, app_name=""):
    fmt = f'%(asctime)s {app_name}: %(message)s'
    formatter = logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()

    try:
        syslog = SysLogHandler(address=(url, port))
        syslog.addFilter(ContextFilter())
        syslog.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(syslog)
    except OSError as e:
        print(f"OS error: {e} with {url}:{port}")

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger
