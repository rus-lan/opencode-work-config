/**
 * harness-guards — механические ограничители харнесса (срез телеметрии 09.11.2026).
 * Формат — как у herdr-agent-state.js: голый объект без SDK-импортов.
 *
 * 1. secret-guard      — deny bash/shell/read/edit/write с путями секретов
 *                        (~/.secrets, .zshrc, .env; .env.example разрешён).
 * 2. read-before-edit  — edit/write только для файлов, прочитанных в сессии.
 * 3. cd-repair         — `cd X && rest` автоматически разворачивается в cwd=X,
 *                        command=rest, чтобы попадать под allowlist permissions.
 * 4. marathon-reminder — на каждые 40 тул-вызовов сессии synthetic-напоминание
 *                        про /handoff (марафоны = главный расход токенов).
 * 4b. cedrus-auth      — при ошибке mcp-cedrus «token is expired» сам запускает
 *                        браузерную авторизацию (`opencode2 mcp auth mcp-cedrus`)
 *                        и информирует модель synthetic-сообщением.
 * 5. ast-index-reindex — после git commit/merge/pull фоновый `ast-index update`.
 * 6. model-nudge       — короткое системное напоминание на каждый вызов модели
 *                        (слабые модели выдумывают имена тулов).
 *
 * Не сработавшие точки интеграции (нет sessionID в событии и т.п.) деградируют молча.
 * Проверено по дампу событий 09.11: execute.after несёт sessionID — счётчик валиден.
 */

const HOME = process.env.HOME ?? "~"
// Пути к внешним бинарям переопределяются окружением: у разных установок они разные.
const AST_INDEX = process.env.HARNESS_GUARDS_AST_INDEX ?? `${HOME}/bin/ast-index`
const MARATHON_STEP = 40
// Браузерная OAuth-авторизация remote-MCP: `<cli> mcp auth <server>`.
const AUTH_CLI = process.env.HARNESS_GUARDS_AUTH_CLI ?? `${HOME}/.bun/bin/opencode2`
const CEDRUS_SERVER = process.env.HARNESS_GUARDS_CEDRUS_SERVER ?? "mcp-cedrus"

const SECRET_PATTERNS = [
  /\.secrets?\//,           // ~/.secrets/..., /path/.secret/
  /\.zshrc/,                // .zshrc, .zshrc.bak
  /\.env(?!\.example\b)/,   // .env, .env.local; .env.example пропускаем
]

const isSecretTarget = (s) => SECRET_PATTERNS.some((re) => re.test(s))

// головы команд, которые правило гигиены разрешает даже для секретов (только метаданные)
const SAFE_SECRET_HEADS = new Set(["ls", "wc", "sha256sum", "shasum", "stat"])

