#!/usr/bin/env python3
"""Замер скорости скачивания: 10 последовательных запросов к одному URL.

Использование:
    python3 speedtest.py <URL>
"""

import sys
import time
import urllib.request

REQUESTS = 10
TIMEOUT = 30
USER_AGENT = "internet-speed-test/1.0"


MB = 1_000_000.0
MBIT = 8.0 / MB


def fetch(url: str) -> tuple[float, int]:
    """Один запрос. Возвращает (время в секундах, скачано байт).

    Замер начинается до отправки запроса и заканчивается после чтения
    последнего байта тела — то есть учитываем подключение (TCP+TLS),
    ожидание ответа и само скачивание.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        total = len(response.read())
    elapsed = time.perf_counter() - start
    return elapsed, total


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Использование: {sys.argv[0]} <URL>", file=sys.stderr)
        print(f"Пример: {sys.argv[0]} https://proof.ovh.net/files/10Mb.dat", file=sys.stderr)
        return 2

    url = sys.argv[1]
    times: list[float] = []
    sizes: list[int] = []

    for i in range(1, REQUESTS + 1):
        try:
            elapsed, size = fetch(url)
        except Exception as error:
            print(f"#{i:>2}: ошибка — {error}", file=sys.stderr)
            continue
        times.append(elapsed)
        sizes.append(size)
        speed_mbps = size / elapsed * MBIT  # байты/сек × (8 / 10^6) = Мбит/с
        print(f"#{i:>2}: {elapsed:6.2f} c | {size / MB:8.2f} МБ | {speed_mbps:7.2f} Мбит/с")

    if not times:
        print("Ни один запрос не прошёл.", file=sys.stderr)
        return 1

    total_time = sum(times)
    total_bytes = sum(sizes)
    avg_time = total_time / len(times)
    avg_mbps = total_bytes / total_time * MBIT
    avg_mb_s = total_bytes / total_time / MB

    print("-" * 62)
    print(f"Успешных запросов: {len(times)} из {REQUESTS}")
    print(f"Среднее время запроса: {avg_time:.2f} c")
    print(f"Общий объём скачанных данных: {total_bytes / MB:.2f} МБ")
    print(f"Скорость скачивания: {avg_mbps:.2f} Мбит/с  ({avg_mb_s:.2f} МБ/с)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
