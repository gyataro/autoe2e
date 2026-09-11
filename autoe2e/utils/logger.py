import logging
import sys
from pathlib import Path


class RunLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("autoe2e")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        self._file_handler: logging.FileHandler | None = None

        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
            handler.close()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(console_handler)

    def configure_run(self, path: Path) -> None:
        self.close_run()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handler = logging.FileHandler(path, mode="a", encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        self._logger.addHandler(self._file_handler)

    def close_run(self) -> None:
        if self._file_handler is None:
            return
        self._logger.removeHandler(self._file_handler)
        self._file_handler.close()
        self._file_handler = None

    def debug(self, message: object) -> None:
        self._logger.debug(message)

    def info(self, message: object) -> None:
        self._logger.info(message)

    def warning(self, message: object) -> None:
        self._logger.warning(message)

    def warn(self, message: object) -> None:
        self.warning(message)

    def error(self, message: object) -> None:
        self._logger.error(message)

    def exception(self, message: object) -> None:
        self._logger.exception(message)

    def set_level(self, level: int) -> None:
        self._logger.setLevel(level)


logger = RunLogger()
