from __future__ import annotations

import argparse
import tkinter as tk

from .config import AppConfig, RadioConfig
from .gui import ChatGUI
from .link import LinkManager
from .radio import build_radio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SDR packet radio chat")
    parser.add_argument("--callsign", required=True, help="Local AX.25-style callsign, e.g. N0CALL-1")
    parser.add_argument("--peer", required=True, help="Peer callsign")
    parser.add_argument("--radio", choices=["mock", "pluto"], default="mock")
    parser.add_argument("--mock-channel", default="default")
    parser.add_argument("--uri", default="ip:192.168.2.1")
    parser.add_argument("--center-freq", type=int, default=435_000_000)
    parser.add_argument("--sample-rate", type=int, default=1_000_000)
    parser.add_argument("--symbol-rate", type=int, default=10_000)
    parser.add_argument("--samples-per-symbol", type=int, default=20)
    parser.add_argument("--tx-gain", type=float, default=-10.0)
    parser.add_argument("--rx-gain", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = AppConfig(
        callsign=args.callsign,
        peer_callsign=args.peer,
        radio_kind=args.radio,
        mock_channel=args.mock_channel,
        pluto_uri=args.uri,
        radio=RadioConfig(
            center_freq=args.center_freq,
            sample_rate=args.sample_rate,
            symbol_rate=args.symbol_rate,
            samples_per_symbol=args.samples_per_symbol,
            tx_gain=args.tx_gain,
            rx_gain=args.rx_gain,
        ),
    )
    radio = build_radio(config)
    root = tk.Tk()
    gui: ChatGUI | None = None

    def on_event(event) -> None:
        if gui is not None:
            gui.post_event(event)

    link_manager = LinkManager(config, radio, on_event=on_event)
    gui = ChatGUI(root, config, link_manager)

    def on_close() -> None:
        link_manager.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0