const plugin = {
  id: "harness-guards",
  async setup(ctx) {
    const { existsSync } = await import("node:fs")
    const { spawn } = await import("node:child_process")
    const { homedir } = await import("node:os")
    const { resolve: resolvePath } = await import("node:path")

    const readFiles = new Set()   // абсолютные пути, прочитанные/созданные в этой работе сервера
    const busyReindex = new Set() // cwd с уже запущенным reindex
    const busyAuth = new Set()    // MCP-серверы, для которых уже запущен auth-flow
    const steps = new Map()       // sessionID -> счётчик тул-вызовов
    const reminded = new Map()    // sessionID -> следующий порог напоминания
    let lastShell = null          // { cwd, command } последней bash/shell-команды

    const norm = (p) => (typeof p === "string" ? p.replace(/^file:\/\//, "").trim() : "")
    const abs = (p, base) => {
      const s = norm(p)
      if (!s) return ""
      const expanded = s.startsWith("~") ? homedir() + s.slice(1) : s
      try {
        return resolvePath(base ?? process.cwd(), expanded)
      } catch {
        return ""
      }
    }

    // 1) secret-guard + read-before-edit — на уровне permission.evaluate:
    //    deny с message доходит до модели как понятная причина отказа.
    await ctx.permission.hook("evaluate", (event) => {
      const items = (event.resources ?? []).map(norm).filter(Boolean)
      if (!items.length) return

      if (isSecretTarget(items.join("\n"))) {
        // ls/wc/sha256/stat по секретам разрешены правилом гигиены (только метаданные)
        if (event.action === "bash" || event.action === "shell") {
          const head = norm(event.resources?.[0]).split(/\s+/)[0]?.replace(/^.*\//, "")
          if (SAFE_SECRET_HEADS.has(head)) return
        }
        event.effect = "deny"
        event.message =
          "Секреты не читать и не править: только ls/wc -c/sha256/коды ответов. " +
          "Значения подключаются через {file:~/.secrets/<id>} в конфигах."
        return
      }

      if (event.action === "edit" && items[0]) {
        const p = abs(items[0])
        // создание нового файла разрешено; перезапись существующего — только после read
        if (p && existsSync(p) && !readFiles.has(p)) {
          event.effect = "deny"
          event.message =
            "Файл не читался в этой сессии — сначала read, затем edit с точным oldString (не по памяти)."
        }
      }
    })

    // 2) cd-repair + запоминание контекста для reindex
    await ctx.shell.hook("create.before", async (event) => {
      lastShell = { cwd: event.cwd, command: event.command }

      let cmd = typeof event.command === "string" ? event.command : ""
      let cwd = event.cwd
      for (let i = 0; i < 5; i++) {
        const m = cmd.trim().match(/^cd\s+(?:"([^"]*)"|'([^']*)'|([^\s&]+))\s*&&\s*([\s\S]+)$/)
        if (!m) break
        const raw = m[1] ?? m[2] ?? m[3]
        const rest = m[4].trim()
        if (!raw || !rest) break
        const target = abs(raw, cwd)
        if (!target || !existsSync(target)) break
        cwd = target
        cmd = rest
      }
      if (cwd !== event.cwd && cmd && !/^\s*cd(\s|$)/.test(cmd)) {
        event.cwd = cwd
        event.command = cmd
      }
    })

    // 3) учёт прочитанных/созданных файлов
    await ctx.tool.hook("execute.before", (event) => {
      const t = String(event.tool ?? "")
      if (t !== "read" && t !== "write") return
      const p = abs(event.input?.path ?? "")
      if (p) readFiles.add(p)
    })

    // 4) марафон-счётчик + 5) фоновый reindex
    await ctx.tool.hook("execute.after", async (event) => {
      const t = String(event.tool ?? "")
      const sid = event.sessionID ?? event.message?.sessionID

      if (sid && event.status === "completed") {
        const n = (steps.get(sid) ?? 0) + 1
        steps.set(sid, n)
        const nextAt = reminded.get(sid) ?? MARATHON_STEP
        if (n >= nextAt) {
          reminded.set(sid, nextAt + MARATHON_STEP)
          try {
            await ctx.session.synthetic({
              sessionID: sid,
              text:
                `Маратон-контроль: в сессии уже ~${n} тул-вызовов. Если текущий этап закрыт — ` +
                "предложи /handoff в свежий контекст; длинный хвост истории перечитывается моделью каждым ходом.",
            })
          } catch {}
        }
      }

      // 4b) cedrus-auth: протухший OAuth-токен mcp-cedrus → сам запускаем браузерную
      //     авторизацию (аналог `opencode2 mcp auth mcp-cedrus`), модель информируем.
      //     Проверено дампом 09.11: event.error — ОБЪЕКТ (Error), текст в .message;
      //     event.result при ошибке undefined; event.tool = "mcp-cedrus_execute_query".
      if (event.status !== "completed" && t.startsWith(CEDRUS_SERVER) && !busyAuth.has("cedrus")) {
        const e = event.error
        const errRaw =
          (typeof e === "string" ? e : e?.message ?? JSON.stringify(e ?? "")) +
          " " +
          (typeof event.result === "string" ? event.result : JSON.stringify(event.result ?? ""))
        if (/token is expired|token verification failed/i.test(errRaw)) {
          busyAuth.add("cedrus")
          if (sid) {
            try {
              await ctx.session.synthetic({
                sessionID: sid,
                text:
                  `Токен ${CEDRUS_SERVER} протух — запущена браузерная авторизация (mcp auth ${CEDRUS_SERVER}). ` +
                  "Завершите вход в открывшемся окне, затем повторите вызов.",
              })
            } catch {}
          }
          try {
            spawn(AUTH_CLI, ["mcp", "auth", CEDRUS_SERVER], { detached: true, stdio: "ignore" })
              .on("exit", () => {
                const tm = setTimeout(() => busyAuth.delete("cedrus"), 120000)
                tm.unref?.()
              })
              .on("error", () => busyAuth.delete("cedrus"))
              .unref()
          } catch {
            busyAuth.delete("cedrus")
          }
        }
      }

      if (event.status === "completed" && (t === "bash" || t === "shell")) {
        const cmd = lastShell?.command ?? ""
        const cwd = lastShell?.cwd
        if (
          cwd &&
          existsSync(AST_INDEX) &&
          !busyReindex.has(cwd) &&
          /\bgit\s+(commit|merge|pull)\b/.test(cmd)
        ) {
          busyReindex.add(cwd)
          try {
            spawn(AST_INDEX, ["update"], { cwd, detached: true, stdio: "ignore" })
              .on("exit", () => busyReindex.delete(cwd))
              .on("error", () => busyReindex.delete(cwd))
              .unref()
          } catch {
            busyReindex.delete(cwd)
          }
        }
      }
    })

    // 6) model-nudge: короткое системное напоминание на каждый вызов модели
    //    (слабые модели выдумывают имена тулов; для anthropic не инжектим)
    await ctx.session.hook("context", (event) => {
      const prov = String(event?.model?.providerID ?? event?.providerID ?? "")
      if (prov.toLowerCase().includes("anthropic")) return
      event.system?.push({
        type: "text",
        text:
          "Вызывай только существующие тулы; тулы из каталога Code Mode — только внутри execute через tools.* " +
          "(перед незнакомым тулом — search(), это tool_search); перед загрузкой скилла — skill-search \"запрос\". " +
          "subagent из сабагента недоступен (depth=1).",
      })
    })
  },
}

export default plugin
