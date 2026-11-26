#!/usr/bin/env python3
"""Verifica articolele noi de pe profilul Xiaomi Romania (Xiaomi Community)
si trimite o notificare push pe telefon prin ntfy.sh."""
import datetime
import json
import os
import sys
import time
import urllib.request

USER_ID = "18ae95de6a129fbbb03173b8464aa75c"
API = os.environ.get("API_URL", "https://ams-api.buy.mi.com/bbs/api/ro/thread/user-thread")
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh/")
POST_URL = "https://new.c.mi.com/ro/post/"
STATE_FILE = "state.json"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
TEST = os.environ.get("TEST_MODE", "").lower() == "true"


def fetch_posts():
    url = f"{API}?user_id={USER_ID}&after=&limit=20&_t={int(time.time())}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Origin": "https://new.c.mi.com",
        "Referer": "https://new.c.mi.com/",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    records = (data.get("data") or {}).get("records")
    if data.get("code") != 0 or not isinstance(records, list):
        raise RuntimeError(f"Raspuns neasteptat de la API: {data.get('msg') or data.get('code')}")
    return records


def push(rec, prefix=""):
    payload = {
        "topic": TOPIC,
        "title": "Articol nou pe Xiaomi Community",
        "message": prefix + (rec.get("title") or "(fara titlu)").strip(),
        "click": POST_URL + str(rec["aid"]),
        "priority": 4,
        "tags": ["bell"],
    }
    req = urllib.request.Request(
        NTFY_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": [], "heartbeat": ""}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def main():
    if not TOPIC:
        sys.exit("Lipseste secretul NTFY_TOPIC.")
    records = fetch_posts()
    state = load_state()
    seen = list(state.get("seen", []))
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    error = None

    if TEST and records:
        newest = max(records, key=lambda r: r.get("create_time") or 0)
        push(newest, "TEST: ")
        print("Notificare de test trimisa.")

    if not seen:
        seen = [r["aid"] for r in records]
        print(f"Prima rulare: memorez {len(seen)} articole existente, fara notificari.")
    else:
        known = set(seen)
        fresh = sorted((r for r in records if r["aid"] not in known),
                       key=lambda r: r.get("create_time") or 0)
        for r in fresh:
            try:
                push(r)
                seen.append(r["aid"])
                print("Notificare trimisa pentru", r["aid"])
            except Exception as e:  # nu marcam ca vazut daca trimiterea a esuat
                error = e
                break
        if not fresh:
            print("Nimic nou.")

    state["seen"] = seen[-300:]
    state["heartbeat"] = today
    save_state(state)
    if error:
        raise error


if __name__ == "__main__":
    main()
