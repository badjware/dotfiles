import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";

const DDG_LITE_URL = "https://lite.duckduckgo.com/lite/";
const USER_AGENT = process.env.PI_DDG_USER_AGENT || "pi-search-web/0.5";
const DEFAULT_TIMEOUT_MS = Number(process.env.PI_DDG_TIMEOUT_S || "20") * 1000;
const DEFAULT_MAX_RESULTS = Number(process.env.PI_DDG_DEFAULT_MAX_RESULTS || "5");

const RESULT_RE =
	/<a rel="nofollow" href="(?<href>[^"]+)" class='result-link'>(?<title>[\s\S]*?)<\/a>(?<body>[\s\S]*?)<span class='link-text'>[\s\S]*?<\/span>/g;

const SNIPPET_RE = /<td class='result-snippet'>\s*([\s\S]*?)\s*<\/td>/;

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

function normalizeHref(href: string): string {
	const decodedHref = decodeEntities(href);
	return decodedHref.startsWith("//") ? `https:${decodedHref}` : decodedHref;
}

function isDdgRedirectUrl(url: URL): boolean {
	return url.hostname.endsWith("duckduckgo.com") && url.pathname === "/l/";
}

function unwrapDdgUrl(href: string): string {
	const normalizedHref = normalizeHref(href);
	try {
		const url = new URL(normalizedHref, "https://duckduckgo.com");
		if (!isDdgRedirectUrl(url)) return url.toString();
		const targetUrl = url.searchParams.get("uddg");
		return targetUrl ? decodeURIComponent(targetUrl) : url.toString();
	} catch {
		return normalizedHref;
	}
}

type SearchResult = {
	title: string;
	url: string;
	snippet: string;
};

function dedupeKey(rawUrl: string): string {
	try {
		const url = new URL(rawUrl);
		const path = url.pathname.replace(/\/+$/, "") || "/";
		return `${url.protocol}//${url.hostname.toLowerCase()}${path}${url.search}`;
	} catch {
		return rawUrl;
	}
}

function parseSearchResults(htmlText: string, maxResults: number): SearchResult[] {
	const results: SearchResult[] = [];
	const seen = new Set<string>();
	RESULT_RE.lastIndex = 0;
	let match: RegExpExecArray | null;
	while ((match = RESULT_RE.exec(htmlText)) !== null) {
		const groups = match.groups ?? {};
		const url = unwrapDdgUrl(groups.href || "");
		const title = stripTags(groups.title || "");
		const snippetMatch = (groups.body || "").match(SNIPPET_RE);
		const snippet = stripTags(snippetMatch?.[1] || "");
		if (!/^https?:\/\//.test(url) || !title) continue;
		const key = dedupeKey(url);
		if (seen.has(key)) continue;
		seen.add(key);
		results.push({
			title,
			url,
			snippet,
		});
		if (results.length >= maxResults) break;
	}
	return results;
}

function formatSearchResults(query: string, results: SearchResult[]): string {
	if (results.length === 0) return `No results found for: ${query}`;
	const lines: string[] = [];
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
			description: "Search the web and return ranked results with titles, URLs, and snippets.",
			promptSnippet: "Search the web by query and return titles, URLs, and snippets.",
			promptGuidelines: [
				"Use search_web when the user asks for current, external, or web-based information.",
				"After search_web, use fetch_url on one or two relevant results when snippets are not enough.",
			],
			parameters: Type.Object({
				query: Type.String({ description: "Search query" }),
				max_results: Type.Optional(
					Type.Number({ description: "Maximum number of results to return (default 5, max 10)" }),
				),
			}),
			renderCall(args, theme, _context) {
				return new Text(
					theme.fg("toolTitle", theme.bold("search_web ")) + theme.fg("muted", args.query),
					0,
					0,
				);
			},

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

				const url = new URL(DDG_LITE_URL);
				url.searchParams.set("q", query);

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
