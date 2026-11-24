/**
 * session-retro — сигналы сессии в JSONL (срез 10.11.2026).
 * Формат — как у harness-guards.js: голый объект без SDK-импортов.
 *
 * Зачем: `/retro` и `/perms` сейчас читают только то, что успело лечь в opencode.db.
 * История «спросили права → ответили once/always/reject» там не сохраняется вовсе,
 * а накопленные «always» дрейфуют мимо конфига. Плагин пишет эту историю сам.
 *
 * Что считает (по сессии, дельтой на каждый session.idle):
 *   calls, разбивка по тулам, ошибки тулов, повторы пары «тул + аргумент»,
 *   запросы прав с ответом (once / always / reject).
 *
 * Куда: ~/.local/share/opencode/retro/sessions.jsonl — одна строка JSON на дельту.
 * Плагин ничего не блокирует и не инжектит в контекст; сбой записи глушится молча.
 *
 * Проверено по типам @opencode-ai/plugin 10.11.2026: tool.execute.after несёт
 * {tool, sessionID, input, status, result|error}; ctx.event.subscribe() — AsyncIterable
 * событий, в манифесте есть permission.asked (data.id), permission.replied
 * (data.requestID, data.reply: once|always|reject) и session.idle (data.sessionID).
 */

const OUT_DIR = `${process.env.HOME ?? "~"}/.local/share/opencode/retro`
const OUT_FILE = `${OUT_DIR}/sessions.jsonl`
const MAX_ERROR_SAMPLES = 20
const MAX_REPEATS = 10
const MAX_PERMISSIONS = 50

const plugin = {
  id: "session-retro",
  async setup(ctx) {
    const fs = await import("node:fs/promises")
    const { mkdirSync } = await import("node:fs")
    const controller = new AbortController()

    const sessions = new Map() // sessionID -> аккумулятор дельты

    const state = (sid) => {
      let s = sessions.get(sid)
      if (!s) {
        s = {
          since: Date.now(),
          calls: 0,
          tools: {},
          errorsTotal: 0,
          errorSamples: [],
          sigs: new Map(),      // сигнатура «тул+аргумент» -> сколько раз
          pending: new Map(),   // requestID -> { action, resources }
          replies: [],          // { action, resource, reply }
        }
        sessions.set(sid, s)
      }
      return s
    }

    // сигнатура вызова: тул + стабильный хэш аргументов (FNV-1a, 32 бита)
    const signature = (tool, input) => {
      let raw = ""
      try {
        raw = JSON.stringify(input ?? null)
      } catch {
        raw = String(input)
      }
      if (raw.length > 400) raw = raw.slice(0, 400)
      const key = `${tool}\u0000${raw}`
      let h = 2166136261
      for (let i = 0; i < key.length; i++) {
        h ^= key.charCodeAt(i)
        h = Math.imul(h, 16777619)
      }
      return `${tool}:${(h >>> 0).toString(16)}`
    }

    const errText = (e) =>
      (typeof e === "string" ? e : e?.message ?? JSON.stringify(e ?? ""))
        .replace(/\s+/g, " ")
        .slice(0, 200)

    await ctx.tool.hook("execute.after", (event) => {
      const sid = event.sessionID
      if (!sid) return
      const s = state(sid)
      const t = String(event.tool ?? "?")

      s.calls += 1
      s.tools[t] = (s.tools[t] ?? 0) + 1

      if (event.status !== "completed") {
        s.errorsTotal += 1
        if (s.errorSamples.length < MAX_ERROR_SAMPLES) {
          s.errorSamples.push({ tool: t, error: errText(event.error) })
        }
      }

      const k = signature(t, event.input)
      s.sigs.set(k, (s.sigs.get(k) ?? 0) + 1)
    })

    const flush = async (sid) => {
      const s = sessions.get(sid)
      if (!s) return
      if (!s.calls && !s.replies.length) {
        sessions.delete(sid)
        return
      }

      const repeats = [...s.sigs.entries()]
        .filter(([, n]) => n > 1)
        .sort((a, b) => b[1] - a[1])
        .slice(0, MAX_REPEATS)
        .map(([sig, n]) => ({ sig, n }))

      const row = {
        at: new Date().toISOString(),
        session: sid,
        directory: ctx.location?.directory ?? "",
        duration_min: Math.round((Date.now() - s.since) / 6000) / 10,
        calls: s.calls,
        tools: s.tools,
        errors: s.errorsTotal,
        error_samples: s.errorSamples,
        repeats,
        permissions: s.replies.slice(0, MAX_PERMISSIONS),
      }

      try {
        mkdirSync(OUT_DIR, { recursive: true })
        await fs.appendFile(OUT_FILE, `${JSON.stringify(row)}\n`, "utf8")
      } catch {
        // запись сигналов не должна ломать сессию
      }
      sessions.delete(sid)
    }

    // permission.asked → permission.replied → session.idle
    void (async () => {
      for await (const ev of ctx.event.subscribe({ signal: controller.signal })) {
        const type = ev?.type
        const data = ev?.data
        if (!type || !data?.sessionID) continue
        const s = state(data.sessionID)

        if (type === "permission.asked") {
          s.pending.set(String(data.id ?? ""), {
            action: String(data.action ?? ""),
            resources: Array.isArray(data.resources) ? data.resources.map(String) : [],
          })
        } else if (type === "permission.replied") {
          const req = s.pending.get(String(data.requestID ?? ""))
          s.pending.delete(String(data.requestID ?? ""))
          s.replies.push({
            action: req?.action ?? "?",
            resource: (req?.resources ?? []).join(" | "),
            reply: String(data.reply ?? "?"),
          })
        } else if (type === "session.idle") {
          await flush(data.sessionID)
        }
      }
    })().catch(() => {})

    return () => controller.abort()
  },
}

export default plugin
