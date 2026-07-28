// Herdr Agent State Plugin v14 — with get_metrics tool + window title + metrics file
// HERDR_INTEGRATION_ID=opencode
// HERDR_INTEGRATION_VERSION=14

import net from "node:net";
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { tool } from "@opencode-ai/plugin/tool";

const SOURCE = "herdr:opencode";
const AGENT = "opencode";
let reportSeq = Date.now() * 1000;

let lastSessionID = null;
let sessionStartTime = null;
let currentModel = null;
let currentDuration = 0;
let currentTokens = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
let currentCost = 0;
let activeSubagents = 0;
let currentState = null;
let lastReportedState = null;
let lastReportedMsg = null;
let lastWindowTitle = null;
let metadataRefreshInterval = null;
let debounceTimer = null;
const DEBOUNCE_MS = 300;

const METRICS_FILE = join(homedir(), ".config/opencode/metrics.json");
mkdirSync(join(homedir(), ".config/opencode"), { recursive: true });

// ---- helpers ----

function nextSeq() { reportSeq += 1; return reportSeq; }

function fmtDur(ms) {
  if (!ms || ms <= 0) return "0s";
  const s = Math.floor(ms / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m ${s % 60}s`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

function fmtTok(t) {
  if (!t || t <= 0) return "0";
  if (t >= 1_000_000) return `${(t / 1_000_000).toFixed(1)}M`;
  if (t >= 1_000) return `${(t / 1_000).toFixed(0)}K`;
  return t.toString();
}

function fmtCost(c) {
  if (!c || c <= 0) return "$0.00";
  if (c < 0.01) return `$${c.toFixed(4)}`;
  return `$${c.toFixed(2)}`;
}

function extractModel(m) {
  if (!m || typeof m !== "string") return "";
  const parts = m.split("/");
  return parts[parts.length - 1] || m;
}

function buildMetricsObj() {
  const liveDur = currentState === "working" && sessionStartTime ? Date.now() - sessionStartTime : currentDuration;
  return {
    state: currentState,
    model: extractModel(currentModel) || "—",
    duration: fmtDur(liveDur),
    duration_ms: liveDur,
    tokens_input: currentTokens.input,
    tokens_output: currentTokens.output,
    tokens_total: currentTokens.input + currentTokens.output,
    tokens_str: `${fmtTok(currentTokens.input)} / ${fmtTok(currentTokens.output)}`,
    cost: currentCost,
    cost_str: fmtCost(currentCost),
    subagents: activeSubagents,
    session_id: lastSessionID || "",
    timestamp: Date.now(),
  };
}

// ---- Herdr socket ----

function send(method, params) {
  const paneId = process.env.HERDR_PANE_ID;
  const socketPath = process.env.HERDR_SOCKET_PATH;
  if (!paneId || !socketPath) return Promise.resolve();
  const msg = {
    id: `${SOURCE}:${Date.now()}`,
    method,
    params: { pane_id: paneId, source: SOURCE, agent: AGENT, seq: nextSeq(), ...params },
  };
  return new Promise((resolve) => {
    const c = net.createConnection(socketPath, () => { c.write(`${JSON.stringify(msg)}\n`); });
    const done = () => { c.destroy(); resolve(); };
    c.setTimeout(500, done);
    c.on("data", done);
    c.on("error", done);
    c.on("end", done);
    c.on("close", resolve);
  });
}

function reportState(state, sessionID, msg) {
  const p = { state };
  if (sessionID) p.agent_session_id = sessionID;
  if (msg) p.message = msg;
  return send("pane.report_agent", p);
}

function reportSession(sessionID) {
  if (!sessionID) return Promise.resolve();
  return send("pane.report_agent_session", { agent_session_id: sessionID });
}

function setWindowTitle(title) {
  return send("client.window_title.set", { title });
}

function writeMetrics() {
  try { writeFileSync(METRICS_FILE, JSON.stringify(buildMetricsObj(), null, 2)); } catch {}
}

// ---- build status strings ----

function buildHerdrMsg() {
  const parts = [];
  if (activeSubagents > 0) parts.push(`agents:${activeSubagents}`);
  if (currentDuration > 0) parts.push(fmtDur(currentDuration));
  const m = extractModel(currentModel);
  if (m) parts.push(m);
  return parts.join(" | ");
}

function buildWindowTitle() {
  const parts = [];
  if (currentState === "working") parts.push("●");
  else if (currentState === "idle") parts.push("○");
  else if (currentState === "blocked") parts.push("⚠");
  else parts.push("○");
  if (currentDuration > 0) parts.push(fmtDur(currentDuration));
  else if (currentState === "working") parts.push("active");
  if (currentTokens.input > 0 || currentTokens.output > 0)
    parts.push(`${fmtTok(currentTokens.input)}/${fmtTok(currentTokens.output)}`);
  if (currentCost > 0) parts.push(fmtCost(currentCost));
  const m = extractModel(currentModel);
  if (m) parts.push(m);
  return parts.join(" ");
}

function formatMetricsDashboard() {
  const o = buildMetricsObj();
  const icon = o.state === "working" ? "●" : o.state === "idle" ? "○" : o.state === "blocked" ? "⚠" : "○";
  const lines = [];
  lines.push(`${icon} **Status:** ${o.state || "no session"}`);
  lines.push(`⏱ **Duration:** ${o.duration}`);
  lines.push(`📥 **Tokens in:** ${o.tokens_str}`);
  lines.push(`💰 **Cost:** ${o.cost_str}`);
  if (o.subagents > 0) lines.push(`🔄 **Active subagents:** ${o.subagents}`);
  lines.push(`🤖 **Model:** ${o.model}`);
  if (o.session_id) lines.push(`🔗 **Session:** \`${o.session_id}\``);
  const summary = `${icon} ${o.state || "inactive"} | ⏱ ${o.duration} | 📥 ${o.tokens_str} | 💰 ${o.cost_str}${o.subagents > 0 ? ` | agents: ${o.subagents}` : ""} | ${o.model}`;
  return { dashboard: lines.join("\n"), summary, raw: o };
}

