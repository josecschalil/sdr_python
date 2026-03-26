from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RadioConfig:
    center_freq: int = 435_000_000
    sample_rate: int = 1_000_000
    symbol_rate: int = 10_000
    samples_per_symbol: int = 20
    intermediate_freq: int = 100_000
    tx_gain: float = -10.0
    rx_gain: float = 30.0
    rx_buffer_size: int = 131072
    frame_preamble_bytes: int = 32


@dataclass(slots=True)
class AppConfig:
    callsign: str
    peer_callsign: str
    radio_kind: str = "mock"
    mock_channel: str = "default"
    pluto_uri: str = "ip:192.168.2.1"
    initial_tx_owner: str = ""
    radio: RadioConfig = field(default_factory=RadioConfig)
