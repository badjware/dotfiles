import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";

const DDG_LITE_URL = "https://lite.duckduckgo.com/lite/";
const USER_AGENT = process.env.PI_DDG_USER_AGENT || "pi-search-web/0.4";
const DEFAULT_TIMEOUT_MS = Number(process.env.PI_DDG_TIMEOUT_S || "20") * 1000;
const DEFAULT_MAX_RESULTS = Number(process.env.PI_DDG_DEFAULT_MAX_RESULTS || "5");

const SAFE_SEARCH_MAP: Record<string, string> = {
	off: "-2",
	moderate: "-1",
	strict: "1",
};

const RESULT_RE =
	/<a rel="nofollow" href="(?<href>[^"]+)" class='result-link'>(?<title>[\s\S]*?)<\/a>(?<tail>[\s\S]*?)(?:<td class='result-snippet'>\s*(?<snippet>[\s\S]*?)\s*<\/td>)?(?<tail2>[\s\S]*?)<span class='link-text'>(?<display>[\s\S]*?)<\/span>/g;

const TAG_RE = /<[^>]+>/g;
const WHITESPACE_RE = /[ \t\v\f\r]+/g;

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

function unwrapDdgUrl(href: string): string {
	let decoded = decodeEntities(href);
	if (decoded.startsWith("//")) decoded = `https:${decoded}`;
	try {
		const parsed = new URL(decoded, "https://duckduckgo.com");
		if (parsed.hostname.endsWith("duckduckgo.com") && parsed.pathname === "/l/") {
			const uddg = parsed.searchParams.get("uddg");
			if (uddg) return decodeURIComponent(uddg);
		}
		return parsed.toString();
	} catch {
		return decoded;
	}
}

type SearchResult = {
	title: string;
	url: string;
	display_url: string;
	snippet: string;
};

function parseSearchResults(htmlText: string, maxResults: number): SearchResult[] {
	const results: SearchResult[] = [];
	RESULT_RE.lastIndex = 0;
	let match: RegExpExecArray | null;
	while ((match = RESULT_RE.exec(htmlText)) !== null) {
		const groups = match.groups ?? {};
		const url = unwrapDdgUrl(groups.href || "");
		const title = stripTags(groups.title || "");
		const snippet = stripTags(groups.snippet || "");
		const display = stripTags(groups.display || "");
		if (!/^https?:\/\//.test(url) || !title) continue;
		results.push({
			title,
			url,
			display_url: display || url,
			snippet,
		});
		if (results.length >= maxResults) break;
	}
	return results;
}

function formatSearchResults(query: string, results: SearchResult[]): string {
	if (results.length === 0) return `No DuckDuckGo results found for: ${query}`;
	const lines = [`DuckDuckGo results for: ${query}`, ""];
	results.forEach((result, i) => {
		lines.push(`${i + 1}. ${result.title}`);
		lines.push(`   URL: ${result.url}`);
		if (result.snippet) lines.push(`   Snippet: ${result.snippet}`);
		lines.push("");
	});
	return lines.join("\n").trim();
}

export default function (pi: ExtensionAPI) {
	pi.registerTool(
		defineTool({
			name: "search_web",
			label: "Search Web",
			description: "Search DuckDuckGo and return ranked results with titles, URLs, and snippets.",
			promptSnippet:
				"Search DuckDuckGo for web results by query and return titles, URLs, and snippets.",
			promptGuidelines: [
				"Use search_web when the user asks for current, external, or web-based information.",
				"After search_web, use fetch_url on one or two relevant results when snippets are not enough.",
			],
			parameters: Type.Object({
				query: Type.String({ description: "Search query" }),
				max_results: Type.Optional(
					Type.Number({ description: "Maximum number of results to return (default 5, max 10)" }),
				),
				region: Type.Optional(
					Type.String({ description: "DuckDuckGo region code like us-en or uk-en" }),
				),
				safe_search: Type.Optional(
					Type.String({ description: "Safe search mode: off, moderate, or strict" }),
				),
			}),
			async execute(_toolCallId, params, signal, onUpdate) {
				const query = (params.query || "").trim();
				if (!query) {
					return {
						content: [{ type: "text", text: "search_web requires a non-empty query." }],
						details: {},
						isError: true,
					};
				}

				let maxResults = Math.floor(params.max_results ?? DEFAULT_MAX_RESULTS);
				if (!Number.isFinite(maxResults)) maxResults = DEFAULT_MAX_RESULTS;
				maxResults = Math.max(1, Math.min(10, maxResults));
				const region = (params.region || "").trim();
				const safeSearch = (params.safe_search || "moderate").trim().toLowerCase();

				const url = new URL(DDG_LITE_URL);
				url.searchParams.set("q", query);
				if (region) url.searchParams.set("kl", region);
				if (safeSearch in SAFE_SEARCH_MAP) {
					url.searchParams.set("kp", SAFE_SEARCH_MAP[safeSearch]);
				}

				onUpdate?.({
					content: [{ type: "text", text: `Searching DuckDuckGo for: ${query}` }],
				});

				const timeout = new AbortController();
				const timer = setTimeout(() => timeout.abort(), DEFAULT_TIMEOUT_MS);
				const combined = signal
					? AbortSignal.any([signal, timeout.signal])
					: timeout.signal;

				try {
					const response = await fetch(url.toString(), {
						method: "GET",
						signal: combined,
						headers: { "User-Agent": USER_AGENT },
					});
					if (!response.ok) {
						return {
							content: [
								{
									type: "text",
									text: `DuckDuckGo request failed: HTTP ${response.status} ${response.statusText}`,
								},
							],
							details: { query, status: response.status },
							isError: true,
						};
					}
					const htmlText = await response.text();
					const results = parseSearchResults(htmlText, maxResults);
					const structured = {
						query,
						region: region || null,
						safe_search: safeSearch,
						results,
					};
					return {
						content: [{ type: "text", text: formatSearchResults(query, results) }],
						details: structured,
						isError: false,
					};
				} catch (error) {
					const message = error instanceof Error ? error.message : String(error);
					return {
						content: [{ type: "text", text: `search_web failed: ${message}` }],
						details: { query },
						isError: true,
					};
				} finally {
					clearTimeout(timer);
				}
			},
		}),
	);
}
