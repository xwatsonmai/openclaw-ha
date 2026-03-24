#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.dirname(path.dirname(__filename));
const WORKSPACE = path.dirname(ROOT);
const DEFAULT_HA_CONFIG = path.join(WORKSPACE, 'skills', 'home-assistant', 'config.json');
const PROJECT_HA_CONFIG = path.join(ROOT, 'config', 'ha.json');
const NOISE_RULES_PATH = path.join(ROOT, 'config', 'ws_noise_rules.json');
const LOG_PATH = path.join(ROOT, 'logs', 'ws_listener.log');
const EVENTS_PATH = path.join(ROOT, 'data', 'recent_events.jsonl');
const SYNC_SCRIPT = path.join(ROOT, 'src', 'sync_snapshot.py');
const PYTHON = process.env.PYTHON_BIN || 'python3';
const DEBOUNCE_MS = Number(process.env.HA_WS_DEBOUNCE_SECONDS || '2') * 1000;
const RECONNECT_MS = Number(process.env.HA_WS_RECONNECT_SECONDS || '5') * 1000;
let lastSyncAt = 0;

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
  });
}

function httpToWs(url) {
  if (url.startsWith('https://')) return url.replace(/^https:/, 'wss:');
  if (url.startsWith('http://')) return url.replace(/^http:/, 'ws:');
  throw new Error(`unsupported HA url: ${url}`);
}

function normalizeWsUrl(url) {
  return url.endsWith('/api/websocket') ? url : `${url}/api/websocket`;
}

function shouldSync(entityId, rules, oldState, newState) {
  if (!entityId) return false;
  if ((oldState ?? null) === (newState ?? null)) return false;
  const lower = entityId.toLowerCase();
  const domain = lower.includes('.') ? lower.split('.', 1)[0] : '';
  if ((rules.ignore_exact_entities || []).some(x => x.toLowerCase() === lower)) return false;
  if ((rules.ignore_domains || []).some(x => x.toLowerCase() === domain)) return false;
  if ((rules.ignore_entity_id_keywords || []).some(x => lower.includes(x.toLowerCase()))) return false;
  const allowDomains = (rules.allow_domains || []).map(x => x.toLowerCase());
  if (allowDomains.length > 0 && !allowDomains.includes(domain)) return false;
  return true;
}

function triggerSync(reason, entityId) {
  const now = Date.now();
  if (now - lastSyncAt < DEBOUNCE_MS) {
    logLine(`sync skipped by debounce: reason=${reason} entity_id=${entityId || ''}`);
    return;
  }
  lastSyncAt = now;
  const result = spawnSync(PYTHON, [SYNC_SCRIPT], {
    cwd: WORKSPACE,
    encoding: 'utf8',
    timeout: 30000,
  });
  logLine(`sync triggered: reason=${reason} entity_id=${entityId || ''} rc=${result.status} stdout=${(result.stdout || '').trim()} stderr=${(result.stderr || '').trim()}`);
}

function connect() {
  const { url, token } = loadHaConfig();
  const noiseRules = loadNoiseRules();
  const wsUrl = normalizeWsUrl(httpToWs(url));
  logLine(`connecting to ${wsUrl}`);
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
      if (msg.success) triggerSync('startup');
      return;
    }
    if (msg.type !== 'event') return;

    const data = (((msg || {}).event || {}).data || {});
    const entityId = data.entity_id;
    const oldState = (((data || {}).old_state || {}) || {}).state;
    const newState = (((data || {}).new_state || {}) || {}).state;
    appendEvent({ ts: new Date().toISOString(), entity_id: entityId, old_state: oldState, new_state: newState });
    logLine(`state_changed: entity_id=${entityId} old=${oldState} new=${newState}`);

    if (shouldSync(entityId, noiseRules, oldState, newState)) {
      triggerSync('state_changed', entityId);
    } else {
      logLine(`event ignored by noise rules: entity_id=${entityId} old=${oldState} new=${newState}`);
    }
  };

  ws.onerror = (err) => {
    logLine(`socket error: ${err && err.message ? err.message : 'unknown'}`);
  };

  ws.onclose = () => {
    logLine(`socket closed, reconnect in ${RECONNECT_MS}ms`);
    setTimeout(connect, RECONNECT_MS);
  };
}

ensureDirs();
connect();
