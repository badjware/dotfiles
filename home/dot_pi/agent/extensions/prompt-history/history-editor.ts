import { CustomEditor } from "@mariozechner/pi-coding-agent";
import { getKeybindings } from "@mariozechner/pi-tui";
import type { HistoryEntry } from "./history-store.js";

/**
 * Editor subclass that adds ↑/↓ prompt-history cycling.
 *
 * Behaviour (mirrors bash readline):
 * - ↑ when cursor is on line 0: enter history mode (or go one step older).
 *   At the oldest entry, stay put — no wrap.
 * - ↓ when in history mode and cursor is on the last line: go one step newer.
 *   Past the newest entry: restore the saved draft and exit history mode.
 * - Any other key while in history mode: exit history mode silently, keep
 *   current text as the new draft (user is now editing the recalled entry).
 * - Normal multi-line cursor movement is fully preserved: ↑/↓ are only
 *   hijacked when the cursor is actually at the first/last line.
 */
export class HistoryEditor extends CustomEditor {
	/** -1 = not in history-browsing mode. Otherwise: index into history array. */
	private histIdx = -1;
	/** Text saved when the user first presses ↑ to enter history mode. */
	private draft = "";
	/** Callback that always returns the current (possibly growing) history. */
	private getHistory: () => HistoryEntry[];
	// CustomEditor doesn't expose the tui instance publicly, so we keep our own reference.
	private tui: { requestRender(): void };

	constructor(tui: any, theme: any, keybindings: any, getHistory: () => HistoryEntry[]) {
		super(tui, theme, keybindings);
		this.tui = tui;
		this.getHistory = getHistory;
	}

	override handleInput(data: string): void {
		const kb = getKeybindings();
		const history = this.getHistory();

		// ── ↑  ──────────────────────────────────────────────────────────────
		if (kb.matches(data, "tui.editor.cursorUp")) {
			// Only hijack when cursor is already on the very first line
			if (this.getCursor().line === 0 && history.length > 0) {
				if (this.histIdx === -1) {
					// Entering history mode: save the current draft
					this.draft = this.getText();
					this.histIdx = history.length - 1; // start at most-recent
				} else if (this.histIdx > 0) {
					this.histIdx--;
				}
				// histIdx === 0 means we are already at the oldest entry — stay put
				this.setText(history[this.histIdx].text);
				this.tui.requestRender();
				return; // consumed — do NOT pass to super
			}
			// Cursor is not on line 0: fall through to normal editor handling
		}

		// ── ↓  ──────────────────────────────────────────────────────────────
		else if (kb.matches(data, "tui.editor.cursorDown")) {
			if (this.histIdx !== -1) {
				// Only hijack when cursor is on the last line
				if (this.getCursor().line === this.getLines().length - 1) {
					if (this.histIdx < history.length - 1) {
						this.histIdx++;
						this.setText(history[this.histIdx].text);
					} else {
						// Past the newest entry: restore the saved draft
						this.histIdx = -1;
						this.setText(this.draft);
					}
					this.tui.requestRender();
					return; // consumed
				}
			}
			// Not in history mode, or cursor not on last line: fall through
		}

		// ── Any other key: silently exit history mode ────────────────────────
		else if (this.histIdx !== -1) {
			this.histIdx = -1;
			// Keep the current text — user is now editing the recalled entry as a new draft
		}

		super.handleInput(data);
	}
}
