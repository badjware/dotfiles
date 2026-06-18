/**
 * pi-claude-bridge
 *
 * Bridges Claude Code assets to pi so they interoperate automatically:
 *
 *  - Slash commands (.claude/commands/**\/*.md, ~/.claude/commands/**\/*.md)
 *      → registered as pi prompt templates (syntax is identical: $ARGUMENTS, $1, etc.)
 *
 *  - Skills (.claude/skills/, ~/.claude/skills/)
 *      → registered as pi skill paths
 *
 *  - CLAUDE.md (CLAUDE.md, ~/.claude/CLAUDE.md)
 *      → injected eagerly into the system prompt
 *
 *  - Rules (.claude/rules/, ~/.claude/rules/)
 *      → injected into the system prompt with read-on-demand links
 *
 *  - /claude-bridge command → show a status report
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Recursively find all .md files under `dir`.
 * Returns paths relative to `dir` (e.g. "subdir/command.md").
 */
function findMarkdownFiles(dir: string, rel = ""): string[] {
	const results: string[] = [];
	if (!fs.existsSync(dir)) return results;

	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const relPath = path.join(rel, entry.name);
		if (entry.isDirectory()) {
			results.push(...findMarkdownFiles(path.join(dir, entry.name), relPath));
		} else if (entry.isFile() && entry.name.endsWith(".md")) {
			results.push(relPath);
		}
	}

	return results;
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export default function claudeBridgeExtension(pi: ExtensionAPI) {
	const home = os.homedir();

	// Populated during resources_discover / before_agent_start; reused by /claude-bridge
	let discoveredSkillPaths: string[] = [];
	let discoveredSkills: { name: string; file: string }[] = [];
	let discoveredCommandFiles: string[] = [];
	let lastInjection: { sections: string[]; chars: number } | null = null;

	function discoverClaudeMd(cwd: string) {
		const globalAgentsMd = path.join(home, ".pi", "agent", "AGENTS.md");
		const globalClaudeMd = path.join(home, ".claude", "CLAUDE.md");
		const piAgentsMdExists = fs.existsSync(globalAgentsMd);
		return {
			skipped: piAgentsMdExists && fs.existsSync(globalClaudeMd) ? globalClaudeMd : null,
			files: [
				...(!piAgentsMdExists ? [globalClaudeMd] : []),
				path.join(cwd, "CLAUDE.md"),
			].filter((p) => fs.existsSync(p)),
		};
	}

	function discoverRules(cwd: string) {
		const entries: string[] = [];
		for (const [rulesDir, prefix] of [
			[path.join(home, ".claude", "rules"), "~/.claude/rules"],
			[path.join(cwd, ".claude", "rules"), ".claude/rules"],
		] as [string, string][]) {
			for (const rel of findMarkdownFiles(rulesDir)) {
				entries.push(`${prefix}/${rel}`);
			}
		}
		return entries;
	}

	// ---------------------------------------------------------------------------
	// resources_discover — register skills and commands (as prompt templates)
	// ---------------------------------------------------------------------------
	pi.on("resources_discover", (event) => {
		const { cwd } = event;
		const skillPaths: string[] = [];
		const promptPaths: string[] = [];

		// ── Skills ──────────────────────────────────────────────────────────────
		const skills: { name: string; file: string }[] = [];
		for (const dir of [
			path.join(home, ".claude", "skills"),
			path.join(cwd, ".claude", "skills"),
		]) {
			if (!fs.existsSync(dir)) continue;
			skillPaths.push(dir);
			for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
				if (!entry.isDirectory()) continue;
				const skillFile = path.join(dir, entry.name, "SKILL.md");
				if (fs.existsSync(skillFile)) skills.push({ name: entry.name, file: skillFile });
			}
		}

		// ── Commands → Prompt templates ──────────────────────────────────────────
		// Claude Code commands use $ARGUMENTS / $1 / $@ – identical to pi templates.
		// Files are enumerated individually so subdirectory commands are included.
		const commandFiles: string[] = [];
		for (const dir of [
			path.join(home, ".claude", "commands"),
			path.join(cwd, ".claude", "commands"),
		]) {
			const files = findMarkdownFiles(dir).map((rel) => path.join(dir, rel));
			commandFiles.push(...files);
			promptPaths.push(...files);
		}

		discoveredSkillPaths = skillPaths;
		discoveredSkills = skills;
		discoveredCommandFiles = commandFiles;

		return { skillPaths, promptPaths };
	});

	// ---------------------------------------------------------------------------
	// before_agent_start — inject CLAUDE.md files and rules into the system prompt
	// ---------------------------------------------------------------------------
	pi.on("before_agent_start", (event, ctx) => {
		const { cwd } = ctx;
		const additions: string[] = [];

		// ── CLAUDE.md — eager injection ──────────────────────────────────────────
		const { files: claudeMdFiles } = discoverClaudeMd(cwd);
		for (const p of claudeMdFiles) {
			const label = p.startsWith(home) ? `~${p.slice(home.length)}` : path.relative(cwd, p);
			const content = fs.readFileSync(p, "utf-8").trim();
			additions.push(`## Instructions from ${label}\n\n${content}`);
		}

		// ── Rules — lazy (list paths, load on demand) ────────────────────────────
		const ruleEntries = discoverRules(cwd);
		if (ruleEntries.length > 0) {
			const list = ruleEntries.map((f) => `- ${f}`).join("\n");
			additions.push(
				`## Project Rules (Claude Code)\n\n` +
				`The following rules are available:\n\n${list}\n\n` +
				`When working on tasks that relate to these rules, use the read tool to load the relevant file(s) before proceeding.`,
			);
		}

		if (additions.length === 0) {
			lastInjection = { sections: [], chars: 0 };
			return;
		}
		const joined = additions.join("\n\n");
		const sections = additions.map((a) => {
			const firstLine = a.split("\n", 1)[0];
			return firstLine.replace(/^##\s+/, "");
		});
		lastInjection = { sections, chars: joined.length };
		return { systemPrompt: event.systemPrompt + "\n\n" + joined };
	});

	// ---------------------------------------------------------------------------
	// /claude-bridge command — show a status report
	// ---------------------------------------------------------------------------
	pi.registerCommand("claude-bridge", {
		description: "Show Claude Code bridge status (commands, skills, rules)",
		handler: (_args, ctx) => {
			const { cwd } = ctx;
			const lines: string[] = ["── Claude Code Interop Status ──────────────────────────"];

			// Commands / Prompt templates
			lines.push("");
			lines.push(`Commands → Prompt templates (${discoveredCommandFiles.length}):`);
			if (discoveredCommandFiles.length === 0) {
				lines.push("  (none — create .md files in .claude/commands/)");
			} else {
				for (const f of discoveredCommandFiles) {
					const rel = f.startsWith(home) ? `~${f.slice(home.length)}` : path.relative(cwd, f);
					lines.push(`  /${path.basename(f, ".md")}  ← ${rel}`);
				}
			}

			// Skills
			lines.push("");
			lines.push(`Skills (${discoveredSkills.length}) from ${discoveredSkillPaths.length} path(s):`);
			if (discoveredSkills.length === 0) {
				lines.push("  (none — create skills in .claude/skills/ or ~/.claude/skills/)");
			} else {
				for (const s of discoveredSkills) {
					const rel = s.file.startsWith(home) ? `~${s.file.slice(home.length)}` : path.relative(cwd, s.file);
					lines.push(`  ${s.name}  ← ${rel}`);
				}
			}

			// CLAUDE.md
			const { files: claudeMdFiles, skipped: skippedClaudeMd } = discoverClaudeMd(cwd);
			lines.push("");
			lines.push(`CLAUDE.md files injected (${claudeMdFiles.length}):`);
			if (claudeMdFiles.length === 0 && !skippedClaudeMd) {
				lines.push("  (none — create CLAUDE.md or ~/.claude/CLAUDE.md)");
			} else {
				for (const p of claudeMdFiles) {
					lines.push(`  ${p.startsWith(home) ? `~${p.slice(home.length)}` : path.relative(cwd, p)}`);
				}
				if (skippedClaudeMd) {
					lines.push("  ~/.claude/CLAUDE.md  (skipped — ~/.pi/agent/AGENTS.md takes precedence)");
				}
			}

			// Rules
			const ruleFiles = discoverRules(cwd);
			lines.push("");
			lines.push(`Rules (${ruleFiles.length}):`);
			if (ruleFiles.length === 0) {
				lines.push("  (none — create .md files in .claude/rules/ or ~/.claude/rules/)");
			} else {
				for (const f of ruleFiles) lines.push(`  ${f}`);
			}

			// System prompt injection
			lines.push("");
			if (lastInjection === null) {
				lines.push("System prompt injection: (agent not started yet)");
			} else if (lastInjection.sections.length === 0) {
				lines.push("System prompt injection: (nothing injected)");
			} else {
				lines.push(`System prompt injection (${lastInjection.chars} chars, ${lastInjection.sections.length} section(s)):`);
				for (const s of lastInjection.sections) lines.push(`  ${s}`);
			}

			lines.push("");
			lines.push("────────────────────────────────────────────────────────");

			ctx.ui.notify(lines.join("\n"), "info");
		},
	});
}
