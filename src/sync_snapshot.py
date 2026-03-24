#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(ROOT)
DEFAULT_HA_CONFIG = os.path.join(WORKSPACE, "skills", "home-assistant", "config.json")
PROJECT_HA_CONFIG = os.path.join(ROOT, "config", "ha.json")
RULES_PATH = os.path.join(ROOT, "config", "cache_rules.json")
FOCUS_PATH = os.path.join(ROOT, "config", "focus_entities.json")
ALIASES_PATH = os.path.join(ROOT, "config", "entity_aliases.json")
RAW_PATH = os.path.join(ROOT, "data", "raw_states.json")
SUMMARY_PATH = os.path.join(ROOT, "data", "summary.json")
BRIEF_PATH = os.path.join(ROOT, "data", "answer_brief.json")
CARD_PATH = os.path.join(ROOT, "data", "answer_card.md")

DEFAULT_RULES = {
    "exclude_name_keywords": ["指示灯", "提示音", "备用开关"],
    "exclude_entity_id_keywords": ["indicator_light", "prompt_tone", "screen_display_alternate"],
    "priority_domains": ["light", "climate", "fan", "cover", "vacuum", "sensor", "binary_sensor", "switch"],
    "environment_keywords": ["temperature", "humidity", "pm2_5", "co2", "tvoc"],
    "environment_device_classes": ["temperature", "humidity", "pm25", "carbon_dioxide", "volatile_organic_compounds"],
    "critical_binary_keywords": ["door", "window", "motion", "occupancy", "presence", "smoke", "gas", "leak", "lock"],
    "switch_include_keywords": ["电辅热", "aux heating"],
    "include_name_keywords": ["客厅", "餐厅", "书房", "卧室", "主卧", "次卧", "儿童房", "走廊", "入户", "阳台", "厨房", "卫生间", "浴室", "空调", "灯", "风扇", "窗帘", "晾衣架", "扫地机", "门", "窗", "人体", "温度", "湿度"],
    "freshness": {"fresh_seconds": 60, "stale_seconds": 300}
}

ROOM_KEYWORDS = ["客厅", "餐厅", "书房", "卧室", "主卧", "次卧", "儿童房", "走廊", "入户", "阳台", "厨房", "卫生间", "浴室"]
ACTIVE_BINARY_SENSOR_STATES = {"on", "open", "detected", "motion", "occupied", "home", "problem"}
INVALID_SENSOR_STATES = {"unknown", "unavailable", "none", "null", ""}
FOCUS_GROUPS = ["lights", "climates", "fans", "covers", "vacuums", "environment", "switches", "critical_binary"]


def utc_now():
    return datetime.now(timezone.utc)


def utc_now_iso():
    return utc_now().isoformat()


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ha_config():
    env_url = os.environ.get("HA_URL")
    env_token = os.environ.get("HA_TOKEN")
    if env_url and env_token:
        return env_url.rstrip("/"), env_token

    for path in (PROJECT_HA_CONFIG, DEFAULT_HA_CONFIG):
        data = load_json(path)
        if data and data.get("url") and data.get("token"):
            return data["url"].rstrip("/"), data["token"]

    raise FileNotFoundError(
        "HA config not found. Set HA_URL/HA_TOKEN or provide config/ha.json"
    )


def load_rules():
    rules = DEFAULT_RULES.copy()
    custom = load_json(RULES_PATH, {}) or {}
    for k, v in custom.items():
        rules[k] = v
    return rules


def load_focus_entities():
    data = load_json(FOCUS_PATH, {}) or {}
    result = {group: set(data.get(group, [])) for group in FOCUS_GROUPS}
    result["all"] = set().union(*result.values()) if result else set()
    return result


def load_aliases():
    return load_json(ALIASES_PATH, {}) or {}


