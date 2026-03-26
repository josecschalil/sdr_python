from __future__ import annotations

from .config import RadioConfig


SYNC_WORD = bytes([0x55, 0xD3, 0x91, 0x7E])


class BPSKModem:
    def __init__(self, config: RadioConfig) -> None:
        self.config = config

    def modulate(self, payload: bytes) -> list[complex]:
        framed = self._frame_payload(payload)
        bits = self._bytes_to_bits(framed)
        samples_per_symbol = self.config.samples_per_symbol
        iq: list[complex] = []
        for bit in bits:
            symbol = 0.7 if bit else -0.7
            iq.extend(complex(symbol, 0.0) for _ in range(samples_per_symbol))
        return iq

    def demodulate(self, samples: list[complex]) -> list[bytes]:
        if len(samples) < self.config.samples_per_symbol * 16:
            return []
        symbols = self._slice_symbols(samples)
        bits = [1 if symbol.real >= 0 else 0 for symbol in symbols]
        data = self._bits_to_bytes(bits)
        return self._extract_frames(data)

    def _slice_symbols(self, samples: list[complex]) -> list[complex]:
        sps = self.config.samples_per_symbol
        usable = len(samples) - (len(samples) % sps)
        if usable <= 0:
            return []
        symbols: list[complex] = []
        for index in range(0, usable, sps):
            chunk = samples[index:index + sps]
            symbols.append(sum(chunk) / sps)
        return symbols

    def _frame_payload(self, payload: bytes) -> bytes:
        length = len(payload).to_bytes(2, "big")
        preamble = bytes([0x55]) * self.config.frame_preamble_bytes
        return preamble + SYNC_WORD + length + payload

    def _extract_frames(self, data: bytes) -> list[bytes]:
        frames: list[bytes] = []
        search_from = 0
        while True:
            sync_index = data.find(SYNC_WORD, search_from)
            if sync_index < 0:
                break
            length_index = sync_index + len(SYNC_WORD)
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
