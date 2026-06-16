import { spawn } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import http from "node:http";
import https from "node:https";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
  defineTool,
  type ExtensionAPI,
  formatSize,
  truncateHead,
  type TruncationResult,
} from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";

const TIMEOUT_S = Number(process.env.PI_FETCH_TIMEOUT_S || "20");
const USER_AGENT =
  process.env.PI_FETCH_USER_AGENT ||
  "Lynx/2.9.2 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/3.0.14";
const MAX_REDIRECTS = 5;

// We use http/https instead of fetch to evade bot detection
function fetchHtml(url: string, signal?: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    const visit = (current: string, redirectsLeft: number) => {
      let parsed: URL;
      try {
        parsed = new URL(current);
      } catch {
        reject(new Error(`Invalid URL: ${current}`));
        return;
      }
      const lib =
        parsed.protocol === "https:"
          ? https
          : parsed.protocol === "http:"
            ? http
            : null;
      if (!lib) {
        reject(new Error(`Unsupported URL scheme: ${parsed.protocol}`));
        return;
      }

      const req = lib.request(
        parsed,
        {
          method: "GET",
          headers: { "User-Agent": USER_AGENT, Accept: "*/*" },
          signal,
          timeout: TIMEOUT_S * 1000,
        },
        (res) => {
          const status = res.statusCode ?? 0;
          if (status >= 300 && status < 400 && res.headers.location) {
            res.resume();
            if (redirectsLeft <= 0) {
              reject(new Error("Too many redirects"));
              return;
            }
            visit(
              new URL(res.headers.location, current).toString(),
              redirectsLeft - 1,
            );
            return;
          }
          if (status >= 400) {
            res.resume();
            reject(
              new Error(`HTTP ${status} ${res.statusMessage ?? ""}`.trim()),
            );
            return;
          }
          res.setEncoding("utf-8");
          let body = "";
          res.on("data", (chunk) => {
            body += chunk;
          });
          res.on("end", () => resolve(body));
          res.on("error", reject);
        },
      );
      req.on("error", reject);
      req.on("timeout", () =>
        req.destroy(new Error(`Request timed out after ${TIMEOUT_S}s`)),
      );
      req.end();
    };
    visit(url, MAX_REDIRECTS);
  });
}

function runTrafilatura(
  html: string,
  signal?: AbortSignal,
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "trafilatura",
      ["--output-format", "markdown", "--formatting"],
      { signal },
    );
    let stdout = "";
    let stderr = "";
    proc.stdout.setEncoding("utf-8");
    proc.stderr.setEncoding("utf-8");
    proc.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    proc.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    proc.on("error", (error) => {
      const err = error as NodeJS.ErrnoException;
      if (err.code === "ENOENT") {
        reject(
          new Error(
            "trafilatura not found on PATH. Install it (e.g. `pipx install trafilatura`).",
          ),
        );
        return;
      }
      reject(error);
    });
    proc.on("close", (code) => resolve({ stdout, stderr, code }));
    proc.stdin.end(html);
  });
}

export default function (pi: ExtensionAPI) {
  pi.registerTool(
    defineTool({
      name: "fetch_url",
      label: "Fetch URL",
      description: `Fetch a web page and extract readable text content. Output is truncated to ${DEFAULT_MAX_LINES} lines or ${formatSize(DEFAULT_MAX_BYTES)} (whichever is hit first). If truncated, full output is saved to a temp file. Not suitable for structured data (e.g. API responses).`,
      promptSnippet: "Fetch a URL and extract readable page text as Markdown.",
      promptGuidelines: [
        "Use fetch_url to read a web page after search_web finds a relevant result or when the user gives a URL.",
        "Do not use fetch_url to retrieve structured data such as API responses; use bash with curl instead.",
        "fetch_url runs no JavaScript and keeps no session; it returns near-empty text for JavaScript-rendered or login-walled pages. Best for static articles, docs, and READMEs.",
      ],
      parameters: Type.Object({
        url: Type.String({ description: "URL to fetch" }),
      }),
      renderCall(args, theme, _context) {
        return new Text(
          theme.fg("toolTitle", theme.bold("fetch_url ")) +
            theme.fg("muted", args.url),
          0,
          0,
        );
      },

      async execute(_toolCallId, params, signal) {
        const rawUrl = params.url.trim();
        try {
          const html = await fetchHtml(rawUrl, signal);
          const traf = await runTrafilatura(html, signal);
          if (traf.code !== 0 && !traf.stdout.trim()) {
            const message =
              traf.stderr.trim() || `trafilatura exited with code ${traf.code}`;
            return {
              content: [{ type: "text", text: message }],
              details: { requested_url: rawUrl, exit_code: traf.code },
              isError: true,
            };
          }

          const text = traf.stdout
            .replace(/\r\n/g, "\n")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
          if (!text) {
            return {
              content: [{ type: "text", text: "No readable text extracted." }],
              details: { requested_url: rawUrl },
              isError: true,
            };
          }

          const truncation = truncateHead(text, {
            maxLines: DEFAULT_MAX_LINES,
            maxBytes: DEFAULT_MAX_BYTES,
          });

          const details: {
            requested_url: string;
            truncated: boolean;
            truncation?: TruncationResult;
            fullOutputPath?: string;
          } = {
            requested_url: rawUrl,
            truncated: truncation.truncated,
          };

          let resultText = truncation.content;
          if (truncation.truncated) {
            const tempDir = await mkdtemp(join(tmpdir(), "pi-fetch-"));
            const tempFile = join(tempDir, "content.md");
            await writeFile(tempFile, text, "utf8");
            details.truncation = truncation;
            details.fullOutputPath = tempFile;

            const omittedLines = truncation.totalLines - truncation.outputLines;
            resultText += `\n\n[Output truncated: showing ${truncation.outputLines} of ${truncation.totalLines} lines`;
            resultText += ` (${formatSize(truncation.outputBytes)} of ${formatSize(truncation.totalBytes)}).`;
            resultText += ` ${omittedLines} lines omitted.`;
            resultText += ` Full output saved to: ${tempFile}]`;
          }

          return {
            content: [{ type: "text", text: resultText }],
            details,
            isError: false,
          };
        } catch (error) {
          const message =
            error instanceof Error ? error.message : String(error);
          return {
            content: [{ type: "text", text: message }],
            details: { requested_url: rawUrl },
            isError: true,
          };
        }
      },
    }),
  );
}
