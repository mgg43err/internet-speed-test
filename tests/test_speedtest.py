"""Тесты скриптов замера скорости на локальном HTTP-сервере — интернет не нужен.

Сервер отдаёт тело известного размера и считает два счётчика:
  * hits        — сколько GET-запросов пришло;
  * connections — сколько TCP-соединений открыл клиент.
Второй счётчик и есть проверка keep-alive: без него соединений было бы 10.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import speedtest
import speedtest_keepalive

PAYLOAD = b"x" * 100_000  # 100 000 байт = ровно 0.10 МБ в десятичной СИ


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive на стороне сервера
    hits = 0
    connections = 0

    def setup(self):
        # Вызывается один раз на каждое TCP-соединение
        type(self).connections += 1
        super().setup()

    def do_GET(self):
        type(self).hits += 1
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *args):
        """Не засоряем вывод pytest access-логами."""


@pytest.fixture()
def server():
    """Локальный HTTP-сервер; отдаёт базовый URL вида http://127.0.0.1:PORT/x."""
    _Handler.hits = 0
    _Handler.connections = 0
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    yield f"http://{host}:{port}/file.bin"
    httpd.shutdown()
    httpd.server_close()


def test_fetch_downloads_exact_bytes(server):
    """fetch() возвращает точное число байт и положительное время."""
    elapsed, size = speedtest.fetch(server)
    assert size == len(PAYLOAD)
    assert elapsed > 0


def test_full_run_makes_10_requests_and_sums_bytes(server, monkeypatch, capsys):
    """Прогон urllib: 10 запросов, итоговый объём = 10 × 0.10 МБ = 1.00 МБ."""
    monkeypatch.setattr(sys, "argv", ["speedtest.py", server])
    assert speedtest.main() == 0

    out = capsys.readouterr().out
    assert _Handler.hits == speedtest.REQUESTS == 10
    assert "Успешных запросов: 10 из 10" in out
    assert "Общий объём скачанных данных: 1.00 МБ" in out
    assert "Скорость скачивания:" in out and "Мбит/с" in out


def test_urllib_opens_new_connection_per_request(server, monkeypatch):
    """Baseline открывает новое соединение на каждый запрос (10 соединений)."""
    monkeypatch.setattr(sys, "argv", ["speedtest.py", server])
    speedtest.main()
    assert _Handler.connections == speedtest.REQUESTS


def test_keepalive_reuses_single_connection(server, monkeypatch, capsys):
    """Главное свойство keep-alive-версии: 10 запросов — 1 соединение."""
    monkeypatch.setattr(sys, "argv", ["speedtest_keepalive.py", server])
    assert speedtest_keepalive.main() == 0

    out = capsys.readouterr().out
    assert _Handler.hits == speedtest_keepalive.REQUESTS == 10
    assert _Handler.connections == 1, "keep-alive должен переиспользовать соединение"
    assert "Успешных запросов: 10 из 10" in out
    assert "Общий объём скачанных данных: 1.00 МБ" in out


def test_usage_error_without_args(monkeypatch, capsys):
    """Без аргументов — подсказка и код выхода 2."""
    monkeypatch.setattr(sys, "argv", ["speedtest.py"])
    assert speedtest.main() == 2
    assert "Использование" in capsys.readouterr().err


def test_unreachable_host_fails_cleanly(monkeypatch, capsys):
    """Недоступный хост не роняет прогон: 10 ошибок -> код выхода 1."""
    monkeypatch.setattr(sys, "argv", ["speedtest.py", "http://127.0.0.1:9/"])
    assert speedtest.main() == 1
    err = capsys.readouterr().err
    assert err.count("ошибка") == speedtest.REQUESTS
    assert "Ни один запрос не прошёл" in err
