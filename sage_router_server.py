"""SAGE sidecar HTTP server — wraps the REAL sage.py directly.

Imports sage.py as a module, reusing its actual working logic (commands,
memory, settings, conversation state, local/web retrieval) unmodified, and
swaps only its MLX-based model runtime for one that talks to llama-server
over HTTP (llama_bridge.LlamaServerRuntime) — so this runs cross-platform
instead of being Apple-Silicon-only.

Endpoints:
  GET  /health    -> {"ok": true}
  POST /message   -> {"text": "..."}
                      For a recognized command (handle_command returns
                      is_command=True): one JSON line with the direct
                      result and whether it signals shutdown.
                      Otherwise: streams newline-delimited JSON events
                      exactly as sage.ask_sage_stream() produces them
                      (thinking_started / token / thinking_finished /
                      complete) as they happen.

Response framing: no Content-Length, Connection: close, each JSON line
flushed to the socket as it's produced — plain NDJSON over a
closes-when-done connection. Deliberately simple rather than implementing
real HTTP chunked transfer-encoding by hand; adequate for one local
sidecar talking to one client (the Tauri app) at a time.

Run from the same directory as sage.py and all its sibling modules:
    python3 sage_router_server.py [SIDECAR_PORT] [LLAMA_SERVER_PORT]
    (defaults: 8722, 8721)
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sage
from llama_bridge import LlamaServerRuntime

LLAMA_SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8721

# Everything in sage.py except model inference runs exactly as it does
# from the CLI — this is the only line that changes its behavior.
sage.sage_ai.runtime = LlamaServerRuntime(port=LLAMA_SERVER_PORT)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _start_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write_line(self, obj: dict):
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/message":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        text = payload.get("text", "")

        try:
            is_command, result, should_exit = sage.handle_command(text)
        except Exception as exc:
            is_command, result, should_exit = True, f"Command error: {exc}", False

        self._start_stream()

        if is_command:
            self._write_line({
                "type": "complete",
                "text": result or "",
                "model": "NONE",
                "should_exit": should_exit,
            })
            return

        try:
            for event in sage.ask_sage_stream(text):
                self._write_line({
                    "type": event.type,
                    "text": event.text,
                    "model": event.model,
                    "thinking": event.thinking,
                    "elapsed_s": event.elapsed_s,
                    "generation_tokens": event.generation_tokens,
                    "generation_tps": event.generation_tps,
                })
        except Exception as exc:
            self._write_line({"type": "error", "message": str(exc)})

    def log_message(self, format, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8722
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(
        f"SAGE sidecar (real sage.py, llama-server backed) on 127.0.0.1:{port}, "
        f"talking to llama-server on 127.0.0.1:{LLAMA_SERVER_PORT}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
