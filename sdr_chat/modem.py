from __future__ import annotations

from .config import RadioConfig


SYNC_WORD = bytes([0x55, 0xD3, 0x91, 0x7E])


class BPSKModem:
    def __init__(self, config: RadioConfig) -> None:
        self.config = config
        self._rx_samples: list[complex] = []
        self._header = (bytes([0x55]) * self.config.frame_preamble_bytes) + SYNC_WORD
        self._max_buffer_samples = max(
            self.config.samples_per_symbol * 8 * (self.config.frame_preamble_bytes + 512),
            self.config.rx_buffer_size * 4,
        )

    def modulate(self, payload: bytes) -> list[complex]:
        framed = self._frame_payload(payload)
        bits = self._bytes_to_bits(framed)
        samples_per_symbol = self.config.samples_per_symbol
        iq: list[complex] = []
        current_symbol = complex(0.7, 0.0)
        iq.extend(current_symbol for _ in range(samples_per_symbol))
        for bit in bits:
            if bit:
                current_symbol = -current_symbol
            symbol = current_symbol
            iq.extend(complex(symbol, 0.0) for _ in range(samples_per_symbol))
        return iq

    def demodulate(self, samples: list[complex]) -> list[bytes]:
        if samples:
            self._rx_samples.extend(samples)
        if len(self._rx_samples) > self._max_buffer_samples:
            self._rx_samples = self._rx_samples[-self._max_buffer_samples:]
        if len(self._rx_samples) < self.config.samples_per_symbol * len(self._header) * 8:
            return []
        frames: list[bytes] = []
        while True:
            detection = self._find_next_frame()
            if detection is None:
                break
            payload, consumed_samples = detection
            frames.append(payload)
            self._rx_samples = self._rx_samples[consumed_samples:]
        return frames

    def _frame_payload(self, payload: bytes) -> bytes:
        length = len(payload).to_bytes(2, "big")
        preamble = bytes([0x55]) * self.config.frame_preamble_bytes
        return preamble + SYNC_WORD + length + payload

    def _extract_frames(self, data: bytes) -> list[bytes]:
        frames: list[bytes] = []
        search_from = 0
        while True:
            sync_index = data.find(self._header, search_from)
            if sync_index < 0:
                break
            length_index = sync_index + len(self._header)
            if len(data) < length_index + 2:
                break
            payload_length = int.from_bytes(data[length_index:length_index + 2], "big")
            payload_start = length_index + 2
            payload_end = payload_start + payload_length
            if len(data) < payload_end:
                break
            frames.append(data[payload_start:payload_end])
            search_from = payload_end
        return frames

    def _find_next_frame(self) -> tuple[bytes, int] | None:
        candidates: list[tuple[int, int, bytes]] = []
        sps = self.config.samples_per_symbol
        min_header_symbols = len(self._header) * 8
        for phase in range(sps):
            symbols = self._slice_symbols(self._rx_samples, phase, sps)
            if len(symbols) < (min_header_symbols + 1):
                continue
            bits = self._differential_decode(symbols)
            data = self._bits_to_bytes(bits)
            frames = self._extract_frames(data)
            if not frames:
                continue
            header_index = data.find(self._header)
            if header_index < 0:
                continue
            first_payload = frames[0]
            consumed_bytes = header_index + len(self._header) + 2 + len(first_payload)
            consumed_symbols = 1 + (consumed_bytes * 8)
            consumed_samples = phase + (consumed_symbols * sps)
            if consumed_samples <= len(self._rx_samples):
                candidates.append((header_index, consumed_samples, first_payload))
        if not candidates:
            return None
        _, consumed_samples, payload = min(candidates, key=lambda item: item[0])
        consumed_samples = max(consumed_samples, sps)
        return payload, consumed_samples

    @staticmethod
    def _slice_symbols(samples: list[complex], phase: int, sps: int | None = None) -> list[complex]:
        if sps is None:
            raise ValueError("samples per symbol must be provided")
        usable = len(samples) - phase
        symbol_count = usable // sps
        if symbol_count <= 0:
            return []
        symbols: list[complex] = []
        for symbol_index in range(symbol_count):
            start = phase + (symbol_index * sps)
            chunk = samples[start:start + sps]
            symbols.append(sum(chunk) / sps)
        return symbols

    @staticmethod
    def _differential_decode(symbols: list[complex]) -> list[int]:
        bits: list[int] = []
        previous = symbols[0]
        for current in symbols[1:]:
            delta = previous.conjugate() * current
            bits.append(0 if delta.real >= 0 else 1)
            previous = current
        return bits

    @staticmethod
    def _bytes_to_bits(data: bytes) -> list[int]:
        bits: list[int] = []
        for byte in data:
            for bit_index in range(8):
                bits.append((byte >> bit_index) & 1)
        return bits

    @staticmethod
    def _bits_to_bytes(bits: list[int]) -> bytes:
        out = bytearray()
        current = 0
        for index, bit in enumerate(bits):
            current |= (bit & 1) << (index % 8)
            if index % 8 == 7:
                out.append(current)
                current = 0
        if len(bits) % 8:
            out.append(current)
        return bytes(out)
