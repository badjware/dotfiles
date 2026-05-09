import { streamSimpleOpenAICompletions, type Model } from "@mariozechner/pi-ai";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

type LiteLLMModel = {
	id: string;
	name?: string;
	context_window?: number;
	contextWindow?: number;
	max_context_window?: number;
	max_tokens?: number;
	maxTokens?: number;
	input_modalities?: string[];
	metadata?: Record<string, unknown>;
};

type LiteLLMModelListResponse = {
	data?: LiteLLMModel[];
};

type LiteLLMModelInfoEntry = {
	model_name?: string;
	model_info?: Record<string, unknown>;
};

type LiteLLMModelInfoResponse = {
	data?: LiteLLMModelInfoEntry[];
};

type DiscoveredLiteLLMModel = {
	model: LiteLLMModel;
	modelInfo?: Record<string, unknown>;
};

const providerName = process.env.PI_LITELLM_PROVIDER || "litellm";
const providerLabel = process.env.PI_LITELLM_NAME || "LiteLLM";
const configuredBaseUrl = process.env.LITELLM_BASE_URL;
const authToken = process.env.LITELLM_API_KEY;
const configuredTimeoutMs = process.env.LITELLM_TIMEOUT_MS
	? Number(process.env.LITELLM_TIMEOUT_MS)
	: 10 * 60 * 1000; // 10 minutes
const baseUrl = configuredBaseUrl ? normalizeBaseUrl(configuredBaseUrl) : undefined;
const modelsUrl = baseUrl ? new URL("models", ensureTrailingSlash(baseUrl)).toString() : undefined;
const modelInfoUrl = baseUrl ? new URL("model/info", ensureTrailingSlash(baseUrl)).toString() : undefined;

function normalizeBaseUrl(url: string): string {
	const trimmed = url.trim().replace(/\/+$/, "");
	return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
}

