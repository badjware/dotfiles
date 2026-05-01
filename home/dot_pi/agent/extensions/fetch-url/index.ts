import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";

type JsonRpcMessage = {
	jsonrpc: "2.0";
	id?: number;
	method?: string;
	params?: unknown;
	result?: unknown;
	error?: { code: number; message: string; data?: unknown };
};

type McpToolCallResult = {
	content?: Array<{ type?: string; text?: string }>;
	structuredContent?: unknown;
	isError?: boolean;
};

const baseDir = dirname(fileURLToPath(import.meta.url));
const serverPath = join(baseDir, "fetch-url.py");
const pythonCommand = process.env.PI_DDG_MCP_PYTHON || "python3";
const requestTimeoutMs = Number(process.env.PI_DDG_MCP_TIMEOUT_MS || 30000);

class McpClient {
	private child: ChildProcessWithoutNullStreams;
	private buffer = Buffer.alloc(0);
	private nextId = 1;
	private pending = new Map<
		number,
		{
			resolve: (value: unknown) => void;
			reject: (error: Error) => void;
			timeout: NodeJS.Timeout;
		}
	>();
	private initPromise?: Promise<void>;
	private closed = false;

	constructor() {
		this.child = spawn(pythonCommand, [serverPath], {
			stdio: ["pipe", "pipe", "pipe"],
			env: process.env,
		});

		this.child.stdout.on("data", (chunk: Buffer) => this.onStdout(chunk));
		this.child.stderr.on("data", (chunk: Buffer) => {
			const text = chunk.toString("utf8").trim();
			if (text) console.error(`[fetch-url] ${text}`);
		});
		this.child.on("error", (error) => this.failAll(`Failed to start fetch_url server: ${error.message}`));
		this.child.on("exit", (code, signal) => {
			if (this.closed) return;
			this.failAll(
				`fetch_url server exited unexpectedly${code !== null ? ` with code ${code}` : ""}${signal ? ` (signal ${signal})` : ""}.`,
			);
		});
	}

	async initialize(): Promise<void> {
		if (!this.initPromise) {
			this.initPromise = (async () => {
				await this.request("initialize", {
					protocolVersion: "2024-11-05",
					capabilities: {},
					clientInfo: { name: "pi-fetch-url", version: "0.3.0" },
				});
				this.notify("notifications/initialized", {});
			})();
		}
		return this.initPromise;
	}

	async callTool(args: Record<string, unknown>): Promise<McpToolCallResult> {
		await this.initialize();
		return (await this.request("tools/call", {
			name: "fetch_url",
			arguments: args,
		})) as McpToolCallResult;
	}

	async listTools(): Promise<unknown> {
		await this.initialize();
		return this.request("tools/list", {});
	}

	shutdown(): void {
		if (this.closed) return;
		this.closed = true;
		for (const [, pending] of this.pending) {
			clearTimeout(pending.timeout);
			pending.reject(new Error("fetch_url server shut down."));
		}
		this.pending.clear();
		this.child.kill();
	}

	private notify(method: string, params?: unknown): void {
		this.write({ jsonrpc: "2.0", method, params });
	}

	private request(method: string, params?: unknown): Promise<unknown> {
		if (this.closed) throw new Error("fetch_url client is closed.");
		const id = this.nextId++;
		return new Promise((resolve, reject) => {
			const timeout = setTimeout(() => {
				this.pending.delete(id);
				reject(new Error(`fetch_url request timed out after ${requestTimeoutMs}ms (${method}).`));
			}, requestTimeoutMs);
			this.pending.set(id, { resolve, reject, timeout });
			this.write({ jsonrpc: "2.0", id, method, params });
		});
	}

	private write(message: JsonRpcMessage): void {
		const payload = Buffer.from(JSON.stringify(message), "utf8");
		const header = Buffer.from(`Content-Length: ${payload.length}\r\n\r\n`, "utf8");
		this.child.stdin.write(Buffer.concat([header, payload]));
	}

