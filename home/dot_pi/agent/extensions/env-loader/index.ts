/**
 * env-loader
 *
 * Loads environment variables from `<pi-config-dir>/config.env` and injects
 * them into `process.env` at extension load time, so any child process started
 * by pi (bash tool, skill scripts, etc.) inherits them.
 *
 * The config directory follows pi's own convention:
 *   - `$PI_CODING_AGENT_DIR` if set
 *   - otherwise `~/.pi/agent`
 *
 * File format: dotenv-style
 *   # comments allowed
 *   KEY=value
 *   KEY="quoted value"          # supports \n \r \t \\ \" escapes
 *   KEY='single quoted'         # taken literally, no escapes
 *   KEY="multi
 *   line"                       # quoted values may span lines
 *   export KEY=value            # leading `export` is stripped
 *   KEY=value # trailing        # inline comments stripped (unquoted only)
 *
 * Behavior:
 *   - Existing process.env values are NOT overwritten (so a real shell export
 *     still wins). Set PI_ENV_LOADER_OVERRIDE=1 to reverse this.
 *   - Missing file is a silent no-op.
 *   - Malformed lines are skipped with a warning.
 *   - If the file is world- or group-readable, a warning is printed
 *     (tokens likely live there). Recommended: chmod 600.
 */

import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const LOG_PREFIX = "[env-loader]";
const KEY_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

interface LoadResult {
	/** Keys actually written to process.env. */
	loaded: string[];
	/** Keys present in the file but skipped because already set in process.env. */
	skipped: string[];
}

function getConfigPath(): string {
	const baseDir = process.env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent");
	return join(baseDir, "config.env");
}

