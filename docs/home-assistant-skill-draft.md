# `home-assistant` skill upgrade draft

This document describes how the existing OpenClaw `home-assistant` skill should evolve to work with `openclaw-ha`.

---

## Core idea

Keep **one skill** in OpenClaw:
- `home-assistant`

Keep **one independent integration project**:
- `openclaw-ha`

The skill becomes the decision layer.
The project becomes the capability layer.

---

## Skill responsibilities

The upgraded `home-assistant` skill should handle two request classes:

1. **Real-time control / real-time HA query**
2. **Home awareness / cached state answers powered by `openclaw-ha`**

### Prefer `openclaw-ha` cache first when:
- The user asks for home overview
- The user asks which lights are on
- The user asks whether AC / fan / airer / robot is running
- The user asks for general current home conditions
- The user asks about known focus devices

Read in this order:
1. `data/answer_brief.json`
2. `data/summary.json`
3. `data/answer_card.md`

### Prefer direct Home Assistant calls when:
- The user asks to control a device
- The user explicitly asks for real-time refresh
- The state is safety-critical (locks, security, power)
- The cache is missing or stale
- Cached result conflicts with the user's report

---

## Cache freshness behavior

- If cache is fresh: answer directly
- If cache is slightly stale: answer and mention it is based on recent sync
- If cache is stale: refresh first, then answer

---

## Refresh entrypoints

- One-shot refresh: `./scripts/run_once.sh`
- Cache read: `python3 src/read_cache.py brief|summary|card`
- Listener status: `systemctl --user status openclaw-ha-ws.service`

---

## Fallback

If `openclaw-ha` is unavailable, the skill falls back to direct Home Assistant query/control behavior.

---

## Current implementation status

The current `home-assistant` skill has already been updated in this direction:
- cache-first guidance added
- direct HA fallback kept
- refresh / listener entrypoints documented
- control-after-refresh guidance added

This draft is kept in the repo so future contributors can understand why the skill remains single while the integration project stays separate.
