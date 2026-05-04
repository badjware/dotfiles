/**
 * Logger Extension
 *
 * Logs every agent turn to ~/.pi/logs/<session-id>.log.
 * Each log file corresponds to one session and records:
 *   - Session start / shutdown with timestamps and reason
 *   - User prompts
 *   - Assistant text responses
 *   - Tool calls (name + input) paired with their results, in order
 *   - Stats (token usage + tokens/s) at the end of each turn
 *
 * Log files are named  <date>T<time>_<cwd-basename>.log
 *
 * Ephemeral sessions (--no-session) are never logged.
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

export default function (pi: ExtensionAPI) {
  const logsDir = path.join(os.homedir(), ".pi", "logs");
  try {
    fs.mkdirSync(logsDir, { recursive: true });
  } catch {
    // If we can't create the log directory, the extension degrades silently.
  }

  /** Absolute path to the current session's log file, or null when not logging. */
  let logFile: string | null = null;

  /** User prompt captured in before_agent_start, consumed on turn 0. */
  let pendingPrompt = "";

  /** Tool calls buffered during a turn, flushed paired with results in turn_end. */
  const bufferedToolCalls: Array<{ toolName: string; toolCallId: string; input: unknown }> = [];

  /** Turn start timestamps keyed by turnIndex, for computing tokens/s. */
  const turnStartTimes = new Map<number, number>();

  // ── helpers ──────────────────────────────────────────────────────────────

  function initLogFile(sessionFile: string, cwd: string) {
    if (logFile) return;
    // Session filenames look like: 2026-05-04T15-29-05-769Z_<uuid>.jsonl
    // Extract date+time including milliseconds, drop the UUID entirely.
    const base = path.basename(sessionFile, ".jsonl");
    const dateTime = base.replace(/T(\d{2}-\d{2}-\d{2}-\d+)Z.*/, "T$1");
    const dirName = path.basename(cwd);
    logFile = path.join(logsDir, `${dateTime}_${dirName}.log`);
  }

  function resetState() {
    logFile = null;
    pendingPrompt = "";
    bufferedToolCalls.length = 0;
    turnStartTimes.clear();
  }

  function log(line: string) {
    if (!logFile) return;
    try {
      fs.appendFileSync(logFile, line + "\n");
    } catch {
      // Silently ignore write errors (e.g. disk full) so pi keeps running.
    }
  }

  function ts() {
    return new Date().toISOString();
  }

  function textFromContent(content: unknown): string {
    if (!Array.isArray(content)) return "";
    return (content as Array<{ type?: string; text?: string }>)
      .filter((b) => b.type === "text" && typeof b.text === "string")
      .map((b) => b.text as string)
      .join("\n");
  }

  // ── events ────────────────────────────────────────────────────────────────

  pi.on("session_start", async (event, ctx) => {
    resetState();

    const sessionFile = ctx.sessionManager.getSessionFile();
    if (!sessionFile) return; // ephemeral — nothing to log

    initLogFile(sessionFile, ctx.cwd);

    log(`\n${"=".repeat(80)}`);
    log(`SESSION START  ${ts()}  reason=${event.reason}`);
    if (event.previousSessionFile) {
      log(`Previous: ${event.previousSessionFile}`);
    }
    log(`File: ${sessionFile}`);
    log(`Log:  ${logFile}`);
    log("=".repeat(80));
  });

  pi.on("before_agent_start", (event, _ctx) => {
    pendingPrompt = event.prompt;
  });

  pi.on("turn_start", (event, _ctx) => {
    turnStartTimes.set(event.turnIndex, event.timestamp);
  });

  // Buffer tool calls; they are written paired with results in turn_end.
  pi.on("tool_call", (event, _ctx) => {
    if (!logFile) return; // ephemeral session — skip
    bufferedToolCalls.push({
      toolName: event.toolName,
      toolCallId: event.toolCallId,
      input: event.input,
    });
  });

  pi.on("turn_end", async (event, _ctx) => {
    if (!logFile) return; // ephemeral session — skip

    const { turnIndex, message, toolResults } = event as {
      turnIndex: number;
      message?: {
        content?: unknown;
        usage?: {
          input: number;
          output: number;
          cacheRead: number;
          cacheWrite: number;
          totalTokens: number;
          cost: { total: number };
        };
      };
      toolResults?: Array<{
        toolName?: string;
        toolCallId?: string;
        isError?: boolean;
        content?: unknown;
      }>;
    };

    log(`\n--- Turn ${turnIndex}  [${ts()}] ---`);

    // User prompt (only on the first turn of each agent run)
    if (turnIndex === 0 && pendingPrompt) {
      log(`\nUSER:\n${pendingPrompt}`);
      pendingPrompt = "";
    }

    // Assistant text
    const assistantText = textFromContent(message?.content);
    if (assistantText.trim()) {
      log(`\nASSISTANT:\n${assistantText}`);
    }

    // Tool calls paired with their results, in dispatch order
    if (bufferedToolCalls.length > 0) {
      const resultsByCallId = new Map(
        (toolResults ?? []).map((r) => [r.toolCallId, r])
      );

      for (const call of bufferedToolCalls) {
        log(`\nTOOL CALL: ${call.toolName}  id=${call.toolCallId}`);
        log(JSON.stringify(call.input, null, 2));

        const result = resultsByCallId.get(call.toolCallId);
        if (result) {
          const errTag = result.isError ? " [ERROR]" : "";
          log(`\nTOOL RESULT: ${call.toolName}${errTag}`);
          const text = textFromContent(result.content);
          if (text) {
            const truncated =
              text.length > 3000 ? text.slice(0, 3000) + "\n...[truncated]" : text;
            log(truncated);
          }
        }
      }

      bufferedToolCalls.length = 0;
    }

    // Stats: token usage + tokens/s — always last in the turn
    const usage = message?.usage;
    if (usage) {
      const startTime = turnStartTimes.get(turnIndex);
      const elapsedS = startTime != null ? (Date.now() - startTime) / 1000 : null;
      const tokensPerSec = elapsedS && elapsedS > 0
        ? (usage.output / elapsedS).toFixed(1)
        : null;

      const parts = [
        `in=${usage.input}`,
        `out=${usage.output}`,
        usage.cacheRead > 0 ? `cacheRead=${usage.cacheRead}` : null,
        usage.cacheWrite > 0 ? `cacheWrite=${usage.cacheWrite}` : null,
        `cost=$${usage.cost.total.toFixed(4)}`,
        tokensPerSec != null ? `${tokensPerSec} tok/s` : null,
      ].filter(Boolean).join("  ");

      log(`\nSTATS: ${parts}`);
      turnStartTimes.delete(turnIndex);
    }
  });

  pi.on("session_shutdown", (_event, _ctx) => {
    if (!logFile) return; // ephemeral session — skip
    log(`\nSESSION SHUTDOWN  ${ts()}  reason=${_event.reason}`);
    resetState();
  });
}
