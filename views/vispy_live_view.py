from __future__ import annotations
 
import numpy as np
from vispy import scene
 
 
class VisPyLiveView(scene.SceneCanvas):
    """
    Live VisPy plotting widget for:
    - single selected channel
    - all channels with vertical offsets
 
    Frontend-only: expects already prepared numpy arrays from ViewModel.
    """
 
    def __init__(self, parent=None):
        super().__init__(keys=None, parent=parent, bgcolor="white", size=(1000, 600))
        self.unfreeze()
 
        self._view = self.central_widget.add_view()
        self._view.camera = scene.PanZoomCamera()
        self._view.camera.set_range()
 
        # Axis widget container
        self._grid = self.central_widget.add_grid(margin=8)
        self._grid.add_widget(self._view, row=0, col=1)
 
        self._x_axis = scene.AxisWidget(
            orientation="bottom",
            axis_label="Time (s)",
            axis_font_size=10,
            tick_font_size=8,
        )
        self._x_axis.height_max = 60
        self._grid.add_widget(self._x_axis, row=1, col=1)
        self._x_axis.link_view(self._view)
 
        self._y_axis = scene.AxisWidget(
            orientation="left",
            axis_label="Amplitude",
            axis_font_size=10,
            tick_font_size=8,
        )
        self._y_axis.width_max = 80
        self._grid.add_widget(self._y_axis, row=0, col=0)
        self._y_axis.link_view(self._view)
 
        # One line for single-channel mode
        self._single_line = scene.Line(
            pos=np.zeros((2, 2), dtype=np.float32),
            color=(0.1, 0.4, 0.9, 1.0),
            width=2.0,
            parent=self._view.scene,
            method="gl",
        )
 
        # 32 lines for all-channels mode
        self._all_lines = []
        for _ in range(32):
            line = scene.Line(
                pos=np.zeros((2, 2), dtype=np.float32),
                color=(0.15, 0.15, 0.15, 0.85),
                width=1.2,
                parent=self._view.scene,
                method="gl",
            )
            line.visible = False
            self._all_lines.append(line)
 
        self._mode_all_channels = False
        self._sampling_rate = 1.0  # set by VM if known
        self.freeze()
 
    # ---------------- Public API for ViewModel ----------------
    def set_sampling_rate(self, fs: float):
        if fs and fs > 0:
            self._sampling_rate = float(fs)
 
    def show_single_channel(self):
        self._mode_all_channels = False
        self._single_line.visible = True
        for ln in self._all_lines:
            ln.visible = False
        self.update()
 
    def show_all_channels(self):
        self._mode_all_channels = True
        self._single_line.visible = False
        for ln in self._all_lines:
            ln.visible = True
        self.update()
 
    def update_single(self, y: np.ndarray):
        """
        y shape: (N,)
        """
        if y is None or y.size == 0:
            return
 
        y = np.asarray(y, dtype=np.float32).ravel()
        n = y.shape[0]
        x = (np.arange(n, dtype=np.float32) / np.float32(self._sampling_rate))
        pos = np.column_stack((x, y))
        self._single_line.set_data(pos=pos)
 
        ymin = float(np.min(y))
        ymax = float(np.max(y))
        if np.isclose(ymin, ymax):
            ymin -= 1.0
            ymax += 1.0
 
        self._view.camera.set_range(
            x=(float(x[0]), float(x[-1]) if n > 1 else 1.0),
            y=(ymin, ymax),
            margin=0.02,
        )
        self.update()
 
    def update_all(self, data_2d: np.ndarray, offset_step: float = 1.0):
        """
        data_2d shape: (32, N)
        Each channel gets vertical offset: ch * offset_step
        """
        if data_2d is None:
            return
        arr = np.asarray(data_2d, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != 32 or arr.shape[1] == 0:
            return
 
        n = arr.shape[1]
        x = (np.arange(n, dtype=np.float32) / np.float32(self._sampling_rate))
 
        global_min = np.inf
        global_max = -np.inf
 
        for ch in range(32):
            y = arr[ch] + (ch * offset_step)
            pos = np.column_stack((x, y))
            self._all_lines[ch].set_data(pos=pos)
 
            local_min = float(np.min(y))
            local_max = float(np.max(y))
            if local_min < global_min:
                global_min = local_min
            if local_max > global_max:
                global_max = local_max
 
        if not np.isfinite(global_min) or not np.isfinite(global_max) or np.isclose(global_min, global_max):
            global_min, global_max = -1.0, 1.0
 
        self._view.camera.set_range(
            x=(float(x[0]), float(x[-1]) if n > 1 else 1.0),
            y=(global_min, global_max),
            margin=0.02,
        )
        self.update()