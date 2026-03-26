from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .config import AppConfig
from .link import LinkEvent, LinkManager


class ChatGUI:
    def __init__(self, root: tk.Tk, config: AppConfig, link_manager: LinkManager) -> None:
        self.root = root
        self.config = config
        self.link_manager = link_manager
        self.event_queue: queue.Queue[LinkEvent] = queue.Queue()

        self.root.title(f"SDR Packet Radio Chat - {config.callsign}")
        self.root.geometry("900x620")

        self.status_var = tk.StringVar(value="Idle")
        self.channel_var = tk.StringVar(value="Channel state: IDLE")

        self._build_widgets()
        self.root.after(100, self._poll_events)

    def post_event(self, event: LinkEvent) -> None:
        self.event_queue.put(event)

    def _build_widgets(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill=tk.BOTH, expand=True)

        info = ttk.LabelFrame(top, text="Station", padding=10)
        info.pack(fill=tk.X)
        ttk.Label(info, text=f"Local: {self.config.callsign}").grid(row=0, column=0, sticky="w")
        ttk.Label(info, text=f"Peer: {self.config.peer_callsign}").grid(row=0, column=1, sticky="w", padx=20)
        ttk.Label(info, text=f"Radio: {self.config.radio_kind}").grid(row=0, column=2, sticky="w")

        controls = ttk.LabelFrame(top, text="Link Control", padding=10)
        controls.pack(fill=tk.X, pady=12)
        ttk.Button(controls, text="Start Link", command=self._start_link).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(controls, text="Request TX", command=self.link_manager.request_tx).grid(row=0, column=1, padx=6, pady=6)
        ttk.Button(controls, text="Release TX", command=self.link_manager.release_tx).grid(row=0, column=2, padx=6, pady=6)
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

    def _start_link(self) -> None:
        try:
            self.link_manager.start()
            self.status_var.set("Receiver running")
        except Exception as exc:
            messagebox.showerror("Start failed", str(exc))

    def _send_message(self) -> None:
        text = self.entry.get("1.0", tk.END).strip()
        if not text:
            return
        self.link_manager.send_text(text)
        self.entry.delete("1.0", tk.END)

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
        self.channel_var.set(f"Channel state: {self.link_manager.state.value}")
        self.chat_box.configure(state=tk.NORMAL)
        self.chat_box.insert(tk.END, f"[{event.kind.upper()}] {event.message}\n")
        self.chat_box.see(tk.END)
        self.chat_box.configure(state=tk.DISABLED)
