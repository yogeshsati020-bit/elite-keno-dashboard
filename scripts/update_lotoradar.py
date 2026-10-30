
#!/usr/bin/env python3

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://lotoradar.com/en/grecia_kino.html"
OUTPUT = Path("latest.json")
TZ = ZoneInfo("Europe/Bucharest")


def valid_numbers(text):
    values = re.findall(r"(?<!\d)\d{1,2}(?!\d)", text)

    if len(values) != 20:
        return None

    numbers = [int(x) for x in values]

    if (
        all(1 <= n <= 80 for n in numbers)
        and len(set(numbers)) == 20
    ):
        return sorted(numbers)

    return None


def parse_date_time(text):
    date_match = re.search(
        r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",
        text
    )

    if date_match:
        year, month, day = map(int, date_match.groups())
    else:
        date_match = re.search(
            r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
            text
        )

        if not date_match:
            return None

        day, month, year = map(int, date_match.groups())

    time_match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        text
    )

    if not time_match:
        return None

    date = f"{year:04d}-{month:02d}-{day:02d}"
    time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

    return date, time


def main():

    print("Connecting to LotoRadar...")

    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 EliteKenoDashboard/1.0"
        }
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    draws = []
    seen = set()

    # Read public results table
    for row in soup.select("tr"):

        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.select("th, td")
        ]

        if not cells:
            continue

        numbers = None

        for cell in cells:
            numbers = valid_numbers(cell)

            if numbers:
                break

        if not numbers:
            continue

        row_text = " | ".join(cells)

        date_time = parse_date_time(row_text)

        if not date_time:
            continue

        date, time = date_time

        id_match = re.search(r"#?\b(\d{5,})\b", row_text)

        draw_id = (
            id_match.group(1)
            if id_match
            else f"LR-{date}-{time}"
        )

        key = (draw_id, tuple(numbers))

        if key in seen:
            continue

        seen.add(key)

        draws.append({
            "id": draw_id,
            "date": date,
            "time": time,
            "stamp": f"{date} {time}",
            "numbers": numbers
        })

    if not draws:
        raise RuntimeError(
            "No valid draw rows found. "
            "LotoRadar HTML may have changed or results may load dynamically."
        )

    # Newest draws first
    draws.sort(
        key=lambda item: (item["stamp"], item["id"]),
        reverse=True
    )

    draws = draws[:100]

    payload = {
        "source": URL,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "timezone_note": "Draw times are as published by LotoRadar (Romanian local time).",
        "count": len(draws),
        "draws": draws
    }

    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print(f"SUCCESS: Saved {len(draws)} draws to latest.json")


if __name__ == "__main__":
    main()
