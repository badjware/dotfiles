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
const baseUrl = configuredBaseUrl
  ? normalizeBaseUrl(configuredBaseUrl)
  : undefined;
const modelsUrl = baseUrl
  ? new URL("models", ensureTrailingSlash(baseUrl)).toString()
  : undefined;
const modelInfoUrl = baseUrl
  ? new URL("model/info", ensureTrailingSlash(baseUrl)).toString()
  : undefined;

function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
}

function ensureTrailingSlash(url: string): string {
  return url.endsWith("/") ? url : `${url}/`;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : undefined;
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

function getExplicitMode(
  modelInfo: Record<string, unknown> | undefined,
): string | undefined {
  const mode = modelInfo?.mode;
  return typeof mode === "string" && mode.trim().length > 0
    ? mode.trim().toLowerCase()
    : undefined;
}

function isEmbeddingModel(
  modelInfo: Record<string, unknown> | undefined,
): boolean {
  return getExplicitMode(modelInfo) === "embedding";
}

function discoverInput(
  model: LiteLLMModel,
  modelInfo?: Record<string, unknown>,
): Array<"text" | "image"> {
  const explicitVisionSupport = readBoolean(
    modelInfo?.supports_vision,
    modelInfo?.supportsVision,
  );
  if (explicitVisionSupport === true) return ["text", "image"];
  if (explicitVisionSupport === false) return ["text"];

  const metadata = asRecord(model.metadata);
  const modalities = [
    ...(Array.isArray(model.input_modalities) ? model.input_modalities : []),
    ...(Array.isArray(metadata?.input_modalities)
      ? (metadata.input_modalities as string[])
      : []),
  ]
    .filter((value): value is string => typeof value === "string")
    .map((value) => value.toLowerCase());

  if (
    modalities.some(
      (value) => value.includes("image") || value.includes("vision"),
    )
  ) {
    return ["text", "image"];
  }

  return ["text"];
}

function discoverReasoning(
  model: LiteLLMModel,
  modelInfo?: Record<string, unknown>,
): boolean {
  if (modelInfo?.engine === "llama.cpp") return true;
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

// Maps pi thinking levels to llama.cpp thinking_budget_tokens values.
// -1 means unlimited (sampler is skipped entirely). "off" is handled
// separately via enable_thinking: false.
const LLAMA_CPP_THINKING_BUDGETS: Record<string, number> = {
  minimal: 512,
  low: 1024,
  medium: 2048,
  high: 4096,
  xhigh: -1,
};

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

async function fetchModelInfoByName(): Promise<
  Map<string, Record<string, unknown>>
> {
  const response = await fetch(modelInfoUrl, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(
      `LiteLLM model info discovery failed: ${response.status} ${await response.text()}`,
    );
  }

  const payload = (await response.json()) as LiteLLMModelInfoResponse;
  if (!Array.isArray(payload.data)) {
    throw new Error(
      "LiteLLM model info discovery failed: /model/info response did not contain a data array.",
    );
  }

  return new Map(
    payload.data
      .filter((entry): entry is LiteLLMModelInfoEntry =>
        Boolean(
          entry &&
          typeof entry.model_name === "string" &&
          entry.model_name.length > 0,
        ),
      )
      .map((entry) => [entry.model_name!, asRecord(entry.model_info) ?? {}]),
  );
}

async function fetchModels(): Promise<DiscoveredLiteLLMModel[]> {
  const [modelsResponse, modelInfoByName] = await Promise.all([
    fetch(modelsUrl, { headers: authHeaders() }),
    fetchModelInfoByName().catch((error) => {
      console.warn(
        `[litellm] ${error instanceof Error ? error.message : String(error)}`,
      );
      return new Map<string, Record<string, unknown>>();
    }),
  ]);
  if (!modelsResponse.ok) {
    throw new Error(
      `LiteLLM discovery failed: ${modelsResponse.status} ${await modelsResponse.text()}`,
    );
  }

  const payload = (await modelsResponse.json()) as LiteLLMModelListResponse;
  if (!Array.isArray(payload.data)) {
    throw new Error(
      "LiteLLM discovery failed: /models response did not contain a data array.",
    );
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
    cost: {
      input: (modelInfo?.input_cost_per_token as number) ?? 0,
      output: (modelInfo?.output_cost_per_token as number) ?? 0,
      cacheRead: (modelInfo?.cache_read_cost_per_token as number) ?? 0,
      cacheWrite: (modelInfo?.cache_creation_cost_per_token as number) ?? 0,
    },
    // local models starts struggling with context >64k tokens
    // set a sane default, may need to increase as the tech gets better
    contextWindow:
      readNumber(
        modelInfo?.max_tokens,
        modelInfo?.maxTokens,
        modelInfo?.max_input_tokens,
        modelInfo?.maxInputTokens,
        model.context_window,
        model.contextWindow,
        model.max_context_window,
        metadata?.context_window,
        metadata?.contextWindow,
        metadata?.max_context_window,
      ) ?? 64000,
    // maxTokens is not set from model_info — it's a request-level parameter
    // that depends on input size, which we don't know at discovery time.
    // xhigh requires an explicit thinkingLevelMap entry to appear in the level cycle.
    ...(modelInfo?.engine === "llama.cpp" ? { thinkingLevelMap: { xhigh: "xhigh" } } : {}),
    compat: {
      supportsStore: false,
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      supportsUsageInStreaming: true,
      },
  };
}

function makeStreamOptions(
  options: Parameters<typeof streamSimpleOpenAICompletions>[2],
  onPayload?: (params: Record<string, unknown>) => Record<string, unknown>,
) {
  return {
    ...options,
    // Cloudflare WAF blocks the OpenAI SDK's default User-Agent header.
    headers: { ...options?.headers, "User-Agent": null as unknown as string },
    onPayload: onPayload ?? options?.onPayload,
  };
}

function injectThinkingParams(params: Record<string, unknown>, level: string): Record<string, unknown> {
  if (level === "off") {
    const existing = params.chat_template_kwargs;
    return {
      ...params,
      chat_template_kwargs: {
        ...(typeof existing === "object" && existing !== null ? existing : {}),
        enable_thinking: false,
      },
    };
  }
  const budget = LLAMA_CPP_THINKING_BUDGETS[level] ?? -1;
  return { ...params, thinking_budget_tokens: budget };
}

export default async function (pi: ExtensionAPI) {
  if (!baseUrl) {
    console.error(
      `[litellm] LITELLM_BASE_URL is not set; skipping provider registration.`,
    );
    return;
  }

  let discoveredModelCount = 0;
  let lastDiscoveryError: string | undefined;

  // Tracks model IDs served by a llama.cpp backend; rebuilt on each discovery.
  const llamaCppModelIds = new Set<string>();
  async function registerDiscoveredModels() {
    llamaCppModelIds.clear();
    const discovered = await fetchModels();
    for (const { model, modelInfo } of discovered) {
      if (modelInfo?.engine === "llama.cpp") llamaCppModelIds.add(model.id);
    }
    const discoveredModels = discovered.map(toProviderModel);
    discoveredModelCount = discoveredModels.length;
    lastDiscoveryError = undefined;

    pi.registerProvider(providerName, {
      name: providerLabel,
      baseUrl,
      apiKey: authToken ?? "dummy-api-key",
      api: "openai-completions",
      models: discoveredModels,
      streamSimple(model, context, options) {
        return streamSimpleOpenAICompletions(
          model as Model<"openai-completions">,
          context,
          makeStreamOptions(
            { ...options, apiKey: options?.apiKey || authToken || "dummy-api-key", timeoutMs: options?.timeoutMs ?? configuredTimeoutMs },
            llamaCppModelIds.has(model.id) ? (params) => injectThinkingParams(params, pi.getThinkingLevel()) : undefined,
          ),
        );
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
        return streamSimpleOpenAICompletions(
          model as Model<"openai-completions">,
          context,
          makeStreamOptions({ ...options, apiKey: options?.apiKey || authToken || "dummy-api-key", timeoutMs: options?.timeoutMs ?? configuredTimeoutMs }),
        );
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
      ctx.ui.notify(
        `${providerLabel}: ${discoveredModelCount} models loaded from ${modelsUrl}`,
        "success",
      );
    },
  });

  pi.registerCommand("litellm-refresh", {
    description: "Refresh models from the LiteLLM /v1/models endpoint",
    handler: async (_args, ctx) => {
      try {
        const models = await registerDiscoveredModels();
        ctx.ui.notify(
          `${providerLabel}: refreshed ${models.length} models from ${modelsUrl}`,
          "success",
        );
      } catch (error) {
        lastDiscoveryError =
          error instanceof Error ? error.message : String(error);
        ctx.ui.notify(
          `${providerLabel}: refresh failed (${lastDiscoveryError})`,
          "error",
        );
      }
    },
  });
}
