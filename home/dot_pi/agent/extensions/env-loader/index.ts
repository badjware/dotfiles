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
 *   KEY="quoted value"
 *   KEY='single quoted'
 *   export KEY=value   # the leading `export` is stripped
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
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

const LOG_PREFIX = "[env-loader]";
const KEY_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

function getConfigPath(): string {
	const baseDir = process.env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent");
	return join(baseDir, "config.env");
}

function isENOENT(err: unknown): boolean {
	return (err as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
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

		let value = line.slice(eq + 1).trim();

		// Strip matching surrounding quotes (requires length >= 2)
		const isDoubleQuoted =
			value.length >= 2 && value.startsWith('"') && value.endsWith('"');
		const isSingleQuoted =
			value.length >= 2 && value.startsWith("'") && value.endsWith("'");
		if (isDoubleQuoted || isSingleQuoted) {
			value = value.slice(1, -1);
		} else {
			// Strip inline `# comment` for unquoted values
			const hashIdx = value.indexOf(" #");
			if (hashIdx >= 0) value = value.slice(0, hashIdx).trimEnd();
		}

		out[key] = value;
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

function loadEnvFile(path: string): string[] {
	let content: string;
	try {
		content = readFileSync(path, "utf8");
	} catch (err) {
		if (isENOENT(err)) return []; // silent no-op
		const msg = (err as Error)?.message ?? String(err);
		console.warn(`${LOG_PREFIX} Failed to load ${path}: ${msg}`);
		return [];
	}

	warnIfLoosePermissions(path);

	const override = process.env.PI_ENV_LOADER_OVERRIDE === "1";
	const loaded: string[] = [];
	for (const [key, value] of Object.entries(parseEnvFile(content))) {
		if (override || process.env[key] === undefined) {
			process.env[key] = value;
			loaded.push(key);
		}
	}
	return loaded;
}

export default function (pi: ExtensionAPI): void {
	const configPath = getConfigPath();
	const loaded = loadEnvFile(configPath);

	pi.registerCommand("env-loader", {
		description: `Show which env vars were loaded from ${configPath}`,
		handler: async (_args, ctx) => {
			if (loaded.length === 0) {
				ctx.ui.notify(`${LOG_PREFIX} no vars loaded from ${configPath}`, "info");
				return;
			}
			ctx.ui.notify(
				`${LOG_PREFIX} loaded ${loaded.length} var(s) from ${configPath}: ${loaded.join(", ")}`,
				"info",
			);
		},
	});
}
