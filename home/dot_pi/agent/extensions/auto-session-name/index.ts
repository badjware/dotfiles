/**
 * Automatically names a session and refreshes the name as it grows.
 *
 * After the first agent run completes, this asks a model for a short title
 * built from the opening user and assistant messages, then sets it as the
 * session display name shown in the selector. Every 5 user turns after that,
 * it asks the model to update the title from the previous title plus only the
 * latest exchange, so the whole conversation never has to be resent.
 *
 * The model defaults to the current session model. Override it with the
 * PI_SESSION_NAME_MODEL environment variable in "provider/model" format
 * (e.g. "google/gemini-2.5-flash").
 */

/** How often (in completed user turns) to refresh the title after the first. */
const REFRESH_EVERY = 5;

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
 * Count completed user turns on the current branch.
 *
 * entries: session branch entries as returned by getBranch().
 * Returns the number of user messages, used as the turn counter so the count
 * survives reloads and session switches.
 */
const countUserTurns = (
	entries: Array<{ type: string; message?: { role?: string } }>,
): number => {
	let turns = 0;
	for (const entry of entries) {
		if (entry.type === "message" && entry.message?.role === "user") {
			turns += 1;
		}
	}
	return turns;
};

/**
 * Build the latest user and assistant text from a run's messages.
 *
 * messages: the messages produced by the agent run that just ended.
 * Returns the last user message and last assistant reply, or null if both
 * are missing.
 */
const latestExchange = (
	messages: Array<{ role?: string; content?: unknown }>,
): { user: string; assistant: string } | null => {
	let user = "";
	let assistant = "";
	for (let i = messages.length - 1; i >= 0; i -= 1) {
		const message = messages[i];
		if (!message?.role) {
			continue;
		}
		const text = extractText(message.content);
		if (!text) {
			continue;
		}
		if (!assistant && message.role === "assistant") {
			assistant = text;
		} else if (!user && message.role === "user") {
			user = text;
		}
		if (user && assistant) {
			break;
		}
	}
	if (!user && !assistant) {
		return null;
	}
	return { user, assistant };
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

/**
 * Build the prompt that refreshes an existing title from the latest exchange.
 *
 * previousTitle: the current session title.
 * user: the latest user message text.
 * assistant: the latest assistant reply text.
 * Returns the prompt sent to the naming model.
 */
const buildUpdatePrompt = (previousTitle: string, user: string, assistant: string): string =>
	[
		"Below is the current title of a conversation and its latest exchange.",
		"Keep the title if it still fits. Otherwise refine it from the new",
		"information, staying at 3 to 6 words.",
		"No quotes, no trailing punctuation, no surrounding text.",
		"",
		"<title>",
		previousTitle,
		"</title>",
		"<user>",
		user,
		"</user>",
		"<assistant>",
		assistant,
		"</assistant>",
	].join("\n");

/**
 * Ask the naming model for a title and return a sanitized result.
 *
 * ctx: the extension context providing the model registry.
 * model: the resolved naming model.
 * prompt: the naming prompt to send.
 * Returns a clean single-line title, or an empty string on failure.
 */
const generateTitle = async (
	ctx: ExtensionContext,
	model: Model<Api>,
	prompt: string,
): Promise<string> => {
	try {
		const response = await ctx.modelRegistry.complete(
			model,
			{
				messages: [
					{
						role: "user",
						content: [{ type: "text", text: prompt }],
						timestamp: Date.now(),
					},
				],
			},
			{ reasoningEffort: "low", cacheRetention: "none", sessionId: uuidv7() },
		);
		return sanitize(
			response.content
				.filter((c): c is { type: "text"; text: string } => c.type === "text")
				.map((c) => c.text)
				.join(" "),
		);
	} catch {
		// Naming is best-effort; ignore model or auth failures.
		return "";
	}
};

export default function (pi: ExtensionAPI) {
	pi.on("agent_end", async (event, ctx) => {
		const currentName = pi.getSessionName();
		const userTurns = countUserTurns(ctx.sessionManager.getBranch());

		const isInitial = !currentName;
		const isRefresh = Boolean(currentName) && userTurns % REFRESH_EVERY === 0;
		if (!isInitial && !isRefresh) {
			return;
		}

		const model = resolveModel(ctx);
		if (!model) {
			return;
		}

		let prompt: string;
		if (isInitial) {
			const exchange = firstExchange(ctx.sessionManager.getBranch());
			if (!exchange) {
				return;
			}
			prompt = buildPrompt(exchange.user, exchange.assistant);
		} else {
			const exchange = latestExchange(event.messages ?? []);
			if (!exchange) {
				return;
			}
			prompt = buildUpdatePrompt(currentName as string, exchange.user, exchange.assistant);
		}

		const title = await generateTitle(ctx, model, prompt);
		if (title) {
			pi.setSessionName(title);
		}
	});
}
