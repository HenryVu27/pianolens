"""PianoLens local web app (P-02): upload a recording or MIDI, get the report with A/B clips.

    uv run python scripts/pianolens_app.py            # http://127.0.0.1:8765, opens a browser
    uv run python scripts/pianolens_app.py --port 9000 --no-browser

Binds 127.0.0.1 only and makes no network calls. Uploads, reports and clips are stored under
``data/interim/app/`` (gitignored). See ``docs/APP.md``.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser

from pianolens.app.server import make_server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    srv, app = make_server(args.port)
    url = f"http://127.0.0.1:{app.port}/"
    print(f"PianoLens on {url}  (data: {app.root})  Ctrl+C to stop", flush=True)
    threading.Thread(target=lambda: app.catalog, daemon=True).start()  # warm the piece list
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
