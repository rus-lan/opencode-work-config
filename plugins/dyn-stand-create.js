/**
 * dyn-stand-create — механические проверки при создании динамического стенда (dyn/perf).
 * Формат — как у harness-guards.js: голый объект без SDK-импортов.
 *
 * Почему плагин, а не промпт: правила ниже детерминированы (регулярка по строке),
 * а цена ошибки — сломанный стенд или запись в эталон. Модель их помнит, пока помнит.
 *
 * 1. branch-name     — ветка dyn/*|perf/* обязана иметь суффикс [a-z0-9][a-z0-9_-]*;
 *                      слэш/заглавная ломают namespace `<ИС>-<suffix>`, `epic` и метку ветки.
 * 2. stateful-label  — лейбла `stateful/postgres` не существует (правильный `stateful/pgop`);
 *                      со стенда такой MR не поднимет БД, а сервис не стартует.
 * 3. push-to-master  — `git push` стендовой ветки в master/main: стенд живёт открытым MR,
 *                      мердж утаскивает конфигурацию в эталон.
 * 4. mr-draft        — MR стенда всегда Draft; `draft:false` в аргументах — отказ.
 * 5. dyn-test-path   — после записи dyn.yaml/perf.yaml: если в externalSecrets попал путь /test,
 *                      предупреждаем (списки не сливаются, под не стартует). Проверка не блокирует.
 *
 * Пункты 1, 2, 4 работают по тексту аргументов вызова. Для MCP-тулов форма аргументов
 * в permission.evaluate не документирована — поэтому включён probe: он пишет в
 * ~/.cache/opencode/dyn-stand-probe.log форму первых релевантных вызовов (не больше 40 строк),
 * чтобы уточнить матчеры по факту, а не по догадке. Не сработавшие точки деградируют молча.
 */

const DYN_BRANCH = /\b(dyn|perf)\/([^\s"'`,:;)]+)/g
const SUFFIX_OK = /^[a-z0-9][a-z0-9_-]*$/
const DYN_VALUES_FILE = /(?:^|\/)(?:dyn|perf)\.ya?ml$/
const PROBE_LIMIT = 40

const plugin = {
  id: "dyn-stand-create",
  async setup(ctx) {
    const fs = await import("node:fs")
    const path = await import("node:path")
    const os = await import("node:os")

    const probePath = path.join(
      process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache"),
      "opencode",
      "dyn-stand-probe.log",
    )
    const warned = new Set()

    const deny = (event, message) => {
      event.effect = "deny"
      event.message = message
    }

    const parts = (event) =>
      (event.resources ?? []).map((r) => (typeof r === "string" ? r : JSON.stringify(r ?? "")))

    const probe = (action, text) => {
      try {
        fs.mkdirSync(path.dirname(probePath), { recursive: true })
        if (fs.existsSync(probePath) && fs.readFileSync(probePath, "utf8").split("\n").length > PROBE_LIMIT) return
        fs.appendFileSync(probePath, `${new Date().toISOString()}\t${action}\t${text.slice(0, 400).replace(/\n/g, " ")}\n`)
      } catch {}
    }

    // ── 1–4: проверки по аргументам вызова ────────────────────────────────────
    await ctx.permission.hook("evaluate", (event) => {
      const list = parts(event)
      const text = list.join("\n")
      if (!text) return

      const action = String(event.action ?? "")
      const isShell = action === "shell" || action === "bash"
      const cmd = isShell ? (list[0] ?? "") : ""
      const looksGitlab = /merge_request|create_branch|branch|label/i.test(action) || /merge_request|stateful\/|"labels?"/i.test(text)
      if (looksGitlab && !isShell) probe(action, text)

      // Проверяем только то, что действительно управляет стендом: git/glab в shell
      // и вызовы GitLab-MCP. Иначе любая документация или heredoc с примером
      // «неправильной» строки попадает под отказ — это ложное срабатывание.
      const relevant = !isShell || /\b(?:git|glab)\b/.test(cmd)
      if (!relevant) return

      // 1) имя ветки: любой dyn/... или perf/... в аргументах
      for (const m of text.matchAll(DYN_BRANCH)) {
        const suffix = m[2]
        if (!SUFFIX_OK.test(suffix)) {
          deny(
            event,
            `Имя ветки стенда некорректно: «${m[0]}». Суффикс — только латиница в нижнем регистре, цифры, ` +
              "дефис, подчёркивание, без слэшей: он задаёт namespace `<ИС>-<суффикс>`, переменную epic и метку ветки.",
          )
          return
        }
      }

      // 2) несуществующий лейбл
      if (/(?:^|[\s"',:[{])stateful\/postgres(?:$|[\s"',\}\]])/.test(text)) {
        deny(
          event,
          "Лейбла `stateful/postgres` не существует: Postgres живёт в стейтфуле `pgop`. " +
            "Поставь `stateful/pgop`, иначе стейтфул не поднимется и сервис не найдёт БД.",
        )
        return
      }

      // 3) push стендовой ветки в master/main
      if (isShell) {
        if (/\bgit\b[^|;&\n]*\bpush\b/.test(cmd) && /\b(?:master|main)\b/.test(cmd) && /\b(?:dyn|perf)\//.test(cmd)) {
          deny(
            event,
            "Стенд живёт открытым Draft-MR из ветки dyn/*|perf/*; пушить в master/main нельзя — " +
              "это утащит конфигурацию стенда в эталон. Закоммить в ветку стенда и обнови MR.",
          )
          return
        }
      }

      // 4) MR стенда обязан быть Draft
      if (/merge_request/i.test(action) && /["']?draft["']?\s*[:=]\s*false/i.test(text)) {
        deny(
          event,
          "MR стенда создаётся только Draft: открытый не-черновик выглядит готовым к мерджу, " +
            "а мердж dyn/*|perf/* сворачивает или ломает стенд.",
        )
      }
    })

    // ── 5: предупреждение о /test в externalSecrets после записи dyn.yaml ──────
    // execute.after не несёт input, поэтому путь запоминаем на execute.before.
    let lastValuesPath = ""

    await ctx.tool.hook("execute.before", (event) => {
      const t = String(event.tool ?? "")
      if (t !== "write" && t !== "edit") return
      const p = String(event.input?.path ?? "")
      lastValuesPath = DYN_VALUES_FILE.test(p) ? p : ""
    })

    await ctx.tool.hook("execute.after", async (event) => {
      const t = String(event.tool ?? "")
      if (t !== "write" && t !== "edit") return
      const p = String(event.input?.path ?? lastValuesPath)
      lastValuesPath = ""
      if (!DYN_VALUES_FILE.test(p) || warned.has(p)) return
      const sid = event.sessionID ?? event.message?.sessionID

      let body = ""
      try {
        body = fs.readFileSync(p, "utf8")
      } catch {
        return
      }
      const block = body.match(/externalSecrets:[\s\S]{0,2000}?(?=\n\S|\n?$)/)?.[0] ?? ""
      if (!/\/test\b/.test(block)) return

      warned.add(p)
      if (!sid) return
      try {
        await ctx.session.synthetic({
          sessionID: sid,
          text:
            `dyn-stand-create: в ${path.basename(p)} externalSecrets ссылается на путь /test. ` +
            "Со стенда доступны только `/dyn` и `shared/qa/...` — ExternalSecret не прочитается, под не стартует. " +
            "Списки externalSecrets в dyn.yaml заменяются целиком, поэтому проверь блок, а не только отдельные ключи.",
        })
      } catch {}
    })
  },
}

export default plugin