// ---- dedup + debounce ----

function pushState(state, sid) {
  const hdrMsg = buildHerdrMsg();
  const winTitle = buildWindowTitle();
  if (state === lastReportedState && hdrMsg === lastReportedMsg && sid === lastSessionID) return;
  lastReportedState = state;
  lastReportedMsg = hdrMsg;
  currentState = state;
  writeMetrics();
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    debounceTimer = null;
    void reportState(state, sid, hdrMsg).catch(() => {});
    if (winTitle !== lastWindowTitle) {
      lastWindowTitle = winTitle;
      void setWindowTitle(`opencode ${winTitle}`).catch(() => {});
    }
  }, DEBOUNCE_MS);
}

// ---- aistats metrics ----

function fetchMetrics() {
  return new Promise((resolve) => {
    const proc = spawn("aistats", ["report", "--format", "json"], { stdio: ["ignore", "pipe", "ignore"] });
    let out = "";
    proc.stdout.on("data", (d) => { out += d.toString(); });
    proc.on("close", (code) => {
      if (code === 0) try { const d = JSON.parse(out); resolve({ tokens: d.tokens || {}, costUsd: d.costUsd || 0, durationMs: d.durationMs || 0 }); } catch { resolve(null); }
      else resolve(null);
    });
    proc.on("error", () => resolve(null));
    setTimeout(() => { proc.kill(); resolve(null); }, 2000);
  });
}

// ---- metadata refresh ----

function startRefresh() {
  if (metadataRefreshInterval) clearInterval(metadataRefreshInterval);
  metadataRefreshInterval = setInterval(async () => {
    if (!lastSessionID) return;
    currentDuration = Date.now() - (sessionStartTime || Date.now());
    const m = await fetchMetrics();
    if (m) { currentTokens = m.tokens || currentTokens; currentCost = m.costUsd || currentCost; }
    pushState("working", lastSessionID);
  }, 10_000);
}

function stopRefresh() {
  if (metadataRefreshInterval) { clearInterval(metadataRefreshInterval); metadataRefreshInterval = null; }
}

// ---- child session tracking ----

const childSessions = new Set();

// ---- plugin export ----

