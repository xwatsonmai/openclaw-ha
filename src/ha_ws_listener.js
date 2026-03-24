#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.dirname(path.dirname(__filename));
const WORKSPACE = path.dirname(ROOT);
const DEFAULT_HA_CONFIG = path.join(WORKSPACE, 'skills', 'home-assistant', 'config.json');
const PROJECT_HA_CONFIG = path.join(ROOT, 'config', 'ha.json');
const NOISE_RULES_PATH = path.join(ROOT, 'config', 'ws_noise_rules.json');
const FOCUS_ENTITIES_PATH = path.join(ROOT, 'config', 'focus_entities.json');
const LOG_PATH = path.join(ROOT, 'logs', 'ws_listener.log');
const EVENTS_PATH = path.join(ROOT, 'data', 'recent_events.jsonl');
const SYNC_SCRIPT = path.join(ROOT, 'src', 'sync_snapshot.py');
const PYTHON = process.env.PYTHON_BIN || 'python3';
const DEBOUNCE_MS = Number(process.env.HA_WS_DEBOUNCE_SECONDS || '2') * 1000;
const RECONNECT_MS = Number(process.env.HA_WS_RECONNECT_SECONDS || '5') * 1000;
let lastSyncAt = 0;
let batchTimer = null;
const pendingEntities = new Set();
const lastEntityAcceptedAt = new Map();

function ensureDirs() {
  fs.mkdirSync(path.join(ROOT, 'logs'), { recursive: true });
  fs.mkdirSync(path.join(ROOT, 'data'), { recursive: true });
}

function logLine(message) {
  ensureDirs();
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  fs.appendFileSync(LOG_PATH, `[${ts}] ${message}\n`, 'utf8');
}

function appendEvent(event) {
  ensureDirs();
  fs.appendFileSync(EVENTS_PATH, JSON.stringify(event) + '\n', 'utf8');
}

function loadJson(pathName, fallback) {
  if (!fs.existsSync(pathName)) return fallback;
  return JSON.parse(fs.readFileSync(pathName, 'utf8'));
}

function loadHaConfig() {
  if (process.env.HA_URL && process.env.HA_TOKEN) {
    return { url: process.env.HA_URL, token: process.env.HA_TOKEN };
  }
  for (const p of [PROJECT_HA_CONFIG, DEFAULT_HA_CONFIG]) {
    const data = loadJson(p, null);
    if (data && data.url && data.token) return data;
  }
  throw new Error('HA config missing. Set HA_URL/HA_TOKEN or provide config/ha.json');
}

function loadNoiseRules() {
  return loadJson(NOISE_RULES_PATH, {
    ignore_exact_entities: ['sun.sun'],
    ignore_domains: ['sun'],
    ignore_entity_id_keywords: ['indicator_light', 'prompt_tone', 'screen_display_alternate'],
    allow_domains: ['light', 'climate', 'fan', 'cover', 'vacuum', 'sensor', 'binary_sensor', 'switch'],
    focus_first: false,
    per_entity_debounce_seconds: 10,
    batch_window_seconds: 2,
    startup_sync: true,
  });
}

function loadFocusSet() {
  const groups = loadJson(FOCUS_ENTITIES_PATH, {}) || {};
  const ids = new Set();
  for (const values of Object.values(groups)) {
    if (!Array.isArray(values)) continue;
    for (const entityId of values) {
      if (entityId) ids.add(String(entityId).toLowerCase());
    }
  }
  return ids;
}

function httpToWs(url) {
  if (url.startsWith('https://')) return url.replace(/^https:/, 'wss:');
  if (url.startsWith('http://')) return url.replace(/^http:/, 'ws:');
  throw new Error(`unsupported HA url: ${url}`);
}

function normalizeWsUrl(url) {
  return url.endsWith('/api/websocket') ? url : `${url}/api/websocket`;
}

function shouldSync(entityId, rules, focusSet, oldState, newState) {
  if (!entityId) return { ok: false, reason: 'missing_entity_id' };
  if ((oldState ?? null) === (newState ?? null)) return { ok: false, reason: 'same_state' };
  const lower = entityId.toLowerCase();
  const domain = lower.includes('.') ? lower.split('.', 1)[0] : '';
  if ((rules.ignore_exact_entities || []).some(x => x.toLowerCase() === lower)) return { ok: false, reason: 'ignore_exact_entity' };
  if ((rules.ignore_domains || []).some(x => x.toLowerCase() === domain)) return { ok: false, reason: 'ignore_domain' };
  if ((rules.ignore_entity_id_keywords || []).some(x => lower.includes(x.toLowerCase()))) return { ok: false, reason: 'ignore_keyword' };
  const allowDomains = (rules.allow_domains || []).map(x => x.toLowerCase());
  if (allowDomains.length > 0 && !allowDomains.includes(domain)) return { ok: false, reason: 'domain_not_allowed' };

  const focusFirst = Boolean(rules.focus_first);
  if (focusFirst && focusSet.size > 0 && !focusSet.has(lower)) {
    return { ok: false, reason: 'not_in_focus_set' };
  }

  const perEntityDebounceMs = Number(rules.per_entity_debounce_seconds || 0) * 1000;
  if (perEntityDebounceMs > 0) {
    const lastAccepted = lastEntityAcceptedAt.get(lower) || 0;
    const now = Date.now();
    if (now - lastAccepted < perEntityDebounceMs) {
      return { ok: false, reason: 'per_entity_debounce' };
    }
    lastEntityAcceptedAt.set(lower, now);
  }

  return { ok: true, reason: focusSet.has(lower) ? 'focus_entity' : 'allowed_domain' };
}

