import { lookup } from "node:dns/promises";
import { gunzipSync, inflateRawSync, inflateSync } from "node:zlib";

import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";

const USER_AGENT = process.env.PI_DDG_USER_AGENT || "pi-fetch-url/0.4";
const DEFAULT_TIMEOUT_MS = Number(process.env.PI_DDG_TIMEOUT_S || "20") * 1000;
const DEFAULT_FETCH_MAX_CHARS = Number(process.env.PI_DDG_DEFAULT_FETCH_MAX_CHARS || "12000");
const MAX_FETCH_BYTES = Number(process.env.PI_DDG_MAX_FETCH_BYTES || `${2 * 1024 * 1024}`);
const ALLOW_PRIVATE = ["1", "true", "yes", "on"].includes(
	(process.env.PI_DDG_ALLOW_PRIVATE || "").toLowerCase(),
);
const MAX_REDIRECTS = 10;

const TITLE_RE = /<title[^>]*>([\s\S]*?)<\/title>/i;
const SCRIPT_STYLE_RE = /<(script|style|noscript|svg)[^>]*>[\s\S]*?<\/\1>/gi;
const TAG_RE = /<[^>]+>/g;
const WHITESPACE_RE = /[ \t\v\f\r]+/g;
const MULTI_NEWLINE_RE = /\n{3,}/g;
const BLOCK_TAG_RE =
	/<\/?(p|div|section|article|main|header|footer|nav|aside|ul|ol|li|table|tr|td|th|h1|h2|h3|h4|h5|h6|blockquote|pre|br)\b[^>]*>/gi;

class PublicUrlError extends Error {}

function decodeEntities(input: string): string {
	return input
		.replace(/&#x([0-9a-fA-F]+);/g, (_m, hex) => {
			try {
				return String.fromCodePoint(parseInt(hex, 16));
			} catch {
				return "";
			}
		})
		.replace(/&#(\d+);/g, (_m, dec) => {
			try {
				return String.fromCodePoint(parseInt(dec, 10));
			} catch {
				return "";
			}
		})
		.replace(/&nbsp;/gi, " ")
		.replace(/&amp;/gi, "&")
		.replace(/&lt;/gi, "<")
		.replace(/&gt;/gi, ">")
		.replace(/&quot;/gi, '"')
		.replace(/&apos;/gi, "'");
}

function stripTags(value: string): string {
	return decodeEntities(value.replace(TAG_RE, "")).replace(WHITESPACE_RE, " ").trim();
}

function normalizeText(value: string): string {
	const cleaned = value.replace(/\xa0/g, " ");
	const lines: string[] = [];
	for (const raw of cleaned.split("\n")) {
		const line = raw.replace(WHITESPACE_RE, " ").trim();
		if (line) lines.push(line);
		else if (lines.length > 0 && lines[lines.length - 1] !== "") lines.push("");
	}
	return lines.join("\n").replace(MULTI_NEWLINE_RE, "\n\n").trim();
}

function htmlToText(htmlText: string): { title: string | null; text: string } {
	const titleMatch = TITLE_RE.exec(htmlText);
	const title = titleMatch ? stripTags(titleMatch[1]) : null;
	let cleaned = htmlText.replace(SCRIPT_STYLE_RE, " ");
	// Insert newlines around block-level tags and <br>
	cleaned = cleaned.replace(BLOCK_TAG_RE, "\n");
	// Strip remaining tags
	cleaned = cleaned.replace(TAG_RE, "");
	cleaned = decodeEntities(cleaned);
	return { title, text: normalizeText(cleaned) };
}

async function validatePublicUrl(rawUrl: string): Promise<URL> {
	let parsed: URL;
	try {
		parsed = new URL(rawUrl);
	} catch {
		throw new PublicUrlError("Invalid URL.");
	}
	if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
		throw new PublicUrlError("Only http and https URLs are allowed.");
	}
	if (!parsed.hostname) throw new PublicUrlError("URL must include a hostname.");
	if (parsed.username || parsed.password) {
		throw new PublicUrlError("Embedded credentials in URLs are not allowed.");
	}
	if (ALLOW_PRIVATE) return parsed;
	const host = parsed.hostname.toLowerCase();
	if (host === "localhost") throw new PublicUrlError("Localhost URLs are blocked.");
	let infos: Array<{ address: string; family: number }>;
	try {
		infos = await lookup(parsed.hostname, { all: true });
	} catch (error) {
		throw new PublicUrlError(`Could not resolve hostname: ${parsed.hostname}`);
	}
	for (const { address } of infos) {
		if (isBlockedAddress(address)) {
			throw new PublicUrlError(`Blocked non-public address: ${parsed.hostname} -> ${address}`);
		}
	}
	return parsed;
}

