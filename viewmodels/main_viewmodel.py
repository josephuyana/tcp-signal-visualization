from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from views.offline_plot_window import OfflinePlotWindow


class MainViewModel(QObject):
    """
    Frontend ViewModel:
    - Connects MainWindow controls to backend service API
    - Pushes processed data to VisPy view
    - Opens offline Matplotlib window

    IMPORTANT:
    Backend service is injected and must be implemented by teammate.
    Expected backend interface documented below.
    """

    status_changed = Signal(str)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self, main_window, backend_service):
        super().__init__()
        self.view = main_window
        self.backend = backend_service
        self.offline_window = None

        self._plot_all_mode = False
        self._current_channel = 0
        self._current_mode = "Original"

        self._wire_view_events()
        self._wire_backend_events()

        # Optional sampling rate from backend (if available)
        fs = getattr(self.backend, "sampling_rate", None)
        if fs:
            self.view.live_view.set_sampling_rate(fs)

    # ---------------- Wiring ----------------
    def _wire_view_events(self):
        self.view.connect_btn.clicked.connect(self.on_connect_clicked)
        self.view.disconnect_btn.clicked.connect(self.on_disconnect_clicked)

        self.view.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        self.view.mode_combo.currentTextChanged.connect(self.on_mode_changed)

        self.view.plot_all_btn.clicked.connect(self.on_plot_all_clicked)
        self.view.plot_single_btn.clicked.connect(self.on_plot_single_clicked)
        self.view.offline_btn.clicked.connect(self.on_open_offline_clicked)

        self.status_changed.connect(self.view.set_status)
        self.error_occurred.connect(self.view.show_error)
        self.connection_changed.connect(self.view.set_connected_ui)

    def _wire_backend_events(self):
        """
        Expected backend Qt signals (if present):
        - data_updated(np.ndarray): latest rolling buffer, shape (32, N)
        - connected()
        - disconnected()
        - error(str)
        """
        if hasattr(self.backend, "data_updated"):
            self.backend.data_updated.connect(self.on_backend_data_updated)
        if hasattr(self.backend, "connected"):
            self.backend.connected.connect(lambda: self._on_connected_state(True))
        if hasattr(self.backend, "disconnected"):
            self.backend.disconnected.connect(lambda: self._on_connected_state(False))
        if hasattr(self.backend, "error"):
            self.backend.error.connect(self._on_backend_error)

    # ---------------- Backend signal handlers ----------------
    @Slot(bool)
    def _on_connected_state(self, connected: bool):
        self.connection_changed.emit(connected)
        self.status_changed.emit("Connected." if connected else "Disconnected.")

    @Slot(str)
    def _on_backend_error(self, msg: str):
        self.error_occurred.emit(msg)
        self.status_changed.emit(msg)

    @Slot(np.ndarray)
    def on_backend_data_updated(self, buffer_2d: np.ndarray):
        """
        buffer_2d expected shape: (32, N), raw/original rolling buffer.
        VM requests processing from backend according to selected mode.
        """
        try:
            if self._plot_all_mode:
                plot_data = self._get_processed_all_channels(buffer_2d, self._current_mode)
                self.view.live_view.update_all(plot_data, offset_step=1500.0)
            else:
                y = self._get_processed_single_channel(buffer_2d, self._current_channel, self._current_mode)
                self.view.live_view.update_single(y)
        except Exception as exc:
            self.status_changed.emit(f"Live plot update failed: {exc}")

    # ---------------- UI events ----------------
    @Slot()
    def on_connect_clicked(self):
        port_text = self.view.port_input.text().strip()
        if not port_text:
            self.error_occurred.emit("Please enter a port.")
            return
        try:
            port = int(port_text)
        except ValueError:
            self.error_occurred.emit("Port must be an integer.")
            return

        try:
            # backend teammate should implement connect(port:int)
            self.backend.connect(port)
            self.status_changed.emit("Connecting...")
        except Exception as exc:
            self.error_occurred.emit(f"Could not connect: {exc}")

    @Slot()
    def on_disconnect_clicked(self):
        try:
            # backend teammate should implement disconnect()
            self.backend.disconnect()
            self.status_changed.emit("Disconnecting...")
        except Exception as exc:
            self.error_occurred.emit(f"Could not disconnect: {exc}")

    @Slot(int)
    def on_channel_changed(self, idx: int):
        self._current_channel = idx
        if not self._plot_all_mode:
            self.status_changed.emit(f"Selected Channel {idx + 1}")

    @Slot(str)
    def on_mode_changed(self, mode: str):
        self._current_mode = mode
        self.status_changed.emit(f"Mode: {mode}")

    @Slot()
    def on_plot_all_clicked(self):
        self._plot_all_mode = True
        self.view.live_view.show_all_channels()
        self.status_changed.emit("Plotting all channels.")

    @Slot()
    def on_plot_single_clicked(self):
        self._plot_all_mode = False
        self.view.live_view.show_single_channel()
        self.status_changed.emit(f"Plotting selected channel ({self._current_channel + 1}).")

    @Slot()
    def on_open_offline_clicked(self):
        # Optional backend helper: has_recorded_data() -> bool
        if hasattr(self.backend, "has_recorded_data"):
            try:
                if not self.backend.has_recorded_data():
                    self.error_occurred.emit("No data available for offline plotting.")
                    return
            except Exception:
                pass

        if self.offline_window is None:
            self.offline_window = OfflinePlotWindow()
            self.offline_window.set_data_provider(self._offline_data_provider)

        self.offline_window.show()
        self.offline_window.raise_()
        self.offline_window.activateWindow()

    # ---------------- Processing delegation ----------------
    def _get_processed_single_channel(self, buffer_2d: np.ndarray, ch: int, mode: str) -> np.ndarray:
        """
        Delegates signal mode logic to backend if possible.
        Fallback: raw signal.
        """
        arr = np.asarray(buffer_2d)
        y = arr[ch]

        # Preferred backend API:
        # process_channel(channel_1d: np.ndarray, mode: str) -> np.ndarray
        if hasattr(self.backend, "process_channel"):
            return np.asarray(self.backend.process_channel(y, mode))

        return y

    def _get_processed_all_channels(self, buffer_2d: np.ndarray, mode: str) -> np.ndarray:
        arr = np.asarray(buffer_2d)

        # Preferred backend API:
        # process_all(data_2d: np.ndarray, mode: str) -> np.ndarray
        if hasattr(self.backend, "process_all"):
            return np.asarray(self.backend.process_all(arr, mode))

        # Fallback: per-channel processing if available
        if hasattr(self.backend, "process_channel"):
            out = np.zeros_like(arr)
            for ch in range(arr.shape[0]):
                out[ch] = np.asarray(self.backend.process_channel(arr[ch], mode))
            return out

        return arr

    # ---------------- Offline provider ----------------
    def _offline_data_provider(self, channel_idx: int, mode: str):
        """
        Called by OfflinePlotWindow.
        Expected backend API:
        - get_recorded_data() -> np.ndarray shape (32, N)
        - sampling_rate attribute or get_sampling_rate()
        - optional processing helpers as above
        """
        if not hasattr(self.backend, "get_recorded_data"):
            raise RuntimeError("Backend does not provide recorded data API.")

        data = np.asarray(self.backend.get_recorded_data())
        if data.ndim != 2 or data.shape[0] != 32 or data.shape[1] == 0:
            raise RuntimeError("Recorded data is empty or invalid.")

        y = self._get_processed_single_channel(data, channel_idx, mode)

        fs = getattr(self.backend, "sampling_rate", None)
        if fs is None and hasattr(self.backend, "get_sampling_rate"):
            fs = self.backend.get_sampling_rate()
        if fs is None or fs <= 0:
            fs = 1.0

        t = np.arange(y.shape[0]) / float(fs)
        return t, y