function triggerSync(reason, entityIds) {
  const now = Date.now();
  if (now - lastSyncAt < DEBOUNCE_MS) {
    logLine(`sync skipped by debounce: reason=${reason} entity_ids=${(entityIds || []).join(',')}`);
    return;
  }
  lastSyncAt = now;
  const result = spawnSync(PYTHON, [SYNC_SCRIPT], {
    cwd: WORKSPACE,
    encoding: 'utf8',
    timeout: 30000,
  });
  logLine(`sync triggered: reason=${reason} entity_count=${(entityIds || []).length} entity_ids=${(entityIds || []).join(',')} rc=${result.status} stdout=${(result.stdout || '').trim()} stderr=${(result.stderr || '').trim()}`);
}

function flushBatch(reason = 'batched_state_changed') {
  if (batchTimer) {
    clearTimeout(batchTimer);
    batchTimer = null;
  }
  const entityIds = Array.from(pendingEntities).sort();
  pendingEntities.clear();
  if (entityIds.length === 0) return;
  triggerSync(reason, entityIds);
}

function scheduleBatch(rules, entityId) {
  pendingEntities.add(entityId);
  const batchWindowMs = Math.max(0, Number(rules.batch_window_seconds || 0) * 1000);
  if (batchWindowMs === 0) {
    flushBatch('state_changed');
    return;
  }
  if (batchTimer) return;
  batchTimer = setTimeout(() => flushBatch('batched_state_changed'), batchWindowMs);
  logLine(`batch scheduled: window_ms=${batchWindowMs} pending_entities=${pendingEntities.size}`);
}

function connect() {
  const { url, token } = loadHaConfig();
  const noiseRules = loadNoiseRules();
  const focusSet = loadFocusSet();
  const wsUrl = normalizeWsUrl(httpToWs(url));
  logLine(`connecting to ${wsUrl}`);
  logLine(`noise rules loaded: focus_first=${Boolean(noiseRules.focus_first)} focus_entities=${focusSet.size} batch_window_seconds=${Number(noiseRules.batch_window_seconds || 0)} per_entity_debounce_seconds=${Number(noiseRules.per_entity_debounce_seconds || 0)}`);
  const ws = new WebSocket(wsUrl);
  let authed = false;

  ws.onopen = () => {
    logLine('socket opened');
  };

  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data.toString());
    } catch (e) {
      logLine(`non-json message: ${String(event.data).slice(0, 200)}`);
      return;
    }

    if (msg.type === 'auth_required') {
      ws.send(JSON.stringify({ type: 'auth', access_token: token }));
      return;
    }
    if (msg.type === 'auth_ok') {
      authed = true;
      logLine('auth ok');
      ws.send(JSON.stringify({ id: 1, type: 'subscribe_events', event_type: 'state_changed' }));
      return;
    }
    if (msg.type === 'auth_invalid') {
      logLine(`auth invalid: ${JSON.stringify(msg)}`);
      ws.close();
      return;
    }
    if (authed && msg.id === 1 && msg.type === 'result') {
      logLine(`subscribe result: ${JSON.stringify(msg)}`);
      if (msg.success && noiseRules.startup_sync !== false) triggerSync('startup', []);
      return;
    }
    if (msg.type !== 'event') return;

    const data = (((msg || {}).event || {}).data || {});
    const entityId = data.entity_id;
    const oldState = (((data || {}).old_state || {}) || {}).state;
    const newState = (((data || {}).new_state || {}) || {}).state;
    appendEvent({ ts: new Date().toISOString(), entity_id: entityId, old_state: oldState, new_state: newState });
    logLine(`state_changed: entity_id=${entityId} old=${oldState} new=${newState}`);

    const decision = shouldSync(entityId, noiseRules, focusSet, oldState, newState);
    if (decision.ok) {
      logLine(`event accepted: entity_id=${entityId} reason=${decision.reason}`);
      scheduleBatch(noiseRules, entityId);
    } else {
      logLine(`event ignored by noise rules: entity_id=${entityId} reason=${decision.reason} old=${oldState} new=${newState}`);
    }
  };

  ws.onerror = (err) => {
    logLine(`socket error: ${err && err.message ? err.message : 'unknown'}`);
  };

  ws.onclose = () => {
    flushBatch('before_reconnect');
    logLine(`socket closed, reconnect in ${RECONNECT_MS}ms`);
    setTimeout(connect, RECONNECT_MS);
  };
}

ensureDirs();
connect();
