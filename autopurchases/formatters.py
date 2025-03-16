import logging


class AutopurchasesFormatter(logging.Formatter):
    default_time_format = "%d/%b/%Y %H:%M:%S"
    default_msec_format = False

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Красный фон
    }
    RESET = "\033[0m"

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname:<8}{self.RESET}"

        if self.uses_server_time() and not hasattr(record, "server_time"):
            record.server_time = self.formatTime(record, self.datefmt)

        return super().format(record)

    def uses_server_time(self):
        return self._fmt.find("{server_time}") >= 0
