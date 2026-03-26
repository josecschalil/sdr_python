from __future__ import annotations

import argparse
import tkinter as tk

from .config import AppConfig, RadioConfig
from .gui import ChatGUI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SDR packet radio chat")
    parser.add_argument("--callsign", default="", help="Local AX.25-style callsign, e.g. N0CALL-1")
    parser.add_argument("--peer", default="", help="Peer callsign")
    parser.add_argument("--radio", choices=["mock", "pluto"], default="mock")
    parser.add_argument("--mock-channel", default="default")
    parser.add_argument("--uri", default="ip:192.168.2.1")
    parser.add_argument("--center-freq", type=int, default=435_000_000)
    parser.add_argument("--sample-rate", type=int, default=1_000_000)
    parser.add_argument("--symbol-rate", type=int, default=10_000)
    parser.add_argument("--samples-per-symbol", type=int, default=20)
    parser.add_argument("--if-freq", type=int, default=100_000)
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
            intermediate_freq=args.if_freq,
            tx_gain=args.tx_gain,
            rx_gain=args.rx_gain,
        ),
    )
    root = tk.Tk()
    gui = ChatGUI(root, config)

    def on_close() -> None:
        gui.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0
