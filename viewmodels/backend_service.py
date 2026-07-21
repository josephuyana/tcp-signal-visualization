"""
backend_service.py

QObject adapter that bridges the plain-Python TCP model layer with the
Qt-based ViewModel.

Why this class exists:
    The TcpClientModel (models/tcp_client.py) is intentionally a plain
    Python class with no Qt dependency — per MVVM, the Model should not
    contain GUI code. But the ViewModel (viewmodels/main_viewmodel.py)
    expects a QObject that emits Qt signals (data_updated, connected,
    disconnected, error).

    BackendService wraps TcpClientModel and signal_processor behind the
    exact interface the ViewModel already uses, so the frontend code does
    not need to change at all.

Polling architecture:
    A QTimer fires every ~16 ms. On each tick, we call
    tcp_client.receive_data() to pull any new bytes off the non-blocking
    socket, then emit the rolling buffer to the ViewModel. This matches
    the poll/render split used throughout the course exercises.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer

from models.tcp_client import TcpClientModel
from models import signal_processor


class BackendService(QObject):
    """
    Qt-signal-based backend service expected by MainViewModel.

    Emitted signals
    ---------------
    data_updated(np.ndarray)
        The current rolling buffer, shape (32, N). Emitted on every
        timer tick that has data.
    connected()
        Emitted after a successful TCP connection.
    disconnected()
        Emitted after the connection is closed (user or server side).
    error(str)
        Emitted when something goes wrong (bad port, connection lost, …).
    """

    data_updated = Signal(object)   # np.ndarray (32, N)
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    # Sampling rate of the EMG recording streamed by the Ex5 server.
    # Adjust if your .pkl recording uses a different frequency.
    SAMPLING_RATE = 2000

    def __init__(self, parent=None):
        super().__init__(parent)

        # The underlying plain-Python TCP model (no Qt dependency).
        self._tcp = TcpClientModel(
            host="localhost",
            port=12345,
            sampling_rate=self.SAMPLING_RATE,
        )

        # Expose sampling_rate as a simple attribute so the ViewModel /
        # VisPy view can read it (they do: getattr(backend, "sampling_rate")).
        self.sampling_rate = float(self.SAMPLING_RATE)

        # Poll timer: calls _tick() every ~16 ms (~60 FPS).
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        # Track the previous connection state so we can emit connected /
        # disconnected signals exactly once on transitions.
        self._was_connected = False

    # ------------------------------------------------------------------
    # Public API expected by the ViewModel
    # ------------------------------------------------------------------

    def connect(self, port: int):
        """
        Connect to the TCP server at localhost:<port>.

        Does not raise — sets the internal status string and emits
        error() if the connection fails, or connected() on success.
        """
        if port <= 0 or port > 65535:
            self.error.emit(f"Invalid port: {port}")
            return

        # Update port on the underlying model before connecting.
        self._tcp.port = port

        # Clear previous session data so the offline plot starts fresh.
        self._tcp.clear_buffers()

        self._tcp.connect()

        if self._tcp.is_connected:
            self._was_connected = True
            self.connected.emit()
            self._timer.start()
        else:
            # connect() failed — status string has the reason.
            self.error.emit(self._tcp.status)

    def disconnect(self):
        """
        Disconnect from the TCP server.

        The recorded data is kept so the user can still open the offline
        Matplotlib plot after disconnecting.
        """
        self._timer.stop()
        self._tcp.disconnect()

        if self._was_connected:
            self._was_connected = False
            self.disconnected.emit()

    def has_recorded_data(self) -> bool:
        """True if there is any data available for offline plotting."""
        return self._tcp.has_recording()

    def get_recorded_data(self) -> np.ndarray:
        """
        Return the full recording as a (32, total_samples) array.

        Used by the ViewModel's offline data provider.
        """
        _x, data = self._tcp.get_full_recording()
        return data

    def process_channel(self, channel_1d: np.ndarray, mode: str) -> np.ndarray:
        """
        Apply the requested signal processing mode to a single channel.

        Handles the case mismatch between the frontend ("Original") and
        signal_processor ("original") internally.
        """
        return signal_processor.process(
            np.asarray(channel_1d, dtype=np.float64),
            mode=mode.lower(),
            fs=int(self.sampling_rate),
        )

    def process_all(self, data_2d: np.ndarray, mode: str) -> np.ndarray:
        """
        Apply the requested signal processing mode to all 32 channels.

        data_2d shape: (32, N).
        """
        return signal_processor.process(
            np.asarray(data_2d, dtype=np.float64),
            mode=mode.lower(),
            fs=int(self.sampling_rate),
        )

    # ------------------------------------------------------------------
    # Internal timer callback
    # ------------------------------------------------------------------

    def _tick(self):
        """
        Called every ~16 ms by the QTimer.

        1. Pull any new bytes off the TCP socket.
        2. If the connection was lost mid-stream, emit disconnected/error.
        3. If data is available, emit the rolling buffer.
        """
        if not self._tcp.is_connected:
            # Connection was lost between ticks (server closed / reset).
            self._timer.stop()
            if self._was_connected:
                self._was_connected = False
                self.error.emit(self._tcp.status)
                self.disconnected.emit()
            return

        self._tcp.receive_data()

        # Re-check after receive_data — it may have called disconnect()
        # internally if the server closed the connection.
        if not self._tcp.is_connected:
            self._timer.stop()
            if self._was_connected:
                self._was_connected = False
                self.error.emit(self._tcp.status)
                self.disconnected.emit()
            return

        if self._tcp.has_data():
            self.data_updated.emit(self._tcp.data_buffer.copy())
