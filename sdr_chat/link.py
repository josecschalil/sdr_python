from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .ax25 import AX25Frame, frame_to_packet, packet_to_frame
from .config import AppConfig
from .modem import BPSKModem
from .packets import LinkPacket, PacketType
from .radio import BaseRadio, RadioError


class ChannelState(str, Enum):
    IDLE = "IDLE"
    REQUESTING = "REQUESTING"
    GRANTED = "GRANTED"
    REMOTE_TX = "REMOTE_TX"


@dataclass(slots=True)
class LinkEvent:
    kind: str
    message: str
    packet: LinkPacket | None = None


class LinkManager:
    def __init__(
        self,
        config: AppConfig,
        radio: BaseRadio,
        on_event: Callable[[LinkEvent], None],
    ) -> None:
        self.config = config
        self.radio = radio
        self.on_event = on_event
        self.modem = BPSKModem(config.radio)
        self.state = ChannelState.IDLE
        self.running = False
        self.sequence = 1
        self._seen_sequences: set[tuple[str, int]] = set()
        self._outbound: queue.Queue[LinkPacket] = queue.Queue()
        self._tx_thread: threading.Thread | None = None
        self.last_peer_seen_at: float | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.radio.start(self._handle_samples)
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._tx_thread.start()
        if self.config.initial_tx_owner.strip() == self.config.callsign:
            self.state = ChannelState.GRANTED
            self._emit("status", "Startup transmit permission assigned to this station")
        elif self.config.initial_tx_owner.strip() == self.config.peer_callsign:
            self.state = ChannelState.REMOTE_TX
            self._emit("status", f"Startup transmit permission assigned to {self.config.peer_callsign}")
        self._emit("status", "Receiver started")

    def stop(self) -> None:
        self.running = False
        self.radio.stop()
        if self._tx_thread:
            self._tx_thread.join(timeout=1.0)
        self._emit("status", "Link stopped")

    def request_tx(self) -> None:
        if self.state not in {ChannelState.IDLE}:
            self._emit("warning", f"Cannot request TX while state is {self.state.value}")
            return
        self.state = ChannelState.REQUESTING
        self._queue_packet(PacketType.REQUEST, payload="TX request")
        self._emit("status", "Transmit request sent")

    def release_tx(self) -> None:
        if self.state != ChannelState.GRANTED:
            self._emit("warning", "You do not currently hold transmit permission")
            return
        self._queue_packet(PacketType.RELEASE, payload="TX release")
        self.state = ChannelState.IDLE
        self._emit("status", "Transmit permission released")

    def grant_tx(self) -> None:
        if self.state == ChannelState.GRANTED:
            self._emit("warning", "You already hold transmit permission")
            return
        self.state = ChannelState.REMOTE_TX
        self._queue_packet(PacketType.GRANT, payload="Manual TX grant")
        self._emit("status", f"Transmit permission granted to {self.config.peer_callsign}")

    def send_text(self, text: str) -> None:
        if self.state != ChannelState.GRANTED:
            self._emit("warning", "Request transmit permission before sending data")
            return
        packet = self._queue_packet(PacketType.DATA, payload=text)
        self._emit("tx", f"You: {text}", packet)

    def ping_peer(self) -> None:
        packet = self._queue_packet(PacketType.HEARTBEAT, payload="ping")
        self._emit("status", f"Peer ping sent to {self.config.peer_callsign}", packet)

    def _tx_loop(self) -> None:
        while self.running:
            try:
                packet = self._outbound.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                frame = packet_to_frame(packet).encode()
                iq = self.modem.modulate(frame)
                self.radio.transmit(iq)
            except RadioError as exc:
                self._emit("error", f"Radio transmit failed: {exc}")
            except Exception as exc:  # pragma: no cover - defensive
                self._emit("error", f"Unexpected transmit error: {exc}")

    def _handle_samples(self, samples: list[complex]) -> None:
        for raw_frame in self.modem.demodulate(samples):
            try:
                frame = self._decode_frame(raw_frame)
                packet = frame_to_packet(frame)
            except Exception as exc:
                self._emit("error", f"Frame decode failed: {exc}")
                continue
            if packet.destination not in {self.config.callsign, "CQ"}:
                continue
            dedupe_key = (packet.source, packet.sequence)
            if packet.sequence and dedupe_key in self._seen_sequences and packet.packet_type == PacketType.DATA:
                continue
            if packet.sequence:
                self._seen_sequences.add(dedupe_key)
            self.last_peer_seen_at = time.time()
            self._handle_packet(packet)

    def _decode_frame(self, raw_frame: bytes):
        if raw_frame[0] != 0x7E:
            raw_frame = bytes([0x7E]) + raw_frame
        if raw_frame[-1] != 0x7E:
            raw_frame = raw_frame + bytes([0x7E])
        return AX25Frame.decode(raw_frame)

    def _handle_packet(self, packet: LinkPacket) -> None:
        if packet.packet_type == PacketType.REQUEST:
            self.state = ChannelState.REMOTE_TX
            self._queue_packet(PacketType.GRANT, payload="TX granted")
            self._emit("status", f"{packet.source} requested TX, grant sent", packet)
            return

        if packet.packet_type == PacketType.GRANT:
            self.state = ChannelState.GRANTED
            self._emit("status", f"{packet.source} granted transmit permission", packet)
            return

        if packet.packet_type == PacketType.RELEASE:
            self.state = ChannelState.IDLE
            self._emit("status", f"{packet.source} released transmit permission", packet)
            return

        if packet.packet_type == PacketType.DATA:
            self._emit("rx", f"{packet.source}: {packet.payload}", packet)
            self._queue_packet(PacketType.ACK, ack_for=packet.sequence, payload="Message received")
            return

        if packet.packet_type == PacketType.HEARTBEAT:
            self._emit("status", f"{packet.source} is reachable", packet)
            self._queue_packet(PacketType.STATUS, payload="online")
            return

        if packet.packet_type == PacketType.STATUS:
            self._emit("status", f"{packet.source} responded: {packet.payload}", packet)
            return

        if packet.packet_type == PacketType.ACK:
            self._emit("ack", f"ACK received for sequence {packet.ack_for}", packet)
            return

        self._emit("status", f"{packet.source}: {packet.packet_type.value}", packet)

    def _queue_packet(
        self,
        packet_type: PacketType,
        payload: str = "",
        ack_for: int | None = None,
    ) -> LinkPacket:
        packet = LinkPacket(
            packet_type=packet_type,
            source=self.config.callsign,
            destination=self.config.peer_callsign,
            sequence=self.sequence,
            ack_for=ack_for,
            payload=payload,
            timestamp=time.time(),
        )
        self.sequence += 1
        self._outbound.put(packet)
        return packet

    def _emit(self, kind: str, message: str, packet: LinkPacket | None = None) -> None:
        self.on_event(LinkEvent(kind=kind, message=message, packet=packet))

    def peer_status_text(self) -> str:
        if self.last_peer_seen_at is None:
            return f"Peer {self.config.peer_callsign}: not detected"
        age = max(0.0, time.time() - self.last_peer_seen_at)
        return f"Peer {self.config.peer_callsign}: detected ({age:.1f}s ago)"