	private onStdout(chunk: Buffer): void {
		this.buffer = Buffer.concat([this.buffer, chunk]);
		while (true) {
			const headerEnd = this.buffer.indexOf("\r\n\r\n");
			if (headerEnd === -1) return;
			const headerText = this.buffer.subarray(0, headerEnd).toString("utf8");
			const match = headerText.match(/Content-Length:\s*(\d+)/i);
			if (!match) {
				this.failAll("fetch_url server sent a message without Content-Length.");
				return;
			}
			const contentLength = Number(match[1]);
			const messageStart = headerEnd + 4;
			const messageEnd = messageStart + contentLength;
			if (this.buffer.length < messageEnd) return;
			const body = this.buffer.subarray(messageStart, messageEnd).toString("utf8");
			this.buffer = this.buffer.subarray(messageEnd);
			let message: JsonRpcMessage;
			try {
				message = JSON.parse(body) as JsonRpcMessage;
			} catch (error) {
				this.failAll(`fetch_url server returned invalid JSON: ${(error as Error).message}`);
				return;
			}
			this.handleMessage(message);
		}
	}

	private handleMessage(message: JsonRpcMessage): void {
		if (typeof message.id !== "number") return;
		const pending = this.pending.get(message.id);
		if (!pending) return;
		clearTimeout(pending.timeout);
		this.pending.delete(message.id);
		if (message.error) {
			pending.reject(new Error(message.error.message));
			return;
		}
		pending.resolve(message.result);
	}

	private failAll(message: string): void {
		if (this.closed) return;
		this.closed = true;
		for (const [, pending] of this.pending) {
			clearTimeout(pending.timeout);
			pending.reject(new Error(message));
		}
		this.pending.clear();
	}
}

function textFromResult(result: McpToolCallResult): string {
	const parts = (result.content || [])
		.filter((part) => part.type === "text" && typeof part.text === "string")
		.map((part) => part.text?.trim())
		.filter((part): part is string => Boolean(part));
	if (parts.length > 0) return parts.join("\n\n");
	if (result.structuredContent !== undefined) return JSON.stringify(result.structuredContent, null, 2);
	return "Tool returned no text.";
}

export default function (pi: ExtensionAPI) {
	let clientPromise: Promise<McpClient> | undefined;

	async function getClient(): Promise<McpClient> {
		if (!clientPromise) {
			clientPromise = (async () => {
				const client = new McpClient();
				await client.initialize();
				await client.listTools();
				return client;
			})();
		}
		try {
			return await clientPromise;
		} catch (error) {
			clientPromise = undefined;
			throw error;
		}
	}

	function resetClient(): void {
		if (!clientPromise) return;
		void clientPromise.then((client) => client.shutdown()).catch(() => undefined);
		clientPromise = undefined;
	}

	pi.on("session_shutdown", () => {
		resetClient();
	});

	pi.registerCommand("fetch-url-status", {
		description: "Check the fetch_url bridge status",
		handler: async (_args, ctx) => {
			try {
				await getClient();
				ctx.ui.notify("fetch_url bridge is ready.", "success");
			} catch (error) {
				ctx.ui.notify(`fetch_url bridge failed: ${(error as Error).message}`, "error");
			}
		},
	});

	pi.registerCommand("fetch-url-restart", {
		description: "Restart the fetch_url bridge",
		handler: async (_args, ctx) => {
			resetClient();
			ctx.ui.notify("fetch_url bridge restarted.", "info");
		},
	});

	pi.registerTool(
		defineTool({
			name: "fetch_url",
			label: "Fetch URL",
			description: "Fetch a public web page and extract readable text content.",
			promptSnippet: "Fetch a public URL and extract readable page text.",
			promptGuidelines: [
				"Use fetch_url to read a public web page after search_web finds a relevant result or when the user gives a public URL.",
				"Use fetch_url only for public http or https URLs; do not use it for local, private, or internal network targets.",
			],
			parameters: Type.Object({
				url: Type.String({ description: "Public http or https URL to fetch" }),
				max_chars: Type.Optional(Type.Number({ description: "Maximum number of extracted characters to return (default 12000)" })),
			}),
			async execute(_toolCallId, params, _signal, onUpdate) {
				onUpdate?.({ content: [{ type: "text", text: `Fetching URL: ${params.url}` }] });
				const client = await getClient();
				try {
					const result = await client.callTool(params as Record<string, unknown>);
					return {
						content: [{ type: "text", text: textFromResult(result) }],
						details: result.structuredContent ?? result,
						isError: Boolean(result.isError),
					};
				} catch (error) {
					client.shutdown();
					clientPromise = undefined;
					throw error;
				}
			},
		}),
	);
}
