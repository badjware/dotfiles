/**
 * Automatically names a session from its first exchange.
 *
 * After the first agent run completes, this asks a model for a short title
 * built from the opening user and assistant messages, then sets it as the
 * session display name shown in the selector.
 *
 * The model defaults to the current session model. Override it with the
 * PI_SESSION_NAME_MODEL environment variable in "provider/model" format
 * (e.g. "google/gemini-2.5-flash").
 */

import { uuidv7 } from "@earendil-works/pi-ai";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

type ContentBlock = { type?: string; text?: string };

/**
 * Extract plain text from a message content field.
 *
 * content: a message content value, either a string or an array of blocks.
 * Returns the concatenated text of all text blocks, trimmed.
 */
const extractText = (content: unknown): string => {
	if (typeof content === "string") {
		return content.trim();
	}
	if (!Array.isArray(content)) {
		return "";
	}
	const parts: string[] = [];
	for (const part of content) {
		if (part && typeof part === "object") {
			const block = part as ContentBlock;
			if (block.type === "text" && typeof block.text === "string") {
				parts.push(block.text);
			}
		}
	}
	return parts.join("\n").trim();
};

/**
 * Build the first user and assistant text from the current branch.
 *
 * entries: session branch entries as returned by getBranch().
 * Returns the first user message and first assistant reply, or null if either
 * is missing.
 */
const firstExchange = (
	entries: Array<{ type: string; message?: { role?: string; content?: unknown } }>,
): { user: string; assistant: string } | null => {
	let user = "";
	let assistant = "";
	for (const entry of entries) {
		if (entry.type !== "message" || !entry.message?.role) {
			continue;
		}
		const text = extractText(entry.message.content);
		if (!text) {
			continue;
		}
		if (!user && entry.message.role === "user") {
			user = text;
		} else if (user && !assistant && entry.message.role === "assistant") {
			assistant = text;
		}
		if (user && assistant) {
			return { user, assistant };
		}
	}
	return null;
};

/**
 * Resolve the model used to generate the session name.
 *
 * ctx: the extension context providing the model registry and active model.
 * Returns a model with configured auth, or null when none is usable.
 */
const resolveModel = (ctx: ExtensionContext): Model<Api> | null => {
	const override = process.env.PI_SESSION_NAME_MODEL?.trim();
	let model: Model<Api> | undefined;
	if (override) {
		const slash = override.indexOf("/");
		if (slash > 0) {
			model = ctx.modelRegistry.find(override.slice(0, slash), override.slice(slash + 1));
		}
	} else {
		model = ctx.model;
	}
	if (!model || !ctx.modelRegistry.hasConfiguredAuth(model)) {
		return null;
	}
	return model;
};

/**
 * Turn a raw model response into a clean session name.
 *
 * raw: the model's text output.
 * Returns a single-line title stripped of quotes and trailing punctuation,
 * clamped to 60 characters.
 */
const sanitize = (raw: string): string =>
	raw
		.split("\n")[0]
		.trim()
		.replace(/^["'`]+|["'`]+$/g, "")
		.replace(/[.]+$/, "")
		.slice(0, 60)
		.trim();

/**
 * Build the naming prompt from the first exchange.
 *
 * user: the first user message text.
 * assistant: the first assistant reply text.
 * Returns the prompt sent to the naming model.
 */
const buildPrompt = (user: string, assistant: string): string =>
	[
		"Write a concise title for this conversation, 3 to 6 words.",
		"No quotes, no trailing punctuation, no surrounding text.",
		"",
		"<user>",
		user,
		"</user>",
		"<assistant>",
		assistant,
		"</assistant>",
	].join("\n");

export default function (pi: ExtensionAPI) {
	pi.on("agent_end", async (_event, ctx) => {
		if (pi.getSessionName()) {
			return;
		}

		const exchange = firstExchange(ctx.sessionManager.getBranch());
		if (!exchange) {
			return;
		}

		const model = resolveModel(ctx);
		if (!model) {
			return;
		}

		try {
			const response = await ctx.modelRegistry.complete(
				model,
				{
					messages: [
						{
							role: "user",
							content: [{ type: "text", text: buildPrompt(exchange.user, exchange.assistant) }],
							timestamp: Date.now(),
						},
					],
				},
				{ reasoningEffort: "low", cacheRetention: "none", sessionId: uuidv7() },
			);

			const title = sanitize(
				response.content
					.filter((c): c is { type: "text"; text: string } => c.type === "text")
					.map((c) => c.text)
					.join(" "),
			);

			if (title && !pi.getSessionName()) {
				pi.setSessionName(title);
			}
		} catch {
			// Naming is best-effort; ignore model or auth failures.
		}
	});
}
