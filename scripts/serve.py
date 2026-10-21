"""Serve this repo locally with CORS, so a local copy of the tools site can
fetch the data files the way it fetches them from data.rupeshbhandari.com.np.

    python3 scripts/serve.py          http://localhost:8001/
    python3 scripts/serve.py 9000     another port

The tools pages use http://localhost:8001/v1/ when they are opened from localhost.
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
print(f"Serving {ROOT} at http://localhost:{port}/")
ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(ROOT))).serve_forever()