export const HerdrAgentStatePlugin = async () => {
  return {
    // Custom tool: get_metrics — returns live session metrics
    tool: {
      get_metrics: tool({
        description: "Get live session metrics — duration, tokens, cost, subagents, model, status. Returns a markdown dashboard and JSON data. Call this to check session performance.",
        args: {},
        async execute(_args, context) {
          // Try to get model from context if not captured from events
          if (!currentModel && context?.agent) {
            currentModel = context.agent;
          }
          const { dashboard, summary, raw } = formatMetricsDashboard();
          return `## Session Metrics\n\n${dashboard}\n\n**One-liner:** ${summary}\n\n\`\`\`json\n${JSON.stringify(raw, null, 2)}\n\`\`\``;
        },
      }),
    },

    "tool.execute.before": async (input) => {
      try {
        const sid = input?.sessionID;
        if (sid && childSessions.has(sid)) return;
        if (input?.tool === "task") activeSubagents++;
        pushState("working", sid);
      } catch {}
    },

    "tool.execute.after": async (input) => {
      try {
        const sid = input?.sessionID;
        if (sid && childSessions.has(sid)) return;
        if (input?.tool === "task") activeSubagents = Math.max(0, activeSubagents - 1);
        pushState("working", sid);
      } catch {}
    },

    event: async ({ event }) => {
      try {
        const p = event?.properties || {};
        const sid = typeof p?.sessionID === "string" && p.sessionID ? p.sessionID : undefined;

        if (p.parentID || p.info?.parentID) {
          const childID = p.info?.id || sid;
          if (childID) childSessions.add(childID);
        }

        // Extract model from any event that has it
        const eventModel = typeof p.params?.model === "string" ? p.params.model :
                           typeof p.model === "string" ? p.model :
                           typeof p.info?.model === "string" ? p.info.model :
                           typeof p.params?.params?.model === "string" ? p.params.params.model : null;
        if (eventModel) currentModel = eventModel;

        // Extract token/cost data from session events
        const eventTokens = p.tokens || p.params?.tokens || p.info?.tokens;
        if (eventTokens) {
          if (typeof eventTokens.input === "number") currentTokens.input = eventTokens.input;
          if (typeof eventTokens.output === "number") currentTokens.output = eventTokens.output;
        }
        const eventCost = p.cost ?? p.params?.cost ?? p.info?.cost;
        if (typeof eventCost === "number") currentCost = eventCost;

        switch (event?.type) {
          case "session.created": {
            if (sid && childSessions.has(sid)) break;
            lastSessionID = sid;
            sessionStartTime = Date.now();
            currentDuration = 0;
            currentTokens = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
            currentCost = 0;
            activeSubagents = 0;
            lastReportedState = null;
            lastWindowTitle = null;
            startRefresh();
            if (process.env.HERDR_PANE_ID) void reportSession(sid).catch(() => {});
            pushState("working", sid);
            break;
          }

          case "session.updated": {
            // model/tokens/cost already extracted above
            break;
          }

          case "session.idle": {
            stopRefresh();
            if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
            currentDuration = Date.now() - (sessionStartTime || Date.now());
            const m = await fetchMetrics();
            if (m) { currentTokens = m.tokens || currentTokens; currentCost = m.costUsd || 0; if (m.durationMs > 0) currentDuration = m.durationMs; }
            activeSubagents = 0;
            writeMetrics();
            void reportState("idle", sid, "").catch(() => {});
            void setWindowTitle("opencode ○ idle").catch(() => {});
            lastReportedState = "idle";
            lastReportedMsg = "";
            lastWindowTitle = "opencode ○ idle";
            currentState = "idle";
            break;
          }

          case "session.error": {
            stopRefresh();
            if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
            writeMetrics();
            void reportState("blocked", sid, "").catch(() => {});
            void setWindowTitle("opencode ⚠ blocked").catch(() => {});
            lastReportedState = "blocked";
            lastReportedMsg = "";
            lastWindowTitle = "opencode ⚠ blocked";
            currentState = "blocked";
            break;
          }

          case "session.deleted": {
            stopRefresh();
            if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
            if (sid) childSessions.delete(sid);
            if (sid === lastSessionID) {
              lastSessionID = null;
              sessionStartTime = null;
              currentModel = null;
              currentDuration = 0;
              activeSubagents = 0;
              currentState = null;
            }
            break;
          }

          default: break;
        }
      } catch {}
    },
  };
};