#!/usr/bin/env python3
"""
Локальный источник для бенчмарка: эмулирует speed.cloudflare.com.

Зачем: 11.09.2026 speed.cloudflare.com начал отвечать 429 Too Many Requests
на серийные запросы к /__down — лимит идёт по объёму за окно, а не по числу
запросов. Пауза в 5 секунд давала один успех из трёх, после 15 секунд первый
же запрос снова упирался в лимит. Сравнивать транспорты в таких условиях
нельзя: разброс внутри одного варианта доходил до 91 %, и мерялось везение,
а не протокол.

Локальный origin убирает из измерения и лимит, и капризы внешнего канала:
остаётся чистый оверхед транспорта xray. Внешний канал меряется отдельно,
разовым прогоном, а не двенадцать раз подряд.

Совместим по интерфейсу: /__down?bytes=N отдаёт N байт, /__up принимает POST.
"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHUNK = b"\0" * 65536


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _bytes_param(self) -> int:
        if "?" not in self.path:
            return 0
        query = self.path.split("?", 1)[1]
        for part in query.split("&"):
            if part.startswith("bytes="):
                try:
                    return max(0, min(int(part[6:]), 2 * 1024 ** 3))
                except ValueError:
                    return 0
        return 0

    # Имена do_GET/do_POST задаёт BaseHTTPRequestHandler, переименовать нельзя.
    def do_GET(self):
        # Метаданные о точке выхода бенчмарк запрашивает отдельным запросом.
        # Выхода здесь нет — отвечаем честно, чтобы в отчёте не было пустоты,
        # которую легко принять за сбой.
        if self.path.startswith(("/meta", "/cdn-cgi")):
            body = b'{"origin":"local","note":"transport overhead bench, no external path"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        total = self._bytes_param()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(total))
        self.end_headers()
        left = total
        while left > 0:
            block = CHUNK if left >= len(CHUNK) else CHUNK[:left]
            try:
                self.wfile.write(block)
            except (BrokenPipeError, ConnectionResetError):
                return
            left -= len(block)

    def do_POST(self):
        left = int(self.headers.get("Content-Length", 0))
        while left > 0:
            left -= len(self.rfile.read(min(left, len(CHUNK))))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass  # лог на каждый запрос тут только мешает


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
