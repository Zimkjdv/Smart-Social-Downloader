"""Bounded local HTTP admission and an absolute request-input deadline."""
from __future__ import annotations

import io
import math
import os
import socket
import threading
import time
from http.server import ThreadingHTTPServer

MAX_CONNECTIONS = 32
READ_SECONDS = 10.0
WRITE_SECONDS = 5.0
BUSY_BODY = '{"error":"本機服務忙碌，請稍後重試。"}'.encode("utf-8")
BUSY_RESPONSE = (b"HTTP/1.0 503 Service Unavailable\r\n"
                 b"Content-Type: application/json; charset=utf-8\r\n"
                 b"Cache-Control: no-store\r\n"
                 b"X-Content-Type-Options: nosniff\r\n"
                 b"Retry-After: 1\r\nConnection: close\r\nContent-Length: "
                 + str(len(BUSY_BODY)).encode("ascii") + b"\r\n\r\n" + BUSY_BODY)


class DeadlineReader(io.RawIOBase):
    """Keep partial reads/trickle traffic from extending the input budget."""
    def __init__(self, connection: socket.socket, seconds: float):
        super().__init__()
        self.connection = connection
        self.deadline = time.monotonic() + seconds

    def readable(self):
        return True

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("HTTP request input deadline exceeded")
        return seconds

    def readinto(self, buffer):
        self.connection.settimeout(self.remaining())
        return self.connection.recv_into(buffer)


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"
    request_queue_size = 64

    def __init__(self, address, handler, *, max_connections=MAX_CONNECTIONS,
                 read_seconds=READ_SECONDS, write_seconds=WRITE_SECONDS):
        if type(max_connections) is not int or not 1 <= max_connections <= 1024:
            raise ValueError("Invalid HTTP connection limit")
        for seconds in (read_seconds, write_seconds):
            if type(seconds) not in (int, float) or not 0 < seconds <= 60 or not math.isfinite(seconds):
                raise ValueError("Invalid HTTP deadline")
        self.max_connections = max_connections
        self.read_seconds, self.write_seconds = read_seconds, write_seconds
        self._slots = threading.BoundedSemaphore(max_connections)
        self._connections_lock = threading.Lock()
        self._connections = set()
        super().__init__(address, handler)

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    @property
    def active_connections(self):
        with self._connections_lock:
            return len(self._connections)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            # Reject before creating a handler thread or reading any request data.
            try:
                request.settimeout(min(self.write_seconds, 0.1))
                request.sendall(BUSY_RESPONSE)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        with self._connections_lock:
            self._connections.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._release(request)
            raise

    def _release(self, request):
        with self._connections_lock:
            self._connections.discard(request)
        self._slots.release()

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(request)

    def server_close(self):
        super().server_close()
        with self._connections_lock:
            connections = list(self._connections)
        # These are only sockets accepted by this server, never media workers.
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
