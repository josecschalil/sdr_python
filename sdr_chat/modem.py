from __future__ import annotations

import math

from .config import RadioConfig


SYNC_WORD = bytes([0x55, 0xD3, 0x91, 0x7E])


class BPSKModem:
    def __init__(self, config: RadioConfig) -> None:
        self.config = config
        self._rx_samples: list[complex] = []
        self._header = (bytes([0x55]) * self.config.frame_preamble_bytes) + SYNC_WORD
        self._rx_mix_index = 0
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
        iq.extend(self._apply_subcarrier(current_symbol, index) for index in range(samples_per_symbol))
        sample_index = samples_per_symbol
        for bit in bits:
            if bit:
                current_symbol = -current_symbol
            symbol = current_symbol
            for _ in range(samples_per_symbol):
                iq.append(self._apply_subcarrier(symbol, sample_index))
                sample_index += 1
        return iq

    def demodulate(self, samples: list[complex]) -> list[bytes]:
        if samples:
            self._rx_samples.extend(self._mix_down(samples))
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

    def _find_next_frame(self) -> tuple[bytes, int] | None:
        candidates: list[tuple[int, int, bytes]] = []
        sps = self.config.samples_per_symbol
        header_bits = self._bytes_to_bits(self._header)
        header_str = "".join(str(b) for b in header_bits)
        min_header_symbols = len(header_bits)
        
        for phase in range(sps):
            symbols = self._slice_symbols(self._rx_samples, phase, sps)
            if len(symbols) < (min_header_symbols + 1):
                continue
            bits = self._differential_decode(symbols)
            bits_str = "".join(str(b) for b in bits)
            
            bit_search_start = 0
            while True:
                header_bit_idx = bits_str.find(header_str, bit_search_start)
                if header_bit_idx < 0:
                    break
                
                length_bit_idx = header_bit_idx + len(header_bits)
                if len(bits) < length_bit_idx + 16:
                    break
                    
                length_bits = bits[length_bit_idx : length_bit_idx + 16]
                length_bytes = self._bits_to_bytes(length_bits)
                payload_length = int.from_bytes(length_bytes, "big")
                
                payload_start_bit = length_bit_idx + 16
                payload_end_bit = payload_start_bit + (payload_length * 8)
                
                if len(bits) < payload_end_bit:
                    break
                    
                payload_bits = bits[payload_start_bit:payload_end_bit]
                payload_bytes = self._bits_to_bytes(payload_bits)
                
                consumed_bits = payload_end_bit
                consumed_symbols = 1 + consumed_bits
                consumed_samples = phase + (consumed_symbols * sps)
                
                if consumed_samples <= len(self._rx_samples):
                    candidates.append((header_bit_idx, consumed_samples, payload_bytes))
                
                bit_search_start = payload_end_bit
                
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

    def _apply_subcarrier(self, symbol: complex, sample_index: int) -> complex:
        angle = 2.0 * math.pi * self.config.intermediate_freq * sample_index / self.config.sample_rate
        carrier = complex(math.cos(angle), math.sin(angle))
        return symbol * carrier

    def _mix_down(self, samples: list[complex]) -> list[complex]:
        mixed: list[complex] = []
        for sample in samples:
            angle = -2.0 * math.pi * self.config.intermediate_freq * self._rx_mix_index / self.config.sample_rate
            carrier = complex(math.cos(angle), math.sin(angle))
            mixed.append(sample * carrier)
            self._rx_mix_index += 1
        return mixed

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
