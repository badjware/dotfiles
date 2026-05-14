import { spawn } from "node:child_process";

import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";

const TIMEOUT_S = Number(process.env.PI_FETCH_TIMEOUT_S || "20");
const WIDTH = Number(process.env.PI_FETCH_WIDTH || "1024");
const DEFAULT_MAX_CHARS = Number(process.env.PI_FETCH_DEFAULT_MAX_CHARS || "32000");

interface LynxResult {
	stdout: string;
	stderr: string;
	code: number | null;
}

function runLynx(url: string, includeLinks: boolean, signal?: AbortSignal): Promise<LynxResult> {
	return new Promise((resolve, reject) => {
		const args = [
			"-dump",
			"-nostatus",
			"-noreferer",
			`-width=${WIDTH}`,
			"-display_charset=utf-8",
			"-assume_charset=utf-8",
			`-connect_timeout=${TIMEOUT_S}`,
			`-read_timeout=${TIMEOUT_S}`,
		];
		if (!includeLinks) args.push("-nolist");
		args.push(url);

		let proc;
		try {
			proc = spawn("lynx", args, { signal });
		} catch (error) {
			reject(error);
			return;
		}
		let stdout = "";
		let stderr = "";
		proc.stdout.on("data", (chunk) => {
			stdout += chunk.toString("utf-8");
		});
		proc.stderr.on("data", (chunk) => {
			stderr += chunk.toString("utf-8");
		});
		proc.on("error", (error) => {
			const err = error as NodeJS.ErrnoException;
			if (err.code === "ENOENT") {
				reject(
					new Error(
						"lynx not found on PATH. Install it (e.g. `apt install lynx` or `brew install lynx`).",
					),
				);
				return;
			}
			reject(error);
		});
		proc.on("close", (code) => resolve({ stdout, stderr, code }));
	});
}

export default function (pi: ExtensionAPI) {
	pi.registerTool(
		defineTool({
			name: "fetch_url",
			label: "Fetch URL",
			description: "Fetch a public web page and extract readable text content.",
			promptSnippet: "Fetch a public URL and extract readable page text.",
			promptGuidelines: [
				"Use fetch_url to read a public web page after search_web finds a relevant result or when the user gives a public URL.",
				"Use fetch_url only for public http or https URLs; do not use it for local, private, or internal network targets.",
			],
			parameters: Type.Object({
				url: Type.String({ description: "Public http or https URL to fetch" }),
				max_chars: Type.Optional(
					Type.Number({
						description: `Maximum number of extracted characters to return (default ${DEFAULT_MAX_CHARS})`,
					}),
				),
				include_links: Type.Optional(
					Type.Boolean({
						description:
							"Append the numbered list of page links at the end (default false). Enable when you intend to follow links.",
					}),
				),
			}),
			async execute(_toolCallId, params, signal, onUpdate) {
				const rawUrl = (params.url || "").trim();
				if (!rawUrl) {
					return {
						content: [{ type: "text", text: "fetch_url requires a non-empty url." }],
						details: {},
						isError: true,
					};
				}
				if (!/^https?:\/\//i.test(rawUrl)) {
					return {
						content: [
							{ type: "text", text: "fetch_url only accepts http or https URLs." },
						],
						details: { requested_url: rawUrl },
						isError: true,
					};
				}

				let maxChars = Math.floor(params.max_chars ?? DEFAULT_MAX_CHARS);
				if (!Number.isFinite(maxChars)) maxChars = DEFAULT_MAX_CHARS;
				maxChars = Math.max(500, Math.min(100000, maxChars));
				const includeLinks = params.include_links ?? false;

				onUpdate?.({ content: [{ type: "text", text: `Fetching URL: ${rawUrl}` }] });

				try {
					const { stdout, stderr, code } = await runLynx(rawUrl, includeLinks, signal);
					if (code !== 0 && !stdout.trim()) {
						const message = stderr.trim() || `lynx exited with code ${code}`;
						return {
							content: [{ type: "text", text: message }],
							details: { requested_url: rawUrl, exit_code: code },
							isError: true,
						};
					}

					let text = stdout
						.replace(/\r\n/g, "\n")
						.replace(/\(BUTTON\) ?/g, "")
						.replace(/_{4,}/g, "")
						.replace(/^[ \t]+$/gm, "")
						.replace(/\n{3,}/g, "\n\n")
						.trim();
					const originalLength = text.length;
					const truncated = originalLength > maxChars;
					if (truncated) text = `${text.slice(0, maxChars - 1).replace(/\s+$/, "")}…`;

					const summary = [`URL: ${rawUrl}`, "", text || "No readable text extracted."]
						.join("\n")
						.trim();

					return {
						content: [{ type: "text", text: summary }],
						details: {
							requested_url: rawUrl,
							content: text,
							truncated,
							original_length: originalLength,
						},
						isError: false,
					};
				} catch (error) {
					const message = error instanceof Error ? error.message : String(error);
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
