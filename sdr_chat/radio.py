from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from .config import AppConfig


class RadioError(RuntimeError):
    pass


class BaseRadio(ABC):
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @abstractmethod
    def start(self, on_samples: Callable[[np.ndarray], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def transmit(self, iq_samples: list[complex]) -> None:
        raise NotImplementedError


@dataclass
class _MockChannel:
    listeners: list[queue.Queue]


_CHANNELS: dict[str, _MockChannel] = {}
_CHANNEL_LOCK = threading.Lock()


class MockRadio(BaseRadio):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self._queue: queue.Queue[list[complex]] = queue.Queue()
        self._running = False
        self._rx_thread: threading.Thread | None = None

    def start(self, on_samples: Callable[[list[complex]], None]) -> None:
        self._running = True
        with _CHANNEL_LOCK:
            channel = _CHANNELS.setdefault(self.config.mock_channel, _MockChannel(listeners=[]))
            channel.listeners.append(self._queue)

        def loop() -> None:
            while self._running:
                try:
                    samples = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                on_samples(samples)

        self._rx_thread = threading.Thread(target=loop, daemon=True)
        self._rx_thread.start()

    def stop(self) -> None:
        self._running = False
        with _CHANNEL_LOCK:
            channel = _CHANNELS.get(self.config.mock_channel)
            if channel and self._queue in channel.listeners:
                channel.listeners.remove(self._queue)
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)

    def transmit(self, iq_samples: list[complex]) -> None:
        with _CHANNEL_LOCK:
            listeners = list(_CHANNELS.get(self.config.mock_channel, _MockChannel([])).listeners)
        for listener in listeners:
            if listener is not self._queue:
                listener.put(list(iq_samples))


class PlutoRadio(BaseRadio):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self._pluto = None
        self._running = False
        self._rx_thread: threading.Thread | None = None

    def start(self, on_samples: Callable[[list[complex]], None]) -> None:
        try:
            import adi
        except ImportError as exc:
            raise RadioError("pyadi-iio is required for Pluto operation") from exc

        self._pluto = adi.Pluto(self.config.pluto_uri)
        self._pluto.sample_rate = int(self.config.radio.sample_rate)
        self._pluto.rx_lo = int(self.config.radio.center_freq)
        self._pluto.tx_lo = int(self.config.radio.center_freq)
        self._pluto.rx_rf_bandwidth = int(self.config.radio.sample_rate)
        self._pluto.tx_rf_bandwidth = int(self.config.radio.sample_rate)
        self._pluto.rx_hardwaregain_chan0 = float(self.config.radio.rx_gain)
        self._pluto.tx_hardwaregain_chan0 = float(self.config.radio.tx_gain)
        self._pluto.rx_buffer_size = int(self.config.radio.rx_buffer_size)
        self._pluto.gain_control_mode_chan0 = "manual"

        self._running = True

        def loop() -> None:
            while self._running:
                samples = self._pluto.rx()
                if samples is None:
                    time.sleep(0.02)
                    continue
                on_samples(list(samples))

        self._rx_thread = threading.Thread(target=loop, daemon=True)
        self._rx_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)
        self._pluto = None

    def transmit(self, iq_samples: list[complex]) -> None:
        if self._pluto is None:
            raise RadioError("Pluto radio not started")
        clipped = [
            complex(
                max(-1.0, min(1.0, sample.real)),
                max(-1.0, min(1.0, sample.imag)),
            )
            for sample in iq_samples
        ]
        self._pluto.tx(clipped)


def build_radio(config: AppConfig) -> BaseRadio:
    if config.radio_kind == "mock":
        return MockRadio(config)
    if config.radio_kind == "pluto":
        return PlutoRadio(config)
    raise RadioError(f"Unsupported radio kind: {config.radio_kind}")
