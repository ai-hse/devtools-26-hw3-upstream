#!/usr/bin/env python3
"""Управляемые HTTP-сценарии. Только учебные данные, без авторизации API."""

import argparse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

EXPORT = b"experiment,accuracy,latency_ms\nbaseline,0.8,100\ntuned,0.9,120\n"


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, mode):
        super().__init__(address, Handler)
        self.upload_mode = mode
        self.sessions = set()
        self.sessions_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def answer(self, status, body, headers=None, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Таймаут клиента в этой лаборатории ожидаем.

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/ok":
            return self.answer(200, {"status": "ok"})
        if path == "/unavailable":
            return self.answer(503, {"error": "Учебная недоступность"})
        if path == "/slow":
            time.sleep(15)
            return self.answer(200, {"status": "ok"})
        if path == "/redirect":
            return self.answer(302, {"location": "/ok"}, {"Location": "/ok"})
        if path == "/session":
            token = secrets.token_hex(16)
            with self.server.sessions_lock:
                self.server.sessions.add(token)
            return self.answer(200, {"message": "Учебный сеанс создан"}, {"Set-Cookie": f"lab_session={token}; Path=/; HttpOnly; SameSite=Lax"})
        if path == "/private-report":
            jar = cookies.SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie", ""))
            except cookies.CookieError:
                return self.answer(401, {"error": "Нужна cookie учебного сеанса"})
            token = jar.get("lab_session")
            with self.server.sessions_lock:
                valid = token is not None and token.value in self.server.sessions
            return self.answer(200, {"report": "demo", "row_count": 2}) if valid else self.answer(401, {"error": "Нужна cookie учебного сеанса"})
        if path == "/export.csv":
            range_value = self.headers.get("Range")
            if range_value is None:
                return self.answer(200, EXPORT, {"Accept-Ranges": "bytes"}, "text/csv")
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_value)
            if not match or not any(match.groups()):
                return self.answer(416, {"error": "Нужен один диапазон байтов"}, {"Content-Range": f"bytes */{len(EXPORT)}"})
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), len(EXPORT) - 1) if right else len(EXPORT) - 1
            else:
                count = int(right)
                start, end = max(0, len(EXPORT) - count), len(EXPORT) - 1
            if start >= len(EXPORT) or end < start:
                return self.answer(416, {"error": "Диапазон вне файла"}, {"Content-Range": f"bytes */{len(EXPORT)}"})
            return self.answer(206, EXPORT[start:end + 1], {"Content-Range": f"bytes {start}-{end}/{len(EXPORT)}", "Accept-Ranges": "bytes"}, "text/csv")
        return self.answer(404, {"error": "Маршрут не найден"})

    def do_POST(self):
        if urlsplit(self.path).path != "/reports":
            self.close_connection = True
            return self.answer(404, {"error": "Маршрут не найден"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 <= length <= 2 * 1024 * 1024:
            self.close_connection = True
            return self.answer(413, {"error": "Неверный размер загрузки"})
        self.rfile.read(length)
        if self.server.upload_mode == "slow":
            time.sleep(15)
            return self.answer(201, {"id": "fixture", "row_count": 1})
        # Намеренно обещаем больше байтов, чем отправляем: curl должен заметить обрыв.
        body = b'{"id":"fixture","row_count":'
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body) + 100))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        self.close_connection = True


def main():
    parser = argparse.ArgumentParser(description="HTTP-опыты: GET /ok /unavailable /slow /redirect /session /private-report /export.csv; POST /reports обрывает ответ либо ждёт 15 секунд.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--upload-mode", choices=("truncated", "slow"), default="truncated")
    args = parser.parse_args()
    with FixtureServer((args.host, args.port), args.upload_mode) as server:
        print(f"Fixture http://{args.host}:{server.server_port} upload_mode={args.upload_mode}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
