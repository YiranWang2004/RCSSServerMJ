import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum
from queue import Queue
from threading import Thread, current_thread

from rcsssmj.server.command_parser import CommandParser
from rcsssmj.server.communication.connection import PConnection
from rcsssmj.sim.commands import MonitorCommand
from rcsssmj.sim.state_info import SceneGraph, SimStateInformation, TransformNode

logger = logging.getLogger(__name__)


class RemoteMonitorState(Enum):
    """Simulation monitor state enum."""

    ACTIVE = 'active'
    """The monitor is actively receiving simulation state messages and can issue commands."""

    SHUTDOWN = 'shutdown'
    """The monitor has been shut down and is waiting to be removed from the simulation server."""


class SimMonitor(ABC):
    """Base class for simulation monitors, monitoring and interacting with the simulation."""

    def __init__(self, update_interval: int = 1):
        """Construct a new simulation monitor."""

        super().__init__()

        self._state: RemoteMonitorState = RemoteMonitorState.ACTIVE
        """The current simulation monitor state."""

        self.update_interval: int = update_interval
        """The update interval of the monitor."""

        self._command_queue: Queue[MonitorCommand] = Queue()
        """The monitor command queue."""

    @property
    def state(self) -> RemoteMonitorState:
        """The current monitor state."""

        return self._state

    @property
    def command_queue(self) -> Queue[MonitorCommand]:
        """The command queue associated with this monitor."""

        return self._command_queue

    def shutdown(self) -> None:
        """Stop the monitor."""

        self._state = RemoteMonitorState.SHUTDOWN

    def join(self) -> None:
        """Wait until the monitor listener thread terminates (if existing)."""

    @abstractmethod
    def update(self, state_info: Sequence[SimStateInformation], frame_id: int, last_recompilation: int) -> None:
        """Update the monitor state.

        Parameter
        ---------
        state_info: Sequence[SimStateInformation]
            The list of simulation state information.

        frame_id: int
            The current simulation frame id.

        last_recompilation: int
            The frame number of the last model recompilation.
        """


class RSMPMonitor(SimMonitor):
    """Simulation monitor that emits RSMP."""

    def __init__(self) -> None:
        """Construct a new remote simulation monitor client.

        Parameter
        ---------
        update_interval: int
            The update interval of the monitor.
        """

        super().__init__(update_interval=2)

        self._node_cache: TransformNode = TransformNode()
        """The transform node cache."""

        self._last_recompilation: int = -1
        """The frame number of the last model recompilation."""

        self._did_recompile: bool = False
        """If the model was recompiled since the last update."""

        self._need_full_state: bool = True
        """If a full state update is required."""

        self._allow_cached_scene_graph: bool = False
        """If using a cached scene graph is allowed."""

    def update(self, state_info: Sequence[SimStateInformation], frame_id: int, last_recompilation: int) -> None:
        self._did_recompile |= last_recompilation != self._last_recompilation
        self._last_recompilation = last_recompilation
        if self._did_recompile:
            self._need_full_state = True

        if frame_id % 250 == 0:
            self._need_full_state = True
            # Allow using the cached scene graph from now on.
            # In this frame, every monitor will emit a frame and thus the diff is also always the same.
            # This only works if the update_interval is the same for each RSMPMonitor.
            # Otherwise, we cannot use the caching mechanism.
            self._allow_cached_scene_graph = True

        if frame_id % self.update_interval != 0:
            return

        if self._need_full_state:
            self._node_cache.reset()

        # RSMP: Robot Simulation Monitor Protocol
        # Major and minor version number of the protocol follows.
        # The sub components are versioned separately.
        # If just the inner structure of a sub component changed, the RSMP version number does not need to change.
        msg = "((RSMP 1 0)"
        for si in state_info:
            if isinstance(si, SceneGraph):
                msg += si.to_sexp(self._need_full_state, node_cache=self._node_cache, allow_cached=self._allow_cached_scene_graph)
            else:
                msg += si.to_sexp(self._need_full_state)
        msg += ")"
        self._emit_message(msg)
        self._need_full_state = False
        self._did_recompile = False

    @abstractmethod
    def _emit_message(self, message: str) -> None:
        """Emit an RSMP message.

        Parameter
        ---------
        message: str
            The RSMP message to emit.
        """


class RemoteMonitor(RSMPMonitor):
    """Remote simulation monitor, utilizing a message based connection to communicate with an external monitor process."""

    def __init__(self, conn: PConnection, parser: CommandParser) -> None:
        """Construct a new remote simulation monitor client.

        Parameter
        ---------
        conn: PConnection
            The monitor connection.

        parser: CommandParser
            The monitor command parser instance.
        """

        super().__init__()

        self._conn: PConnection = conn
        """The monitor connection for exchanging state and command messages."""

        self._parser: CommandParser = parser
        """Parser for parsing incoming command messages."""

        self._monitor_thread: Thread | None = None
        """The thread, running the monitor receive loop (if existing)."""

    def shutdown(self) -> None:
        super().shutdown()
        self._conn.shutdown()

    def join(self) -> None:
        if self._monitor_thread is not None:
            self._monitor_thread.join()

    def _emit_message(self, message: str) -> None:
        try:
            self._conn.send_message(message.encode('utf-8'))
        except BrokenPipeError:
            self.shutdown()

    def run(self) -> None:
        """Continuously receive and process monitor commands.

        Note: This method is blocking until the monitor connection has been closed and thus supposed to be executed in a separate thread.
        """

        if self._monitor_thread is not None:
            logger.warning('run()-method of remote monitor %s called multiple times! Joining existing monitor thread.', self)
            self._monitor_thread.join()
            return

        # fetch monitor thread instance
        self._monitor_thread = current_thread()

        while True:
            # receive next command message
            try:
                msg = self._conn.receive_message()
            except ConnectionError:
                logger.debug('Monitor connection %s closed!', self._conn)
                break

            # parse commands
            commands = self._parser.parse(msg)

            # forward commands
            for command in commands:
                self._command_queue.put(command)

        self._state = RemoteMonitorState.SHUTDOWN
        self._conn.close()

        logger.debug('Monitor thread for %s finished!', self._conn)

    def __str__(self) -> str:
        return f'RemoteMonitor @ {self._conn}'

    def __repr__(self) -> str:
        return f'RemoteMonitor({self._conn.__repr__()})'
