"""Subprocess fixture. No platform traffic, personal state, or credentials."""
import json
import subprocess
import sys
import time
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ssdl.ipc import read_message, write_message, MAX_MESSAGE_BYTES
    data = read_message(sys.stdin.buffer)
    mode = data.get("mode", "success")
    def send(kind, **values):
        write_message(sys.stdout.buffer, {"type": kind, **values})
    if mode == "exit":
        raise SystemExit(3)
    if mode == "error":
        send("error", data={"error": "fixture error", "error_code": "fixture_failure"})
    elif mode == "large_files":
        send("progress", data={"files": data["files"]})
        send("rpc", operation="before_post", id=1)
        read_message(sys.stdin.buffer)
        send("result", data={"files": data["files"], "quality": "fixture", "title": "fixture"})
    elif mode in {"bad_chunk", "oversize_chunk", "truncated_chunk", "chunk_hang"}:
        import base64
        frame = {"_ipc": "chunk", "size": 100, "offset": 1 if mode == "bad_chunk" else 0,
                 "data": base64.b64encode(b'{').decode()}
        if mode == "oversize_chunk": frame["size"] = MAX_MESSAGE_BYTES + 1
        sys.stdout.buffer.write(json.dumps(frame).encode() + b'\n'); sys.stdout.buffer.flush()
        if mode == "chunk_hang": time.sleep(60)
    elif mode == "hang":
        time.sleep(60)
    elif mode == "browser_hang":
        # Real Chrome runs an infinite synthetic script; the parent must kill only
        # this owned job tree, including the browser and Playwright driver.
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import socket
        import threading
        from unittest.mock import patch
        from ssdl.browser_media import BrowserMediaDiscovery, browser_driver
        from ssdl.network import public_network
        from ssdl import web_media
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"<body><script>while(true){}</script>"
                self.send_response(200); self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with browser_driver(True) as driver:
            connect = socket.socket.connect
            def fixture_connect(sock, address):
                return connect(sock, ("127.0.0.1", server.server_port))
            with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", server.server_port))]), \
                 patch.object(socket.socket, "connect", fixture_connect), patch.object(web_media.POLICY, "before_request"), public_network():
                BrowserMediaDiscovery(f"http://public.example:{server.server_port}/", lambda event: send("progress", data=event),
                                      driver, seconds=1).discover()
    elif mode == "tree":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        send("progress", data={"child_pid": child.pid})
        time.sleep(60)
    elif mode == "wait":
        send("rpc", operation="before_post", id=1)
        read_message(sys.stdin.buffer)
        send("result", data={"files": [], "quality": "fixture", "title": "fixture"})
    elif mode == "merge":
        send("progress", data={"stage": "postprocessing", "status_text": "merging fixture"})
        deadline = time.monotonic() + 1.2
        while time.monotonic() < deadline:
            sum(i * i for i in range(10000))
        send("result", data={"files": [], "quality": "fixture", "title": "fixture"})
    else:
        send("result", data={"files": [], "quality": "fixture", "title": "fixture"})