function isBlockedAddress(addr: string): boolean {
	// IPv4
	if (/^\d{1,3}(\.\d{1,3}){3}$/.test(addr)) {
		const parts = addr.split(".").map((p) => Number(p));
		if (parts.some((n) => Number.isNaN(n) || n < 0 || n > 255)) return true;
		const [a, b] = parts;
		// loopback 127/8, private 10/8, 172.16/12, 192.168/16, link-local 169.254/16,
		// multicast 224/4, reserved 240/4, 0/8, CGNAT 100.64/10
		if (a === 0) return true;
		if (a === 10) return true;
		if (a === 127) return true;
		if (a === 169 && b === 254) return true;
		if (a === 172 && b >= 16 && b <= 31) return true;
		if (a === 192 && b === 168) return true;
		if (a === 100 && b >= 64 && b <= 127) return true;
		if (a >= 224) return true;
		return false;
	}
	// IPv6
	const lower = addr.toLowerCase();
	if (lower === "::" || lower === "::1") return true;
	if (lower.startsWith("fe80:") || lower.startsWith("fc") || lower.startsWith("fd")) return true;
	if (lower.startsWith("ff")) return true; // multicast
	// IPv4-mapped
	const mapped = lower.match(/^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/);
	if (mapped) return isBlockedAddress(mapped[1]);
	return false;
}

function maybeDecompress(body: Buffer, encoding: string): Buffer {
	const enc = encoding.toLowerCase();
	try {
		if (enc === "gzip") return gunzipSync(body);
		if (enc === "deflate") {
			try {
				return inflateSync(body);
			} catch {
				return inflateRawSync(body);
			}
		}
	} catch {
		// Fall through and return raw body
	}
	return body;
}

function getCharset(contentType: string | null): string {
	if (!contentType) return "utf-8";
	const m = /charset=([^;]+)/i.exec(contentType);
	return (m ? m[1].trim().replace(/^["']|["']$/g, "") : "utf-8") || "utf-8";
}

async function fetchBytes(
	initialUrl: string,
	signal: AbortSignal | undefined,
): Promise<{ finalUrl: string; body: Buffer; charset: string }> {
	let currentUrl = (await validatePublicUrl(initialUrl)).toString();
	const timeout = new AbortController();
	const timer = setTimeout(() => timeout.abort(), DEFAULT_TIMEOUT_MS);
	const combined = signal
		? AbortSignal.any([signal, timeout.signal])
		: timeout.signal;
	try {
		for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
			const response = await fetch(currentUrl, {
				method: "GET",
				redirect: "manual",
				signal: combined,
				headers: {
					"User-Agent": USER_AGENT,
					Accept:
						"text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.1",
					"Accept-Encoding": "gzip, deflate",
				},
			});
			if (response.status >= 300 && response.status < 400) {
				const location = response.headers.get("location");
				if (!location) throw new Error(`Redirect (${response.status}) without Location header.`);
				const next = new URL(location, currentUrl).toString();
				await validatePublicUrl(next);
				currentUrl = next;
				continue;
			}
			if (!response.ok) {
				throw new Error(`HTTP ${response.status} ${response.statusText} for ${currentUrl}`);
			}
			const reader = response.body?.getReader();
			const chunks: Buffer[] = [];
			let total = 0;
			if (reader) {
				while (true) {
					const { value, done } = await reader.read();
					if (done) break;
					if (value) {
						chunks.push(Buffer.from(value));
						total += value.byteLength;
						if (total > MAX_FETCH_BYTES) {
							try {
								await reader.cancel();
							} catch {}
							break;
						}
					}
				}
			}
			let body = Buffer.concat(chunks);
			if (body.length > MAX_FETCH_BYTES) body = body.subarray(0, MAX_FETCH_BYTES);
			const encoding = response.headers.get("content-encoding") || "";
			body = maybeDecompress(body, encoding);
			const charset = getCharset(response.headers.get("content-type"));
			return { finalUrl: currentUrl, body, charset };
		}
		throw new Error(`Too many redirects (>${MAX_REDIRECTS}).`);
	} finally {
		clearTimeout(timer);
	}
}

function decodeBody(body: Buffer, charset: string): string {
	try {
		return new TextDecoder(charset, { fatal: false }).decode(body);
	} catch {
		return new TextDecoder("utf-8", { fatal: false }).decode(body);
	}
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
						description: "Maximum number of extracted characters to return (default 12000)",
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
				let maxChars = Math.floor(params.max_chars ?? DEFAULT_FETCH_MAX_CHARS);
				if (!Number.isFinite(maxChars)) maxChars = DEFAULT_FETCH_MAX_CHARS;
				maxChars = Math.max(500, Math.min(100000, maxChars));

				onUpdate?.({ content: [{ type: "text", text: `Fetching URL: ${rawUrl}` }] });

				try {
					const { finalUrl, body, charset } = await fetchBytes(rawUrl, signal);
					const decoded = decodeBody(body, charset);
					const stripped = decoded.replace(/^\s+/, "");
					const looksHtml =
						stripped.startsWith("<!DOCTYPE html") ||
						stripped.startsWith("<html") ||
						stripped.slice(0, 5000).toLowerCase().includes("<body");
					let title: string | null = null;
					let text: string;
					if (looksHtml) {
						const extracted = htmlToText(decoded);
						title = extracted.title;
						text = extracted.text;
					} else {
						text = normalizeText(decoded);
					}
					const originalLength = text.length;
					const truncated = originalLength > maxChars;
					if (truncated) text = `${text.slice(0, maxChars - 1).replace(/\s+$/, "")}…`;

					const summaryLines = [`URL: ${finalUrl}`];
					if (title) summaryLines.push(`Title: ${title}`);
					summaryLines.push("");
					summaryLines.push(text || "No readable text content extracted.");

					return {
						content: [{ type: "text", text: summaryLines.join("\n").trim() }],
						details: {
							requested_url: rawUrl,
							final_url: finalUrl,
							title,
							content: text,
							truncated,
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
