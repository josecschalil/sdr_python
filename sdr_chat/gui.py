from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .config import AppConfig
from .link import LinkEvent, LinkManager
from .radio import build_radio


class ChatGUI:
    def __init__(self, root: tk.Tk, config: AppConfig) -> None:
        self.root = root
        self.config = config
        self.link_manager: LinkManager | None = None
        self.event_queue: queue.Queue[LinkEvent] = queue.Queue()

        self.root.title(f"SDR Packet Radio Chat - {config.callsign}")
        self.root.geometry("980x760")

        self.status_var = tk.StringVar(value="Idle")
        self.channel_var = tk.StringVar(value="Channel state: IDLE")
        self.callsign_var = tk.StringVar(value=config.callsign)
        self.peer_var = tk.StringVar(value=config.peer_callsign)
        self.radio_var = tk.StringVar(value=config.radio_kind)
        self.mock_channel_var = tk.StringVar(value=config.mock_channel)
        self.uri_var = tk.StringVar(value=config.pluto_uri)
        self.center_freq_var = tk.StringVar(value=str(config.radio.center_freq))
        self.sample_rate_var = tk.StringVar(value=str(config.radio.sample_rate))
        self.symbol_rate_var = tk.StringVar(value=str(config.radio.symbol_rate))
        self.samples_per_symbol_var = tk.StringVar(value=str(config.radio.samples_per_symbol))
        self.tx_gain_var = tk.StringVar(value=str(config.radio.tx_gain))
        self.rx_gain_var = tk.StringVar(value=str(config.radio.rx_gain))

        self._build_widgets()
        self._update_station_title()
        self.root.after(100, self._poll_events)

    def post_event(self, event: LinkEvent) -> None:
        self.event_queue.put(event)

    def _build_widgets(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill=tk.BOTH, expand=True)

        info = ttk.LabelFrame(top, text="Connection Settings", padding=10)
        info.pack(fill=tk.X)
        ttk.Label(info, text="Local Callsign").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.callsign_var, width=18).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Peer Callsign").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.peer_var, width=18).grid(row=0, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Radio").grid(row=0, column=4, sticky="w", padx=4, pady=4)
        radio_combo = ttk.Combobox(
            info,
            textvariable=self.radio_var,
            values=("mock", "pluto"),
            state="readonly",
            width=10,
        )
        radio_combo.grid(row=0, column=5, sticky="w", padx=4, pady=4)
        radio_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_radio_fields())

        ttk.Label(info, text="Mock Channel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.mock_channel_entry = ttk.Entry(info, textvariable=self.mock_channel_var, width=18)
        self.mock_channel_entry.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Pluto URI").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.uri_entry = ttk.Entry(info, textvariable=self.uri_var, width=18)
        self.uri_entry.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Center Freq").grid(row=1, column=4, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.center_freq_var, width=14).grid(row=1, column=5, sticky="w", padx=4, pady=4)

        ttk.Label(info, text="Sample Rate").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.sample_rate_var, width=18).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Symbol Rate").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.symbol_rate_var, width=18).grid(row=2, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="Samples/Symbol").grid(row=2, column=4, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.samples_per_symbol_var, width=14).grid(row=2, column=5, sticky="w", padx=4, pady=4)

        ttk.Label(info, text="TX Gain").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.tx_gain_var, width=18).grid(row=3, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(info, text="RX Gain").grid(row=3, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(info, textvariable=self.rx_gain_var, width=18).grid(row=3, column=3, sticky="w", padx=4, pady=4)

        controls = ttk.LabelFrame(top, text="Link Control", padding=10)
        controls.pack(fill=tk.X, pady=12)
        ttk.Button(controls, text="Start Link", command=self._start_link).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(controls, text="Request TX", command=self._request_tx).grid(row=0, column=1, padx=6, pady=6)
        ttk.Button(controls, text="Release TX", command=self._release_tx).grid(row=0, column=2, padx=6, pady=6)
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=3, sticky="w", padx=12)
        ttk.Label(controls, textvariable=self.channel_var).grid(row=1, column=0, columnspan=4, sticky="w", padx=6)

        chat = ttk.LabelFrame(top, text="Messages", padding=10)
        chat.pack(fill=tk.BOTH, expand=True)
        self.chat_box = scrolledtext.ScrolledText(chat, wrap=tk.WORD, height=22, state=tk.DISABLED)
        self.chat_box.pack(fill=tk.BOTH, expand=True)

        compose = ttk.LabelFrame(top, text="Compose", padding=10)
        compose.pack(fill=tk.X, pady=12)
        self.entry = tk.Text(compose, height=4, wrap=tk.WORD)
        self.entry.pack(fill=tk.X, expand=True)
        ttk.Button(compose, text="Send Message", command=self._send_message).pack(anchor="e", pady=(8, 0))
        self._update_radio_fields()

    def _start_link(self) -> None:
        if self.link_manager is not None:
            self.status_var.set("Link already started")
            return
        try:
            self.config = self._read_config_from_form()
            radio = build_radio(self.config)
            self.link_manager = LinkManager(self.config, radio, on_event=self.post_event)
            self.link_manager.start()
            self.status_var.set("Receiver running")
            self._update_station_title()
        except Exception as exc:
            self.link_manager = None
            messagebox.showerror("Start failed", str(exc))

    def _send_message(self) -> None:
        text = self.entry.get("1.0", tk.END).strip()
        if not text:
            return
        if self.link_manager is None:
            messagebox.showwarning("Link not started", "Start the link first.")
            return
        self.link_manager.send_text(text)
        self.entry.delete("1.0", tk.END)

    def _request_tx(self) -> None:
        if self.link_manager is None:
            messagebox.showwarning("Link not started", "Start the link first.")
            return
        self.link_manager.request_tx()

    def _release_tx(self) -> None:
        if self.link_manager is None:
            messagebox.showwarning("Link not started", "Start the link first.")
            return
        self.link_manager.release_tx()

    def _read_config_from_form(self) -> AppConfig:
        callsign = self.callsign_var.get().strip()
        peer = self.peer_var.get().strip()
        if not callsign or not peer:
            raise ValueError("Local and peer callsigns are required")
        return AppConfig(
            callsign=callsign,
            peer_callsign=peer,
            radio_kind=self.radio_var.get().strip() or "mock",
            mock_channel=self.mock_channel_var.get().strip() or "default",
            pluto_uri=self.uri_var.get().strip() or "ip:192.168.2.1",
            radio=self.config.radio.__class__(
                center_freq=int(self.center_freq_var.get().strip()),
                sample_rate=int(self.sample_rate_var.get().strip()),
                symbol_rate=int(self.symbol_rate_var.get().strip()),
                samples_per_symbol=int(self.samples_per_symbol_var.get().strip()),
                tx_gain=float(self.tx_gain_var.get().strip()),
                rx_gain=float(self.rx_gain_var.get().strip()),
            ),
        )

    def _update_station_title(self) -> None:
        name = self.callsign_var.get().strip() or "Unconfigured"
        self.root.title(f"SDR Packet Radio Chat - {name}")

    def _update_radio_fields(self) -> None:
        is_mock = self.radio_var.get() == "mock"
        self.mock_channel_entry.configure(state=tk.NORMAL if is_mock else tk.DISABLED)
        self.uri_entry.configure(state=tk.DISABLED if is_mock else tk.NORMAL)

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._render_event(event)
        self.root.after(100, self._poll_events)

    def _render_event(self, event: LinkEvent) -> None:
        if event.kind in {"status", "warning", "error", "ack"}:
            self.status_var.set(event.message)
        if self.link_manager is not None:
            self.channel_var.set(f"Channel state: {self.link_manager.state.value}")
        self.chat_box.configure(state=tk.NORMAL)
        self.chat_box.insert(tk.END, f"[{event.kind.upper()}] {event.message}\n")
        self.chat_box.see(tk.END)
        self.chat_box.configure(state=tk.DISABLED)

    def shutdown(self) -> None:
        if self.link_manager is not None:
            self.link_manager.stop()
