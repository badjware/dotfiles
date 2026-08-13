/**
 * Check whether commands exist on the system PATH.
 */

import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const checkCommandTool = defineTool({
	name: "check_command",
	label: "Check Command",
	description:
		"Check whether commands exist on the system PATH. " +
		"Returns a status per command: 'found' (with its resolved path) or 'missing'.",
	parameters: Type.Object({
		commands: Type.Array(Type.String(), {
			description: "Command names to check",
			minItems: 1,
		}),
	}),

	async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
		const statuses = await Promise.all(
			params.commands.map(async (command) => {
				try {
					const { stdout } = await execFileAsync(
						"/bin/bash",
						["-c", 'command -v "$1"', "bash", command],
					);
					return { command, status: "found", path: stdout.trim() };
				} catch {
					return { command, status: "missing", path: null };
				}
			}),
		);

		const text = statuses
			.map((s) =>
				s.status === "found"
					? `${s.command}: found (${s.path})`
					: `${s.command}: missing`,
			)
			.join("\n");
		return {
			content: [{ type: "text", text }],
			details: { statuses },
		};
	},
});

export default function (pi: ExtensionAPI) {
	pi.registerTool(checkCommandTool);
}
