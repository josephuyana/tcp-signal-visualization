# Models layer — interface for ViewModel

Two files, no Qt dependency, no GUI code (per MVVM requirement).

## `tcp_client.TcpClientModel`

Plain polling class — **not** a QObject, has no signals. Call `receive_data()`
repeatedly from a QTimer in the ViewModel (~16ms interval) to pull in new
packets; the model does not push data on its own.

```python
client = TcpClientModel(host="localhost", port=12345, sampling_rate=2000)

client.connect()                    # never raises; check client.status after
client.is_connected                 # bool
client.status                       # human-readable string for the status label

client.receive_data()               # call on a timer tick

client.has_data()                   # enough data for live plot?
client.get_window()                 # (x, y) — selected channel, rolling window
client.get_all_channels_window()    # (x, data[32, N]) — for "Plot All Channels"
client.set_selected_channel(3)      # raises ValueError if out of range

client.has_recording()              # any data for offline inspection?
client.get_full_recording()         # (x, data[32, total_samples]) — whole session

client.disconnect()                 # buffers are kept, so offline view still works
client.clear_buffers()              # call explicitly before starting a new session
```

**Sampling rate**: defaulted to 2000 Hz — confirm against the actual `.pkl`
recording's `device_information['sampling_frequency']` and update the
constructor argument if it differs.

## `signal_processor.process(data, mode, fs=2000)`

Stateless. Same function is used for both the live VisPy view and the
offline Matplotlib view, so results always match.

```python
process(data, "original")   # unchanged
process(data, "filtered")   # 10-500 Hz, 4th-order Butterworth, zero-phase
process(data, "rms")        # 100-sample moving RMS
```

Accepts either a 1D array (single channel, e.g. from `get_window()`) or a
2D array (`channels x samples`, e.g. from `get_all_channels_window()` /
`get_full_recording()`). Raises `ValueError` on an unknown mode string —
catch this in the ViewModel and show it as a status message.

Document these exact parameters (FS, 10-500 Hz, order 4, RMS window 100)
in the top-level project README as required — adjust here first if your
Ex2 implementation used different values, everything downstream will
follow automatically.

## Known gaps / things to confirm with the team

- **Sampling rate**: using 2000 Hz as a placeholder — needs confirming
  against the real recording.
- **Filter parameters**: using defaults consistent with typical EMG
  bandpass (10-500 Hz); replace with your actual Ex2 values if they were
  different.
- **Server pkl path**: the Ex5 server has a hardcoded Windows path to the
  recording file — needs to be made relative/configurable so teammates
  can run it locally.
