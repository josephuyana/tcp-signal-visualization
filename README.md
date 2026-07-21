# TCP Signal Visualization
 
A PySide6 desktop application for live visualization and offline inspection
of TCP-streamed signal data (32 channels × 18 samples per packet, float64),
built with an MVVM architecture. Live plotting uses VisPy; offline inspection
uses Matplotlib.
 
## Group Information
 
- **Group name/number:** 12
- **Team members and responsibilities:**
  - **Shaheer Ahmed Khan** — Models (`models/`): TCP client, buffering, signal processing
  - **Joseph Uyana** — Views (`views/`): GUI, live plot widget, offline plot widget
  - **Enio Kazazi** — ViewModels (`viewmodels/`), integration, testing, and documentation
---
 
## Installation
 
This project uses `pyproject.toml` / `uv.lock`. If you have [`uv`](https://docs.astral.sh/uv/) installed:
 
```bash
uv sync
```
 
Otherwise, install dependencies with plain pip:
 
```bash
pip install pyside6 vispy numpy scipy matplotlib
```
 
## Running the Application
 
```bash
python main.py
```
 
(or `uv run main.py` if using `uv`)
 
A window titled **"TCP Signal Visualization"** will open.
 
---
 
## Connecting to the TCP Server
 
1. Start the provided Exercise 5 TCP server first, in a separate terminal.
2. In the app, enter the server's port number in the **Port** field (e.g. `12345`).
3. Click **Connect**.
   - On success, the status label turns green ("Connected") and the status
     bar shows the streaming sample rate.
   - On failure (wrong port, server not running, connection lost), an error
     message is shown and the status label stays "Disconnected" — the app
     does not crash.
4. Click **Disconnect** to stop streaming. Previously received data is kept
   in memory so it can still be inspected offline afterward.
---
 
## Using the Live Plot
 
- **Channel dropdown** — selects which of the 32 channels is shown in
  single-channel mode.
- **Mode dropdown** — switches between `Original`, `RMS`, and `Filtered`
  signal views. Applies to both live and offline plots identically, since
  both use the same underlying `signal_processor` functions.
- **Plot Selected Channel** — shows only the currently selected channel.
- **Plot All Channels** — shows all 32 channels simultaneously, stacked
  with a vertical offset per channel for readability.
The live plot updates automatically once connected; no manual refresh is
needed.
 
---
 
## Opening the Offline Plot
 
1. After streaming has stopped (or while data has been recorded), click
   **Open Offline Plot**.
2. A separate window opens showing a static Matplotlib plot of the full
   recorded session for the selected channel and mode.
3. Use that window's own **Channel** and **Mode** dropdowns to inspect
   different channels/modes — the plot updates immediately on selection,
   without needing to reconnect.
If no data has been recorded yet, an error message is shown instead of an
empty/broken plot.
 
---
 
## Signal Processing Parameters
 
Defined in `models/signal_processor.py`:
 
| Parameter | Value |
|---|---|
| Sampling rate (`fs`) | 2000 Hz *(confirm this matches your actual recording — adjust if different)* |
| Filter type | 4th-order Butterworth bandpass |
| Filter band | 10–500 Hz |
| RMS window | 100 samples (moving RMS) |
 
These are applied identically for both live (VisPy) and offline
(Matplotlib) views, since both call the same `process()` dispatcher.
 
---
 
## Project Structure (MVVM)
 
```text
tcp-signal-visualization/
├── main.py                        # Entry point: builds Model/ViewModel/View, wires them together
├── models/
│   ├── tcp_client.py               # TCP connection, packet reconstruction, buffering
│   ├── signal_buffer.py            # Standalone rolling/full-session buffer helper
│   └── signal_processor.py         # Stateless RMS / bandpass filter functions
├── viewmodels/
│   ├── backend_service.py          # QObject adapter: wraps TcpClientModel + signal_processor,
│   │                                #   exposes Qt signals (data_updated, connected, disconnected, error)
│   └── main_viewmodel.py            # Connects View widgets <-> BackendService; owns UI state
│                                     #   (e.g. single- vs all-channel display mode)
└── views/
    ├── main_window.py               # Main GUI: connection controls, channel/mode selectors, live plot host
    ├── vispy_live_view.py           # VisPy live plotting widget (single-channel + all-channel modes)
    └── offline_plot_window.py       # Matplotlib offline inspection window
```
 
**Dependency direction:** `views/` → `viewmodels/` → `models/`. Models
contain no Qt/GUI imports; Views never import from `models/` directly or
touch a socket — they only call methods on / connect to signals from their
ViewModel.
 
- **Models** (`tcp_client.py`, `signal_buffer.py`, `signal_processor.py`)
  are plain Python with no GUI framework dependency, so they can be tested
  or reused independently of the GUI.
- **ViewModels** (`backend_service.py`, `main_viewmodel.py`) hold Qt
  signals/state and translate raw Model data into a form the Views can
  bind to, and translate View actions (button clicks, dropdown changes)
  into calls on the Model layer.
- **Views** (`main_window.py`, `vispy_live_view.py`, `offline_plot_window.py`)
  contain only GUI code — no TCP handling, no signal processing logic.
---
 
## Error Handling
 
The application handles the following without crashing:
 
- Server not running / wrong port → status bar shows a clear error message
- Connection lost mid-stream → automatically disconnects and reports the
  reason
- No recorded data when opening the offline plot → error message shown
  instead of an empty/broken plot
- Invalid port input (non-numeric) → error message shown, connection
  attempt is not made