/**
 * Check whether environment variables are set, without revealing their values.
 */

import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const checkEnvTool = defineTool({
	name: "check_env",
	label: "Check Env",
	description:
		"Check whether environment variables are set, without revealing their values. " +
		"Returns a status per name: 'set' or 'unset' (empty values count as unset).",
	parameters: Type.Object({
		names: Type.Array(Type.String(), {
			description: "Environment variable names to check",
			minItems: 1,
		}),
	}),

	async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
		const statuses = params.names.map((name) => {
			const value = process.env[name];
			const status = value ? "set" : "unset";
			return { name, status };
		});

		const text = statuses.map((s) => `${s.name}: ${s.status}`).join("\n");
		return {
			content: [{ type: "text", text }],
			details: { statuses },
		};
	},
});

export default function (pi: ExtensionAPI) {
	pi.registerTool(checkEnvTool);
}
