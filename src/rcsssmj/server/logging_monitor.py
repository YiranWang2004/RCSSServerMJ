from io import TextIOWrapper

from rcsssmj.server.remote_monitor import RSMPMonitor


class LoggingMonitor(RSMPMonitor):
    """Logging monitor that writes RSMP messages to a file."""

    def __init__(self, file: TextIOWrapper, update_interval: int = 1) -> None:
        """Construct a new logging monitor client.

        Parameter
        ---------
        file: TextIOWrapper
            The log file.

        update_interval: int
            The update interval of the monitor.
        """

        super().__init__(update_interval=update_interval)

        self._file: TextIOWrapper = file
        """The log file."""

    def shutdown(self) -> None:
        super().shutdown()
        self._file.close()

    def _emit_message(self, message: str) -> None:
        self._file.write(message + '\n')

    def __str__(self) -> str:
        return f'Logger @ {self._file}'

    def __repr__(self) -> str:
        return f'Logger ({self._file.__repr__()})'
