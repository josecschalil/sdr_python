# SDR Packet Radio Chat

Python implementation of a half-duplex packet radio messaging system designed for two computers using ADALM-Pluto SDR devices.

## Features

- AX.25-inspired packet framing with CRC validation
- Half-duplex link arbitration using `REQUEST`, `GRANT`, `RELEASE`, and `ACK`
- BPSK modem pipeline for converting packets to IQ samples and back
- Pluto SDR backend for over-the-air operation
- Mock loopback backend for local development without hardware
- Tkinter GUI for link control, messaging, and live status

## Project layout

- `main.py`: application entrypoint
- `sdr_chat/config.py`: runtime configuration
- `sdr_chat/ax25.py`: packet framing and CRC
- `sdr_chat/packets.py`: control/data packet model
- `sdr_chat/modem.py`: BPSK modulation and demodulation
- `sdr_chat/radio.py`: radio abstraction, mock transport, Pluto backend
- `sdr_chat/link.py`: half-duplex link manager
- `sdr_chat/gui.py`: desktop GUI

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Start the app in mock mode:

```powershell
python main.py --callsign N0CALL-1 --peer N0CALL-2 --radio mock --mock-channel demo
```

Open a second instance with the callsigns swapped:

```powershell
python main.py --callsign N0CALL-2 --peer N0CALL-1 --radio mock --mock-channel demo
```

## Pluto usage

Example:

```powershell
python main.py --callsign N0CALL-1 --peer N0CALL-2 --radio pluto --uri ip:192.168.2.1 --center-freq 435000000
```

Notes:

- Both stations must use the same center frequency, sample rate, symbol rate, and samples per symbol.
- Gain, frequency offset, and threshold tuning may be required for reliable operation.
- The Pluto backend expects `pyadi-iio` and accessible ADALM-Pluto hardware.
- Mock mode does not require Pluto-specific dependencies.

## Workflow

1. Click `Start Link` to begin RX processing.
2. Click `Request TX` to ask the remote station for transmit permission.
3. Once granted, send one or more messages.
4. Click `Release TX` to hand the channel back.

## Limitations

- The modem is intentionally simple for educational clarity rather than maximum RF robustness.
- Real deployments may need filtering, timing recovery, carrier recovery, and better framing preambles.
- This implementation uses an AX.25-inspired UI frame format, not a full TNC stack.
