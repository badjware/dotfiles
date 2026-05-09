# LiteLLM Provider

Automatically discovers and registers models from a [LiteLLM](https://litellm.vercel.app/) proxy as a pi provider.

## Overview

This extension queries the LiteLLM `/v1/models` and `/model/info` endpoints at startup, filters out embedding models, and registers the discovered models as a provider named `litellm` (configurable). It also provides commands to inspect and refresh the model list at runtime.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LITELLM_BASE_URL` | Yes | — | Base URL of the LiteLLM proxy (e.g. `http://localhost:4000`). The `/v1` prefix is appended automatically. |
| `LITELLM_API_KEY` | No | — | API key for authenticating with the LiteLLM proxy. |
| `LITELLM_TIMEOUT_MS` | No | `600000` (10 min) | Request timeout in milliseconds for model streaming calls. |
| `PI_LITELLM_PROVIDER` | No | `litellm` | Internal provider name used by pi. |
| `PI_LITELLM_NAME` | No | `LiteLLM` | Display name shown in the TUI. |

### Example

```bash
export LITELLM_BASE_URL="http://localhost:4000"
export LITELLM_API_KEY="sk-my-api-key"
```

## Commands

| Command | Description |
|---------|-------------|
| `/litellm-status` | Show discovery status — how many models were loaded or why discovery failed. |
| `/litellm-refresh` | Re-query the LiteLLM endpoints and reload the model list. |

## How It Works

1. On startup, the extension fetches both `/v1/models` and `/model/info` from the configured LiteLLM proxy in parallel.
2. Models identified as embeddings (via `mode: "embedding"` in model info) are excluded.
3. For each remaining model, input modalities (text / image) and reasoning support are inferred from the model metadata.
4. Models are registered with the `openai-completions` API, delegating streaming to pi's built-in OpenAI-compatible provider.
5. If discovery fails (e.g. the proxy is unreachable), the provider is still registered with an empty model list so the user is not blocked.

## Model Discovery Details

### Input modalities

The extension determines whether a model accepts images by checking, in order:

1. Explicit `supports_vision` / `supportsVision` boolean in model info.
2. `input_modalities` array on the model or in its metadata, looking for entries containing `"image"` or `"vision"`.

### Reasoning support

Reasoning capability is detected from any of these fields in model info or metadata: `supports_reasoning`, `supportsReasoning`, `reasoning`, `thinking`.

### Context window

The context window size is read from model info or metadata, falling back to `64000` tokens:

- `max_input_tokens` / `maxInputTokens`
- `context_window` / `contextWindow`
- `max_context_window`

### Costs

Cost information is not yet fetched from LiteLLM; all costs default to `0`.

## File Structure

```
litellm/
├── index.ts        # Extension entry point
└── README.md       # This file
```