def api_request(base_url, token, endpoint):
    req = urllib.request.Request(
        f"{base_url}{endpoint}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_states(base_url, token):
    return api_request(base_url, token, "/api/states")


def fetch_state(base_url, token, entity_id):
    return api_request(base_url, token, f"/api/states/{entity_id}")


def infer_room(name, entity_id):
    text = f"{name or ''} {entity_id or ''}"
    for room in ROOM_KEYWORDS:
        if room in text:
            return room
    return "未分类"


def clean_name(name, entity_id, aliases):
    if entity_id in aliases:
        return aliases[entity_id]
    raw = (name or entity_id or "").strip()
    raw = re.sub(r"\s+None$", "", raw)
    raw = re.sub(r"\s{2,}", " ", raw)
    raw = raw.strip()
    if raw.lower() == (entity_id or "").lower() and entity_id:
        fallback = entity_id.split(".", 1)[-1].replace("_", " ").strip()
        return aliases.get(entity_id, fallback or raw)
    return raw


def simplify_state(item, aliases):
    attrs = item.get("attributes", {})
    entity_id = item.get("entity_id")
    return {
        "entity_id": entity_id,
        "state": item.get("state"),
        "friendly_name": clean_name(attrs.get("friendly_name"), entity_id, aliases),
        "device_class": attrs.get("device_class"),
        "unit_of_measurement": attrs.get("unit_of_measurement"),
        "current_temperature": attrs.get("current_temperature"),
        "temperature": attrs.get("temperature"),
        "hvac_mode": attrs.get("hvac_mode"),
        "last_changed": item.get("last_changed"),
        "last_updated": item.get("last_updated"),
        "room": infer_room(attrs.get("friendly_name"), entity_id)
    }


def should_exclude(simple, rules):
    name = (simple.get("friendly_name") or "").lower()
    entity_id = (simple.get("entity_id") or "").lower()
    for kw in rules.get("exclude_name_keywords", []):
        if kw.lower() in name:
            return True
    for kw in rules.get("exclude_entity_id_keywords", []):
        if kw.lower() in entity_id:
            return True
    return False


def is_relevant(simple, domain, rules, focus):
    entity_id = simple.get("entity_id") or ""
    name = simple.get("friendly_name") or ""
    text = f"{name} {entity_id}"

    if entity_id in focus["all"]:
        return True
    if domain in {"light", "climate", "fan", "cover", "vacuum"}:
        return True
    if domain == "switch":
        return any(kw.lower() in text.lower() for kw in rules.get("switch_include_keywords", []))
    if domain in {"sensor", "binary_sensor"}:
        return any(kw.lower() in text.lower() for kw in rules.get("include_name_keywords", []))
    return False


def is_valid_environment(simple, rules, focus):
    entity_id = simple.get("entity_id") or ""
    state = str(simple.get("state") or "").strip().lower()
    if entity_id in focus["environment"]:
        return state not in INVALID_SENSOR_STATES
    if state in INVALID_SENSOR_STATES:
        return False
    device_class = (simple.get("device_class") or "").lower()
    entity_id_lower = entity_id.lower()
    env_keywords = tuple(k.lower() for k in rules.get("environment_keywords", []))
    env_classes = set(k.lower() for k in rules.get("environment_device_classes", []))
    return device_class in env_classes or any(k in entity_id_lower for k in env_keywords)


def concise_item(simple):
    return {
        "name": simple["friendly_name"],
        "entity_id": simple["entity_id"],
        "state": simple["state"],
        "room": simple["room"],
        "temperature": simple.get("temperature"),
        "current_temperature": simple.get("current_temperature"),
        "unit": simple.get("unit_of_measurement"),
        "device_class": simple.get("device_class")
    }


def pick_focus(states, entity_ids):
    picked = []
    index = {s["entity_id"]: s for s in states}
    for entity_id in entity_ids:
        if entity_id in index:
            picked.append(concise_item(index[entity_id]))
    return picked


def build_focus_alerts(focus_views):
    alerts = []
    for group in ["lights", "climates", "fans", "covers", "vacuums", "switches"]:
        for item in focus_views.get(group, []):
            if str(item.get("state") or "").lower() in {"unknown", "unavailable"}:
                alerts.append({
                    "type": "focus_unavailable",
                    "group": group,
                    "name": item["name"],
                    "entity_id": item["entity_id"],
                    "state": item["state"]
                })
    return alerts


def build_answer_views(summary, focus_views):
    overview = summary["overview"]
    env = focus_views["environment"] or summary["environment_sensors"]
    alerts = []

    if summary["counts"]["unavailable"]:
        alerts.append(f"有 {summary['counts']['unavailable']} 个已纳入跟踪的实体处于 unavailable/unknown")
    if overview["open_covers"]:
        alerts.append(f"打开中的帘类/晾衣架：{'、'.join(x['name'] for x in overview['open_covers'])}")
    if summary["critical_binary_sensors"]:
        alerts.append(f"触发中的关键传感器：{'、'.join(x['name'] for x in summary['critical_binary_sensors'])}")
    if summary["focus_alerts"]:
        alerts.append("重点设备异常：" + "、".join(x["name"] for x in summary["focus_alerts"][:6]))

    return {
        "home_overview": {
            "lights_on_count": summary["counts"]["lights_on"],
            "climates_active_count": summary["counts"]["climates_active"],
            "fans_on_count": summary["counts"]["fans_on"],
            "covers_open_count": summary["counts"]["covers_open"],
            "headline": summary["brief"]["headline"]
        },
        "lights_status": {
            "focus": focus_views["lights"],
            "currently_on": overview["lights_on"]
        },
        "climate_status": {
            "focus": focus_views["climates"],
            "currently_active": overview["active_climates"],
            "switches_on": focus_views["switches"]
        },
        "fan_status": {
            "focus": focus_views["fans"],
            "currently_on": overview["fans_on"]
        },
        "cover_status": {
            "focus": focus_views["covers"],
            "currently_open": overview["open_covers"]
        },
        "vacuum_status": {
            "focus": focus_views["vacuums"],
            "currently_active": overview["active_vacuums"]
        },
        "environment_status": env,
        "alerts": alerts
    }


def build_summary(states, rules, focus, aliases):
    by_domain = defaultdict(list)
    by_room = defaultdict(lambda: defaultdict(list))
    unavailable = []
    excluded = []
    ignored = []
    env_sensors = []
    critical_binary = []
    critical_keywords = tuple(rules.get("critical_binary_keywords", []))
    priority_domains = set(rules.get("priority_domains", []))

    for item in states:
        entity_id = item.get("entity_id", "")
        domain = entity_id.split(".", 1)[0] if "." in entity_id else "unknown"
        simple = simplify_state(item, aliases)

        if should_exclude(simple, rules):
            excluded.append(concise_item(simple))
            continue
        if domain not in priority_domains:
            ignored.append(concise_item(simple))
            continue
        if not is_relevant(simple, domain, rules, focus):
            ignored.append(concise_item(simple))
            continue

        by_domain[domain].append(simple)
        by_room[simple["room"]][domain].append(simple)

        if simple["state"] in ("unavailable", "unknown"):
            unavailable.append(simple)
        if domain == "sensor" and is_valid_environment(simple, rules, focus):
            env_sensors.append(simple)
        if domain == "binary_sensor":
            text = f"{simple.get('friendly_name', '')} {simple.get('entity_id', '')}".lower()
            if any(k.lower() in text for k in critical_keywords) and str(simple.get("state") or "").lower() in ACTIVE_BINARY_SENSOR_STATES:
                critical_binary.append(simple)

    tracked_pool = (
        by_domain["light"] + by_domain["climate"] + by_domain["fan"] + by_domain["cover"] +
        by_domain["vacuum"] + by_domain["sensor"] + by_domain["binary_sensor"] + by_domain["switch"]
    )

    lights_on = [concise_item(x) for x in by_domain["light"] if x["state"] == "on"]
    climates_active = [concise_item(x) for x in by_domain["climate"] if x["state"] not in ("off", "unavailable", "unknown")]
    fans_on = [concise_item(x) for x in by_domain["fan"] if x["state"] == "on"]
    covers_open = [concise_item(x) for x in by_domain["cover"] if x["state"] not in ("closed", "off", "unavailable", "unknown")]
    vacuums_active = [concise_item(x) for x in by_domain["vacuum"] if x["state"] not in ("docked", "idle", "off", "unavailable", "unknown")]
    switches_on = [concise_item(x) for x in by_domain["switch"] if x["state"] == "on"][:20]

    room_summary = {}
    for room, domains in by_room.items():
        room_summary[room] = {
            "lights_on": [x["friendly_name"] for x in domains.get("light", []) if x["state"] == "on"],
            "active_climates": [x["friendly_name"] for x in domains.get("climate", []) if x["state"] not in ("off", "unavailable", "unknown")],
            "fans_on": [x["friendly_name"] for x in domains.get("fan", []) if x["state"] == "on"],
            "open_covers": [x["friendly_name"] for x in domains.get("cover", []) if x["state"] not in ("closed", "off", "unavailable", "unknown")]
        }

    focus_views = {group: pick_focus(tracked_pool, focus[group]) for group in FOCUS_GROUPS}
    focus_alerts = build_focus_alerts(focus_views)

    summary = {
        "generated_at": utc_now_iso(),
        "freshness": rules.get("freshness", {}),
        "counts": {
            "total_entities": len(states),
            "excluded_entities": len(excluded),
            "ignored_entities": len(ignored),
            "tracked_lights": len(by_domain["light"]),
            "lights_on": len(lights_on),
            "tracked_climates": len(by_domain["climate"]),
            "climates_active": len(climates_active),
            "tracked_fans": len(by_domain["fan"]),
            "fans_on": len(fans_on),
            "tracked_switches": len(by_domain["switch"]),
            "switches_on": len(switches_on),
            "tracked_covers": len(by_domain["cover"]),
            "covers_open": len(covers_open),
            "tracked_vacuums": len(by_domain["vacuum"]),
            "vacuums_active": len(vacuums_active),
            "unavailable": len(unavailable),
            "environment_sensors": len(env_sensors),
            "critical_binary_sensors": len(critical_binary),
            "focus_alerts": len(focus_alerts)
        },
        "overview": {
            "lights_on": lights_on,
            "active_climates": climates_active,
            "fans_on": fans_on,
            "switches_on": switches_on,
            "open_covers": covers_open,
            "active_vacuums": vacuums_active
        },
        "focus": focus_views,
        "focus_alerts": focus_alerts,
        "rooms": room_summary,
        "environment_sensors": [concise_item(x) for x in env_sensors[:20]],
        "critical_binary_sensors": [concise_item(x) for x in critical_binary[:20]],
        "unavailable_entities": [concise_item(x) for x in unavailable[:30]],
        "excluded_examples": excluded[:20],
        "ignored_examples": ignored[:20]
    }
    return summary


def build_brief(summary):
    counts = summary["counts"]
    focus = summary["focus"]
    lines = []

    on_lights = [x["name"] for x in focus["lights"] if x["state"] == "on"]
    if on_lights:
        lines.append(f"重点灯光当前开启：{'、'.join(on_lights)}")
    else:
        lines.append("重点灯光当前都关着")

    active_climates = [x["name"] for x in focus["climates"] if x["state"] not in ("off", "unavailable", "unknown")]
    if active_climates:
        lines.append(f"重点空调运行中：{'、'.join(active_climates)}")
    else:
        lines.append("重点空调当前都没在运行")

    active_fans = [x["name"] for x in focus["fans"] if x["state"] == "on"]
    if active_fans:
        lines.append(f"重点风扇运行中：{'、'.join(active_fans)}")
    else:
        lines.append("重点风扇当前都没在运行")

    open_covers = [x["name"] for x in focus["covers"] if x["state"] not in ("closed", "off", "unavailable", "unknown")]
    if open_covers:
        lines.append(f"重点帘类/晾衣架当前打开：{'、'.join(open_covers)}")

    env_items = focus["environment"] or summary["environment_sensors"]
    if env_items:
        env_parts = [f"{x['name']} {x['state']}{x.get('unit') or ''}" for x in env_items[:6]]
        lines.append("环境数据：" + "；".join(env_parts))

    if summary["focus_alerts"]:
        names = "、".join(x["name"] for x in summary["focus_alerts"][:6])
        lines.append(f"重点设备异常：{names}")

    if summary["unavailable_entities"]:
        names = "、".join(x["name"] for x in summary["unavailable_entities"][:5])
        lines.append(f"当前仍有 {counts['unavailable']} 个已纳入跟踪的实体 unavailable/unknown，示例：{names}")
    else:
        lines.append("当前已纳入跟踪的实体里没有 unavailable/unknown")

    return {
        "generated_at": summary["generated_at"],
        "freshness": summary.get("freshness", {}),
        "headline": "；".join(lines[:3]),
        "lines": lines
    }


def build_answer_card(summary):
    brief = summary["brief"]
    lines = [
        "# 家中状态速览",
        "",
        f"- 生成时间：{brief['generated_at']}",
        f"- 头条：{brief['headline']}",
        ""
    ]
    for line in brief["lines"]:
        lines.append(f"- {line}")
    if summary.get("answer_views", {}).get("alerts"):
        lines.append("")
        lines.append("## 提醒")
        for alert in summary["answer_views"]["alerts"]:
            lines.append(f"- {alert}")
    return "\n".join(lines) + "\n"


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_entity_args(argv):
    entity_ids = []
    for arg in argv:
        if arg.startswith("--entity-id="):
            entity_ids.append(arg.split("=", 1)[1])
        elif arg == "--entity-id":
            continue
        elif entity_ids and argv[argv.index(arg)-1] == "--entity-id":
            entity_ids.append(arg)
    deduped = []
    seen = set()
    for entity_id in entity_ids:
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            deduped.append(entity_id)
    return deduped


def parse_entity_args_safe(argv):
    entity_ids = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--entity-id" and i + 1 < len(argv):
            entity_ids.append(argv[i + 1])
            i += 2
            continue
        if arg.startswith("--entity-id="):
            entity_ids.append(arg.split("=", 1)[1])
        i += 1
    deduped = []
    seen = set()
    for entity_id in entity_ids:
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            deduped.append(entity_id)
    return deduped


def load_existing_raw_states():
    raw = load_json(RAW_PATH, {}) or {}
    states = raw.get("states") or []
    if not isinstance(states, list):
        return []
    return states


def merge_states(existing_states, updates):
    index = {}
    ordered = []
    for item in existing_states:
        entity_id = item.get("entity_id")
        if not entity_id:
            continue
        index[entity_id] = item
        ordered.append(entity_id)

    for item in updates:
        entity_id = item.get("entity_id")
        if not entity_id:
            continue
        if entity_id not in index:
            ordered.append(entity_id)
        index[entity_id] = item

    return [index[entity_id] for entity_id in ordered if entity_id in index]


def main():
    try:
        base_url, token = load_ha_config()
        rules = load_rules()
        focus = load_focus_entities()
        aliases = load_aliases()
        changed_entity_ids = parse_entity_args_safe(sys.argv[1:])

        refresh_mode = "full"
        states = None
        partial_failures = []

        if changed_entity_ids and os.path.exists(RAW_PATH):
            existing_states = load_existing_raw_states()
            if existing_states:
                refresh_mode = "partial"
                updates = []
                for entity_id in changed_entity_ids:
                    try:
                        updates.append(fetch_state(base_url, token, entity_id))
                    except Exception as e:
                        partial_failures.append({"entity_id": entity_id, "error": str(e)})
                if partial_failures:
                    refresh_mode = "full_fallback"
                    states = fetch_states(base_url, token)
                else:
                    states = merge_states(existing_states, updates)

        if states is None:
            states = fetch_states(base_url, token)
            refresh_mode = "full" if not changed_entity_ids else refresh_mode

        raw = {
            "generated_at": utc_now_iso(),
            "source": "home_assistant_api",
            "base_url": base_url,
            "entity_count": len(states),
            "refresh_mode": refresh_mode,
            "changed_entity_ids": changed_entity_ids,
            "states": states
        }
        summary = build_summary(states, rules, focus, aliases)
        brief = build_brief(summary)
        summary["brief"] = brief
        summary["answer_views"] = build_answer_views(summary, summary["focus"])
        summary["refresh_mode"] = refresh_mode
        summary["changed_entity_ids"] = changed_entity_ids
        if partial_failures:
            summary["partial_failures"] = partial_failures
        card = build_answer_card(summary)
        write_json(RAW_PATH, raw)
        write_json(SUMMARY_PATH, summary)
        write_json(BRIEF_PATH, brief)
        write_text(CARD_PATH, card)
        print(json.dumps({
            "ok": True,
            "raw_path": RAW_PATH,
            "summary_path": SUMMARY_PATH,
            "brief_path": BRIEF_PATH,
            "card_path": CARD_PATH,
            "entity_count": len(states),
            "generated_at": summary["generated_at"],
            "excluded_entities": summary["counts"]["excluded_entities"],
            "ignored_entities": summary["counts"]["ignored_entities"],
            "tracked_unavailable": summary["counts"]["unavailable"],
            "focus_alerts": summary["counts"]["focus_alerts"],
            "refresh_mode": refresh_mode,
            "changed_entity_count": len(changed_entity_ids),
            "partial_failures": partial_failures
        }, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