function ensureTrailingSlash(url: string): string {
	return url.endsWith("/") ? url : `${url}/`;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
	return value && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function readNumber(...values: unknown[]): number | undefined {
	for (const value of values) {
		if (typeof value === "number" && Number.isFinite(value)) return value;
		if (typeof value === "string") {
			const parsed = Number(value);
			if (Number.isFinite(parsed)) return parsed;
		}
	}
	return undefined;
}

function readBoolean(...values: unknown[]): boolean | undefined {
	for (const value of values) {
		if (typeof value === "boolean") return value;
		if (typeof value === "string") {
			const normalized = value.trim().toLowerCase();
			if (["1", "true", "yes", "on"].includes(normalized)) return true;
			if (["0", "false", "no", "off"].includes(normalized)) return false;
		}
	}
	return undefined;
}

function getExplicitMode(modelInfo: Record<string, unknown> | undefined): string | undefined {
	const mode = modelInfo?.mode;
	return typeof mode === "string" && mode.trim().length > 0 ? mode.trim().toLowerCase() : undefined;
}

function isEmbeddingModel(modelInfo: Record<string, unknown> | undefined): boolean {
	return getExplicitMode(modelInfo) === "embedding";
}

function discoverInput(
	model: LiteLLMModel,
	modelInfo?: Record<string, unknown>,
): Array<"text" | "image"> {
	const explicitVisionSupport = readBoolean(modelInfo?.supports_vision, modelInfo?.supportsVision);
	if (explicitVisionSupport === true) return ["text", "image"];
	if (explicitVisionSupport === false) return ["text"];

	const metadata = asRecord(model.metadata);
	const modalities = [
		...(Array.isArray(model.input_modalities) ? model.input_modalities : []),
		...(Array.isArray(metadata?.input_modalities) ? (metadata.input_modalities as string[]) : []),
	]
		.filter((value): value is string => typeof value === "string")
		.map((value) => value.toLowerCase());

	if (modalities.some((value) => value.includes("image") || value.includes("vision"))) {
		return ["text", "image"];
	}

	return ["text"];
}

function discoverReasoning(model: LiteLLMModel, modelInfo?: Record<string, unknown>): boolean {
	const metadata = asRecord(model.metadata);
	return (
		readBoolean(
			modelInfo?.supports_reasoning,
			modelInfo?.supportsReasoning,
			modelInfo?.reasoning,
			modelInfo?.thinking,
			metadata?.reasoning,
			metadata?.supports_reasoning,
			metadata?.supportsReasoning,
			metadata?.thinking,
		) ?? false
	);
}

function authHeaders(): Record<string, string> {
	return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

async function fetchModelInfoByName(): Promise<Map<string, Record<string, unknown>>> {
	const response = await fetch(modelInfoUrl, { headers: authHeaders() });
	if (!response.ok) {
		throw new Error(`LiteLLM model info discovery failed: ${response.status} ${await response.text()}`);
	}

	const payload = (await response.json()) as LiteLLMModelInfoResponse;
	if (!Array.isArray(payload.data)) {
		throw new Error("LiteLLM model info discovery failed: /model/info response did not contain a data array.");
	}

	return new Map(
		payload.data
			.filter(
				(entry): entry is LiteLLMModelInfoEntry =>
					Boolean(entry && typeof entry.model_name === "string" && entry.model_name.length > 0),
			)
			.map((entry) => [entry.model_name!, asRecord(entry.model_info) ?? {}]),
	);
}

async function fetchModels(): Promise<DiscoveredLiteLLMModel[]> {
	const [modelsResponse, modelInfoByName] = await Promise.all([
		fetch(modelsUrl, { headers: authHeaders() }),
		fetchModelInfoByName().catch((error) => {
			console.warn(`[litellm] ${error instanceof Error ? error.message : String(error)}`);
			return new Map<string, Record<string, unknown>>();
		}),
	]);
	if (!modelsResponse.ok) {
		throw new Error(`LiteLLM discovery failed: ${modelsResponse.status} ${await modelsResponse.text()}`);
	}

	const payload = (await modelsResponse.json()) as LiteLLMModelListResponse;
	if (!Array.isArray(payload.data)) {
		throw new Error("LiteLLM discovery failed: /models response did not contain a data array.");
	}

	return payload.data.flatMap((model) => {
		if (!model || typeof model.id !== "string") return [];
		const modelInfo = modelInfoByName.get(model.id);
		if (isEmbeddingModel(modelInfo)) return [];
		return [{ model, modelInfo }];
	});
}

function toProviderModel({ model, modelInfo }: DiscoveredLiteLLMModel) {
	const metadata = asRecord(model.metadata);
	return {
		id: model.id,
		name: model.name || model.id,
		reasoning: discoverReasoning(model, modelInfo),
		input: discoverInput(model, modelInfo),
		// TODO: fetch actual cost info from litellm
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		// local models starts struggling with context >64k tokens
		// set a sane default, may need to increase as the tech gets better
		contextWindow: readNumber(
			modelInfo?.max_input_tokens,
			modelInfo?.maxInputTokens,
			model.context_window,
			model.contextWindow,
			model.max_context_window,
			metadata?.context_window,
			metadata?.contextWindow,
			metadata?.max_context_window,
		) ?? 64000,
		// use default maxTokens for now
		// maxTokens: readNumber(
		// 	modelInfo?.max_output_tokens,
		// 	modelInfo?.maxOutputTokens,
		// 	modelInfo?.max_tokens,
		// 	modelInfo?.maxTokens,
		// 	model.max_tokens,
		// 	model.maxTokens,
		// 	metadata?.max_tokens,
		// 	metadata?.maxTokens,
		// ) ?? 16384,
		compat: {
			supportsStore: false,
			supportsDeveloperRole: false,
			supportsReasoningEffort: false,
			supportsUsageInStreaming: true,
			// maxTokensField: "max_tokens" as const,
		},
	};
}

export default async function (pi: ExtensionAPI) {
	if (!baseUrl) {
		console.error(`[litellm] LITELLM_BASE_URL is not set; skipping provider registration.`);
		return;
	}

	let discoveredModelCount = 0;
	let lastDiscoveryError: string | undefined;

	async function registerDiscoveredModels() {
		const discoveredModels = (await fetchModels()).map(toProviderModel);
		discoveredModelCount = discoveredModels.length;
		lastDiscoveryError = undefined;

		pi.registerProvider(providerName, {
			name: providerLabel,
			baseUrl,
			apiKey: authToken ?? "dummy-api-key",
			api: "openai-completions",
			models: discoveredModels,
			streamSimple(model, context, options) {
				return streamSimpleOpenAICompletions(model as Model<"openai-completions">, context, {
					...options,
					apiKey: options?.apiKey || authToken || "dummy-api-key",
					timeoutMs: options?.timeoutMs ?? configuredTimeoutMs,
				});
			},
		});

		return discoveredModels;
	}

	try {
		await registerDiscoveredModels();
	} catch (error) {
		lastDiscoveryError = error instanceof Error ? error.message : String(error);
		console.error(`[litellm] ${lastDiscoveryError}`);
		pi.registerProvider(providerName, {
			name: providerLabel,
			baseUrl,
			apiKey: authToken ?? "dummy-api-key",
			api: "openai-completions",
			models: [],
			streamSimple(model, context, options) {
				return streamSimpleOpenAICompletions(model as Model<"openai-completions">, context, {
					...options,
					apiKey: options?.apiKey || authToken || "dummy-api-key",
					timeoutMs: options?.timeoutMs ?? configuredTimeoutMs,
				});
			},
		});
	}

	pi.registerCommand("litellm-status", {
		description: "Show LiteLLM discovery status",
		handler: async (_args, ctx) => {
			if (lastDiscoveryError) {
				ctx.ui.notify(
					`${providerLabel}: discovery failed for ${modelsUrl} (${lastDiscoveryError})`,
					"error",
				);
				return;
			}
			ctx.ui.notify(`${providerLabel}: ${discoveredModelCount} models loaded from ${modelsUrl}`, "success");
		},
	});

	pi.registerCommand("litellm-refresh", {
		description: "Refresh models from the LiteLLM /v1/models endpoint",
		handler: async (_args, ctx) => {
			try {
				const models = await registerDiscoveredModels();
				ctx.ui.notify(`${providerLabel}: refreshed ${models.length} models from ${modelsUrl}`, "success");
			} catch (error) {
				lastDiscoveryError = error instanceof Error ? error.message : String(error);
				ctx.ui.notify(`${providerLabel}: refresh failed (${lastDiscoveryError})`, "error");
			}
		},
	});
}
