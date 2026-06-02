import { spawn } from "node:child_process";

import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";

const TIMEOUT_S = Number(process.env.PI_FETCH_TIMEOUT_S || "20");
const WIDTH = Number(process.env.PI_FETCH_WIDTH || "1024");
const DEFAULT_MAX_CHARS = Number(process.env.PI_FETCH_DEFAULT_MAX_CHARS || "32000");
const LONG_LINE_THRESHOLD = Number(process.env.PI_FETCH_LONG_LINE_THRESHOLD || "60");

interface LynxResult {
	stdout: string;
	stderr: string;
	code: number | null;
}

/**
 * Strips leading and trailing "chrome" blocks from lynx text output.
 *
 * Strategy: split the output into blank-line-separated blocks and remove
 * any all-short-line blocks at the head and tail of the document.  Blocks
 * that contain at least one line whose trimmed length meets LONG_LINE_THRESHOLD
 * are considered content and anchor the kept region.
 *
 * Known limitation: very long URLs or legal notices in page footers may
 * extend the kept region slightly into footer territory — acceptable without
 * site-specific keyword matching.
 */
function stripChrome(text: string): string {
	const blocks = text.split(/\n\n+/);

	const hasLongLine = (block: string): boolean =>
		block.split("\n").some((line) => line.trimEnd().length >= LONG_LINE_THRESHOLD);

	let start = 0;
	while (start < blocks.length && !hasLongLine(blocks[start])) start++;

	let end = blocks.length - 1;
	while (end > start && !hasLongLine(blocks[end])) end--;

	// No content blocks found — return as-is rather than an empty string.
	if (start > end) return text;

	return blocks.slice(start, end + 1).join("\n\n");
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
			description: "Fetch a web page and extract readable text content. Not suitable for structured data (e.g. API responses).",
			promptSnippet: "Fetch a URL and extract readable page text.",
			promptGuidelines: [
				"Use fetch_url to read a web page after search_web finds a relevant result or when the user gives a URL.",
				"Do not use fetch_url to retrieve structured data such as API responses; use bash with curl instead.",
			],
			parameters: Type.Object({
				url: Type.String({ description: "URL to fetch" }),
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
				strip_chrome: Type.Optional(
					Type.Boolean({
						description:
							"Remove navigation menus and other short-line boilerplate from the top and bottom of the page (default true). Set to false if the content is unexpectedly truncated or the page layout is unconventional.",
					}),
				),
			}),
			renderCall(args, theme, _context) {
				return new Text(
					theme.fg("toolTitle", theme.bold("fetch_url ")) + theme.fg("muted", args.url),
					0,
					0,
				);
			},

			async execute(_toolCallId, params, signal, onUpdate) {
				const rawUrl = (params.url || "").trim();
				if (!rawUrl) {
					return {
						content: [{ type: "text", text: "fetch_url requires a non-empty url." }],
						details: {},
						isError: true,
					};
				}
				let maxChars = Math.floor(params.max_chars ?? DEFAULT_MAX_CHARS);
				if (!Number.isFinite(maxChars)) maxChars = DEFAULT_MAX_CHARS;
				maxChars = Math.max(500, Math.min(100000, maxChars));
				const includeLinks = params.include_links ?? false;
				const shouldStripChrome = params.strip_chrome ?? true;

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
						// Lynx artifacts: <link>/<a name> rendered as "#word word…" lines
						.replace(/^\s*#\w[^\n]*/gm, "")
						// Lynx artifacts: <button> and <input type="checkbox"> markers
						.replace(/\(BUTTON\) ?/g, "")
						.replace(/\[ ?[Xx]? ?\]/g, "")
						// Lynx artifacts: <input type="text"> and <img> with no alt text
						.replace(/_{4,}/g, "")
						.replace(/\[INLINE\]|\[IMG\]/g, "")
						.replace(/^[ \t]+$/gm, "")
						.replace(/\n{3,}/g, "\n\n")
						.trim();
					if (shouldStripChrome) text = stripChrome(text);
					const originalLength = text.length;
					const truncated = originalLength > maxChars;
					if (truncated) text = `${text.slice(0, maxChars - 1).replace(/\s+$/, "")}…`;

					const summary = text || "No readable text extracted.";

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
