#!/usr/bin/env python3
import json, os, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data.json"
ROME = ZoneInfo("Europe/Rome")
API_URL = "https://api.lottevo.com/v1/lotteries/IT-012/draws?per_page=25"
FALLBACK_URL = "https://lottogazzetta.it/estrazioni-10elotto-5min/"
MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
          "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}

def valid_numbers(values):
    return (isinstance(values, list) and len(values) == 20 and
            all(isinstance(n, int) and 1 <= n <= 90 for n in values) and
            len(set(values)) == 20)

def get_json(url, headers=None):
    req = Request(url, headers={"User-Agent":"Italy10eLottoDashboard/1.0","Accept":"application/json", **(headers or {})})
    with urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def fetch_lottevo():
    key = os.environ.get("LOTTEVO_API_KEY", "").strip()
    if not key:
        raise RuntimeError("LOTTEVO_API_KEY GitHub Actions secret is missing")
    payload = get_json(API_URL, {"X-Api-Key": key})
    rows = payload.get("data", [])
    out = []
    for row in rows:
        if row.get("lottery_code") not in (None, "IT-012"):
            continue
        nums = row.get("numbers")
        if not valid_numbers(nums):
            continue
        stamp = row.get("drawn_at") or row.get("scheduled_at")
        if not stamp:
            continue
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ROME)
        draw_id = str(row.get("id") or row.get("draw_number") or dt.strftime("%Y%m%d%H%M"))
        out.append({"id":draw_id,"drawn_at":dt.isoformat(),"numbers":sorted(nums),"source":"Lottevo API (fallback)"})
    if not out:
        raise RuntimeError("Lottevo returned no valid IT-012 20/90 draw rows")
    return out

def fetch_lottogazzetta():
    req = Request(FALLBACK_URL, headers={"User-Agent":"Mozilla/5.0 (compatible; Italy10eLottoDashboard/1.0)"})
    with urlopen(req, timeout=25) as response:
        html = response.read().decode("utf-8", "replace")
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\\s+", " ", text)
    pattern = re.compile(
        r"(\\d{1,2})\\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\\s+(20\\d{2})\\s*[·-]\\s*ore\\s+(\\d{2}:\\d{2})\\s+Concorso\\s+(\\d+).*?20\\s+numeri(.*?)(?=\\d{1,2}\\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\\s+20\\d{2}\\s*[·-]\\s*ore|$)",
        re.I)
    out = []
    for m in pattern.finditer(text):
        day, month, year, hm, contest, body = m.groups()
        nums = [int(x) for x in re.findall(r"(?:^|\\s)(?:[1-9]|[1-8]\\d|90)\\s*(?=Numeri|Numero|$|\\s)", body)]
        # More robust extraction of numbered list entries: 1. 06 ... 20. 84
        entries = re.findall(r"(?:^|\\s)(?:[1-9]|1\\d|20)\\.\\s*(\\d{1,2})(?=\\s)", body)
        if len(entries) == 20:
            nums = [int(x) for x in entries]
        if not valid_numbers(nums):
            continue
        dt = datetime(int(year), MONTHS[month.lower()], int(day), int(hm[:2]), int(hm[3:]), tzinfo=ROME)
        out.append({"id":f"LG-{contest}","drawn_at":dt.isoformat(),"numbers":sorted(nums),"source":"Lotto Gazzetta (fallback)"})
    if not out:
        raise RuntimeError("Fallback page contained no parseable 5-minute draws")
    now = datetime.now(ROME)
    fresh = [r for r in out if timedelta(0) <= now - datetime.fromisoformat(r["drawn_at"]) <= timedelta(minutes=30)]
    if not fresh:
        latest = max(datetime.fromisoformat(r["drawn_at"]) for r in out)
        raise RuntimeError(f"Fallback archive is stale; latest listed draw is {latest.isoformat()}. Nothing imported.")
    return fresh

def main():
    old = {"game":"Italy 10eLotto 20/90","updated_at":None,"draws":[]}
    if DATA_FILE.exists():
        try: old = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    errors = []
    try:
        incoming = fetch_lottevo()
        selected_source = "Lottevo API (fallback)"
    except Exception as e:
        errors.append(f"Lottevo: {e}")
        try:
            incoming = fetch_lottogazzetta()
            selected_source = "Lotto Gazzetta (fallback)"
        except Exception as e2:
            errors.append(f"Lotto Gazzetta: {e2}")
            raise RuntimeError("All fallback sources failed. " + " | ".join(errors))
    by_id = {str(d["id"]): d for d in old.get("draws", []) if valid_numbers(d.get("numbers"))}
    for draw in incoming:
        by_id[str(draw["id"])] = draw
    merged = sorted(by_id.values(), key=lambda d: d["drawn_at"])
    result = {"game":"Italy 10eLotto 20/90","timezone":"Europe/Rome","updated_at":datetime.now(ROME).isoformat(),
              "source_status":selected_source,"draw_count":len(merged),"draws":merged[-10000:]}
    DATA_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\\n", encoding="utf-8")
    print(f"Saved {len(incoming)} new/current valid source rows; archive now has {len(result['draws'])} draws.")
    print("Source:", selected_source)

if __name__ == "__main__":
    main()
