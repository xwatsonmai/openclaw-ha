#!/usr/bin/env python3
import asyncio
import json
import os
import ssl
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

try:
    import websockets
except ImportError:
    print(json.dumps({"ok": False, "error": "missing dependency: websockets"}, ensure_ascii=False))
    sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(ROOT)
HA_CONFIG = os.path.join(WORKSPACE, "skills", "home-assistant", "config.json")
LOG_PATH = os.path.join(ROOT, "logs", "ws_listener.log")
EVENTS_PATH = os.path.join(ROOT, "data", "recent_events.jsonl")
SYNC_SCRIPT = os.path.join(ROOT, "src", "sync_snapshot.py")
DEBOUNCE_SECONDS = float(os.environ.get("HA_WS_DEBOUNCE_SECONDS", "2"))
RECONNECT_SECONDS = float(os.environ.get("HA_WS_RECONNECT_SECONDS", "5"))

last_sync_at = 0.0


def ensure_dirs():
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)



def log_line(message):
    ensure_dirs()
    ts = datetime.now().strftime("%F %T")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")



def append_event(event):
    ensure_dirs()
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")



def load_ha_config():
    if not os.path.exists(HA_CONFIG):
        raise FileNotFoundError(f"HA config not found: {HA_CONFIG}")
    with open(HA_CONFIG, "r", encoding="utf-8") as f:
        data = json.load(f)
    url = data.get("url")
    token = data.get("token")
    if not url or not token:
        raise RuntimeError("HA config missing url or token")
    return url.rstrip("/"), token



def http_to_ws(url):
    parsed = urlparse(url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/websocket"



def should_sync(entity_id):
    if not entity_id:
        return False
    noisy_keywords = [
        "indicator_light",
        "prompt_tone",
        "screen_display_alternate",
    ]
    entity_id = entity_id.lower()
    return not any(k in entity_id for k in noisy_keywords)



def trigger_sync(reason, entity_id=None):
    global last_sync_at
    now = time.time()
    if now - last_sync_at < DEBOUNCE_SECONDS:
        log_line(f"sync skipped by debounce: reason={reason} entity_id={entity_id}")
        return
    last_sync_at = now
    try:
        result = subprocess.run(
            [sys.executable, SYNC_SCRIPT],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        log_line(f"sync triggered: reason={reason} entity_id={entity_id} rc={result.returncode} stdout={stdout} stderr={stderr}")
    except Exception as e:
        log_line(f"sync trigger failed: reason={reason} entity_id={entity_id} error={e}")


async def run_once():
    base_url, token = load_ha_config()
    ws_url = http_to_ws(base_url)
    ssl_context = ssl.create_default_context() if ws_url.startswith("wss://") else None

    log_line(f"connecting to {ws_url}")
    async with websockets.connect(ws_url, ssl=ssl_context, ping_interval=20, ping_timeout=20) as ws:
        hello = json.loads(await ws.recv())
        log_line(f"hello received: {hello}")

        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        log_line(f"auth result: {auth_result}")
        if auth_result.get("type") != "auth_ok":
            raise RuntimeError(f"auth failed: {auth_result}")

        await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
        sub_result = json.loads(await ws.recv())
        log_line(f"subscribe result: {sub_result}")
        if not sub_result.get("success"):
            raise RuntimeError(f"subscribe failed: {sub_result}")

        trigger_sync("startup")

        async for raw in ws:
            try:
                message = json.loads(raw)
            except Exception:
                log_line(f"non-json message: {raw}")
                continue

            if message.get("type") != "event":
                continue

            event = message.get("event", {})
            data = event.get("data", {})
            entity_id = data.get("entity_id")
            new_state = ((data.get("new_state") or {}) or {}).get("state")
            old_state = ((data.get("old_state") or {}) or {}).get("state")
            event_record = {
                "ts": datetime.now().isoformat(),
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state,
            }
            append_event(event_record)
            log_line(f"state_changed: entity_id={entity_id} old={old_state} new={new_state}")

            if should_sync(entity_id):
                trigger_sync("state_changed", entity_id)


async def main_loop():
    while True:
        try:
            await run_once()
        except Exception as e:
            log_line(f"listener error: {e}")
            await asyncio.sleep(RECONNECT_SECONDS)


if __name__ == "__main__":
    ensure_dirs()
    asyncio.run(main_loop())
