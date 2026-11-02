#!/usr/bin/env python3
"""Fetch verified Italy 10eLotto 20/90 draws from Lottevo and merge them."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("LOTTEVO_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Missing LOTTEVO_API_KEY repository secret.")
URL = "https://api.lottevo.com/v1/lotteries/IT-012/draws?" + urllib.parse.urlencode({"sort": "-drawn_at", "per_page": 25})
req = urllib.request.Request(URL, headers={
    "X-Api-Key": API_KEY,
    "Accept": "application/json",
    "User-Agent": "Italy10eLottoDashboard/1.0"
})
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.load(response)

items = payload.get("data")
if not isinstance(items, list):
    raise SystemExit("API response did not contain a data array; refusing to import.")

valid = []
for item in items:
    if not isinstance(item, dict):
        continue
    code = item.get("lottery_code")
    if code and code != "IT-012":
        continue
    numbers = item.get("numbers")
    if numbers is None:
        numbers = item.get("sorted_numbers")
    drawn_at = item.get("drawn_at")
    draw_id = item.get("id") or item.get("draw_id")
    if not isinstance(numbers, list) or len(numbers) != 20:
        continue
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 1 or n > 90 for n in numbers):
        continue
    if len(set(numbers)) != 20 or not isinstance(drawn_at, str) or not drawn_at:
        continue
    try:
        parsed = datetime.fromisoformat(drawn_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            continue
    except ValueError:
        continue
    stable_id = str(draw_id) if draw_id is not None else drawn_at + "|" + ",".join(map(str, sorted(numbers)))
    valid.append({
        "id": stable_id,
        "lottery_code": "IT-012",
        "drawn_at": drawn_at,
        "numbers": sorted(numbers),
        "source": "Lottevo API"
    })

if not valid:
    raise SystemExit("No valid IT-012 20/90 draw records in API response; existing data left unchanged.")

path = Path("data/italy-draws.json")
path.parent.mkdir(parents=True, exist_ok=True)
if path.exists():
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        old_draws = old.get("draws", []) if isinstance(old, dict) else []
    except Exception:
        old_draws = []
else:
    old_draws = []

merged = {}
for draw in old_draws + valid:
    if isinstance(draw, dict) and draw.get("id") and isinstance(draw.get("numbers"), list):
        merged[str(draw["id"])] = draw

draws = sorted(merged.values(), key=lambda d: d.get("drawn_at", ""))[-5000:]
old_sorted = sorted(old_draws, key=lambda d: d.get("drawn_at", ""))[-5000:]
if draws == old_sorted:
    print(f"No new or corrected draws. Store remains at {len(draws)} unique draw(s).")
    raise SystemExit(0)
result = {
    "source": "Lottevo API (game IT-012)",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "draw_count": len(draws),
    "draws": draws
}
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Validated {len(valid)} API draw(s); saved {len(draws)} unique draw(s).")
