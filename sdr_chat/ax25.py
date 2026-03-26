from __future__ import annotations

from dataclasses import dataclass

from .packets import LinkPacket

FLAG = 0x7E
CONTROL_UI = 0x03
PID_NO_LAYER3 = 0xF0


def _normalize_callsign(callsign: str) -> tuple[str, int]:
    if "-" in callsign:
        base, ssid = callsign.split("-", 1)
        return base.upper()[:6], int(ssid)
    return callsign.upper()[:6], 0


def encode_address(callsign: str, last: bool) -> bytes:
    base, ssid = _normalize_callsign(callsign)
    padded = base.ljust(6)
    address = bytearray((ord(char) << 1) for char in padded)
    ssid_byte = 0x60 | ((ssid & 0x0F) << 1)
    if last:
        ssid_byte |= 0x01
    address.append(ssid_byte)
    return bytes(address)


def decode_address(address: bytes) -> str:
    base = "".join(chr(byte >> 1) for byte in address[:6]).strip()
    ssid = (address[6] >> 1) & 0x0F
    return f"{base}-{ssid}" if ssid else base


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF


@dataclass(slots=True)
class AX25Frame:
    destination: str
    source: str
    information: bytes

    def encode(self) -> bytes:
        core = bytearray()
        core.extend(encode_address(self.destination, last=False))
        core.extend(encode_address(self.source, last=True))
        core.append(CONTROL_UI)
        core.append(PID_NO_LAYER3)
        core.extend(self.information)
        fcs = crc16_ccitt(bytes(core)).to_bytes(2, "little")
        return bytes([FLAG]) + bytes(core) + fcs + bytes([FLAG])

    @classmethod
    def decode(cls, raw: bytes) -> "AX25Frame":
        if len(raw) < 18 or raw[0] != FLAG or raw[-1] != FLAG:
            raise ValueError("Invalid AX.25 frame boundaries")
        core = raw[1:-1]
        if len(core) < 18:
            raise ValueError("Frame too short")
        body, received_fcs = core[:-2], int.from_bytes(core[-2:], "little")
        calculated_fcs = crc16_ccitt(body)
        if received_fcs != calculated_fcs:
            raise ValueError("CRC mismatch")
        if body[14] != CONTROL_UI or body[15] != PID_NO_LAYER3:
            raise ValueError("Unsupported AX.25 control or PID")
        return cls(
            destination=decode_address(body[:7]),
            source=decode_address(body[7:14]),
            information=body[16:],
        )


def packet_to_frame(packet: LinkPacket) -> AX25Frame:
    return AX25Frame(
        destination=packet.destination,
        source=packet.source,
        information=packet.to_bytes(),
    )


def frame_to_packet(frame: AX25Frame) -> LinkPacket:
    return LinkPacket.from_bytes(frame.information)
