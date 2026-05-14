import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { appendHistory, loadHistory, type HistoryEntry } from "./history-store.js";
import { HistoryEditor } from "./history-editor.js";
import { HistorySearchOverlay } from "./search-overlay.js";

export default function (pi: ExtensionAPI) {
	const historyFile = join(getAgentDir(), "prompt-history.jsonl");
	let history: HistoryEntry[] = [];

	// ── Load history at startup ────────────────────────────────────────────
	pi.on("session_start", async (_event, ctx) => {
		history = loadHistory(historyFile);

		// Install the history-aware editor (re-applied on every session start
		// so it survives /new, /resume, and /reload)
		ctx.ui.setEditorComponent((tui, theme, kb) => new HistoryEditor(tui, theme, kb, () => history));
	});

	// ── Capture every submitted prompt ────────────────────────────────────
	pi.on("input", async (event, _ctx) => {
		if (event.source === "interactive") {
			history = appendHistory(historyFile, history, event.text);
		}
		return { action: "continue" };
	});

	// ── Ctrl+R: open search overlay ───────────────────────────────────────
	pi.registerShortcut("ctrl+r", {
		description: "Search prompt history (Ctrl+R)",
		handler: async (ctx) => {
			if (history.length === 0) {
				ctx.ui.notify("No history yet", "info");
				return;
			}

			const selected = await ctx.ui.custom<string | null>(
				(tui, theme, _kb, done) => new HistorySearchOverlay(history, tui, theme, done),
				{
					overlay: true,
					overlayOptions: {
						width: "100%",
						maxHeight: "90%",
						anchor: "bottom-center",
						offsetY: -2,
					},
				},
			);

			if (selected) {
				ctx.ui.setEditorText(selected);
			}
		},
	});
}