function isENOENT(err: unknown): boolean {
	return (err as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
}

function unescapeDoubleQuoted(s: string): string {
	return s.replace(/\\([nrt"\\])/g, (_m, c) => {
		switch (c) {
			case "n":
				return "\n";
			case "r":
				return "\r";
			case "t":
				return "\t";
			default:
				return c; // " or \
		}
	});
}

/**
 * Parse a value starting at lines[i].slice(start). May consume additional
 * lines if the value opens a quote that closes on a later line.
 * Returns the parsed value and the index of the last line consumed.
 */
function parseValue(
	lines: string[],
	i: number,
	start: number,
): { value: string; endLine: number } | null {
	const first = lines[i].slice(start);
	const trimmed = first.trimStart();
	const leadingWs = first.length - trimmed.length;

	const quote = trimmed[0];
	if (quote === '"' || quote === "'") {
		// Find matching closing quote, possibly on a later line, honoring
		// backslash escapes only inside double quotes.
		let buf = "";
		let j = i;
		let k = start + leadingWs + 1; // position after opening quote
		while (j < lines.length) {
			const line = lines[j];
			while (k < line.length) {
				const ch = line[k];
				if (quote === '"' && ch === "\\" && k + 1 < line.length) {
					buf += line[k] + line[k + 1];
					k += 2;
					continue;
				}
				if (ch === quote) {
					// Found closing quote. Trailing junk after it is ignored
					// only if it's whitespace or a `# comment`.
					const rest = line.slice(k + 1).trim();
					if (rest && !rest.startsWith("#")) return null; // malformed
					const raw = buf;
					const value = quote === '"' ? unescapeDoubleQuoted(raw) : raw;
					return { value, endLine: j };
				}
				buf += ch;
				k += 1;
			}
			// reached end of line without closing quote: include newline, continue
			buf += "\n";
			j += 1;
			k = 0;
		}
		return null; // unterminated quote
	}

	// Unquoted: strip inline `\s#...` comment, then trim.
	let value = trimmed;
	const m = value.match(/\s#/);
	if (m && m.index !== undefined) value = value.slice(0, m.index);
	return { value: value.trim(), endLine: i };
}

function parseEnvFile(content: string): Record<string, string> {
	const out: Record<string, string> = {};
	const lines = content.split(/\r?\n/);

	for (let i = 0; i < lines.length; i++) {
		const rawLine = lines[i];
		let line = rawLine.trim();
		if (!line || line.startsWith("#")) continue;

		// Allow `export FOO=bar`
		if (line.startsWith("export ")) line = line.slice("export ".length).trimStart();

		const eq = line.indexOf("=");
		if (eq <= 0) {
			console.warn(`${LOG_PREFIX} Skipping malformed line ${i + 1}: ${rawLine}`);
			continue;
		}

		const key = line.slice(0, eq).trim();
		if (!KEY_RE.test(key)) {
			console.warn(`${LOG_PREFIX} Skipping invalid key on line ${i + 1}: ${key}`);
			continue;
		}

		// Re-parse the value from the original line so multi-line quoted values
		// can find their continuation in `lines`. Keys can't contain `=`, so the
		// first `=` in rawLine is the assignment separator.
		const valueStart = rawLine.indexOf("=") + 1;
		const parsed = parseValue(lines, i, valueStart);
		if (!parsed) {
			console.warn(`${LOG_PREFIX} Skipping malformed value on line ${i + 1}: ${rawLine}`);
			continue;
		}

		if (Object.prototype.hasOwnProperty.call(out, key)) {
			console.warn(`${LOG_PREFIX} Duplicate key on line ${i + 1}, overwriting: ${key}`);
		}
		out[key] = parsed.value;
		i = parsed.endLine;
	}
	return out;
}

function warnIfLoosePermissions(path: string): void {
	let st: ReturnType<typeof statSync>;
	try {
		st = statSync(path);
	} catch {
		return; // can't stat, nothing useful to say
	}
	// Any group or other permission bits set.
	if ((st.mode & 0o077) !== 0) {
		const mode = (st.mode & 0o777).toString(8);
		console.warn(
			`${LOG_PREFIX} ${path} is readable by group/other (mode ${mode}). ` +
				`Consider: chmod 600 "${path}"`,
		);
	}
}

function loadEnvFile(path: string): LoadResult {
	let content: string;
	try {
		content = readFileSync(path, "utf8");
	} catch (err) {
		if (isENOENT(err)) return { loaded: [], skipped: [] };
		const msg = (err as Error)?.message ?? String(err);
		console.warn(`${LOG_PREFIX} Failed to load ${path}: ${msg}`);
		return { loaded: [], skipped: [] };
	}

	warnIfLoosePermissions(path);

	const override = process.env.PI_ENV_LOADER_OVERRIDE === "1";
	const loaded: string[] = [];
	const skipped: string[] = [];
	for (const [key, value] of Object.entries(parseEnvFile(content))) {
		if (override || process.env[key] === undefined) {
			process.env[key] = value;
			loaded.push(key);
		} else {
			skipped.push(key);
		}
	}
	return { loaded, skipped };
}

export default function (pi: ExtensionAPI): void {
	const configPath = getConfigPath();
	const initial = loadEnvFile(configPath);

	pi.registerCommand("env-loader", {
		description: `Reload and show env vars from ${configPath}`,
		handler: async (_args, ctx) => {
			// Re-read the file on demand so users can edit and re-check without
			// restarting pi. New vars are applied; already-applied vars are
			// reported as skipped (since they're now set in process.env).
			const result = loadEnvFile(configPath);
			const parts: string[] = [];
			if (result.loaded.length > 0) {
				parts.push(`loaded ${result.loaded.length}: ${result.loaded.join(", ")}`);
			}
			if (result.skipped.length > 0) {
				parts.push(`skipped ${result.skipped.length} (already set): ${result.skipped.join(", ")}`);
			}
			if (parts.length === 0) {
				ctx.ui.notify(`${LOG_PREFIX} no vars in ${configPath}`, "info");
				return;
			}
			const initialNote =
				initial.loaded.length > 0 ? ` [startup loaded ${initial.loaded.length}]` : "";
			ctx.ui.notify(`${LOG_PREFIX} ${parts.join("; ")}${initialNote}`, "info");
		},
	});
}
