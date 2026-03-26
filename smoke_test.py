from __future__ import annotations

import time

from sdr_chat.config import AppConfig
from sdr_chat.link import LinkEvent, LinkManager
from sdr_chat.radio import build_radio


def main() -> int:
    events: list[tuple[str, str]] = []

    def capture(tag: str):
        def inner(event: LinkEvent) -> None:
            events.append((tag, f"{event.kind}:{event.message}"))
        return inner

    a_config = AppConfig(callsign="N0CALL-1", peer_callsign="N0CALL-2", mock_channel="smoke")
    b_config = AppConfig(callsign="N0CALL-2", peer_callsign="N0CALL-1", mock_channel="smoke")

    a = LinkManager(a_config, build_radio(a_config), capture("A"))
    b = LinkManager(b_config, build_radio(b_config), capture("B"))

    try:
        a.start()
        b.start()
        time.sleep(0.2)
        a.request_tx()
        time.sleep(0.3)
        a.send_text("hello over SDR")
        time.sleep(0.3)
        a.release_tx()
        time.sleep(0.3)
    finally:
        a.stop()
        b.stop()

    for tag, event in events:
        print(f"{tag} {event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
