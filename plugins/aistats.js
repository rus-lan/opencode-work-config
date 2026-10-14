// aistats opencode plugin (V2, fixed for 2.0.28).
// - non-blocking setup: event loop runs in a detached promise; setup returns cleanup immediately
//   (required by the v2 activation contract — otherwise every prompt hangs).
// - triggers ingest on session.execution.succeeded|failed|interrupted
//   (session.idle is NOT emitted as a stream event in 2.0.28).
// Fire-and-forget: ingest runs detached; any failure is swallowed so the plugin never breaks the host.
import { spawn } from "node:child_process";
import { Plugin } from "@opencode/plugin";

export default Plugin.define({
  id: "aistats",

  setup(ctx) {
    const childSessions = new Set(); // subagent/spawn session ids to skip

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe()) {
          try {
            if (event.type === "session.created") {
              const sid = event.data?.sessionID;
              if (sid && event.data?.parentID) childSessions.add(sid);
            } else if (event.type === "session.deleted") {
              const sid = event.data?.sessionID;
              if (sid) childSessions.delete(sid);
            } else if (
              event.type === "session.execution.succeeded" ||
              event.type === "session.execution.failed" ||
              event.type === "session.execution.interrupted"
            ) {
              const id = event.data?.sessionID;
              if (id && childSessions.has(id)) continue; // skip subagent sessions
              try {
                const proc = spawn("aistats", ["ingest", "--tool", "opencode"], {
                  stdio: "ignore",
                  detached: true,
                });
                proc.unref();
              } catch (e) {
                console.error("[aistats]", e);
              }
            }
          } catch {}
        }
      } catch (e) {
        console.error("[aistats]", e);
      }
    })();

    return () => {}; // non-blocking cleanup — activation completes immediately
  },
});
