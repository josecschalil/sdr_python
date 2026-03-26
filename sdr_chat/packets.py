from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum


class PacketType(str, Enum):
    REQUEST = "REQUEST"
    GRANT = "GRANT"
    RELEASE = "RELEASE"
    DATA = "DATA"
    ACK = "ACK"
    HEARTBEAT = "HEARTBEAT"
    STATUS = "STATUS"


@dataclass(slots=True)
class LinkPacket:
    packet_type: PacketType
    source: str
    destination: str
    sequence: int = 0
    ack_for: int | None = None
    payload: str = ""
    timestamp: float = 0.0

    def to_bytes(self) -> bytes:
        body = {
            "type": self.packet_type.value,
            "source": self.source,
            "destination": self.destination,
            "sequence": self.sequence,
            "ack_for": self.ack_for,
            "payload": self.payload,
            "timestamp": self.timestamp or time.time(),
        }
        return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "LinkPacket":
        body = json.loads(raw.decode("utf-8"))
        return cls(
            packet_type=PacketType(body["type"]),
            source=body["source"],
            destination=body["destination"],
            sequence=body.get("sequence", 0),
            ack_for=body.get("ack_for"),
            payload=body.get("payload", ""),
            timestamp=body.get("timestamp", 0.0),
        )
