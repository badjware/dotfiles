import { DynamicBorder } from "@earendil-works/pi-coding-agent";
import { Container, fuzzyFilter, getKeybindings, Input, Spacer, TruncatedText } from "@mariozechner/pi-tui";
import type { HistoryEntry } from "./history-store.js";

const MAX_VISIBLE = 25;

type Theme = { fg(color: string, text: string): string };
type Tui = { requestRender(): void };

/**
 * Ctrl+R history search overlay.
 *
 * Layout (mirrors ModelSelectorComponent structure):
 *   DynamicBorder
 *   listContainer  ← rebuilt on every state change; older entries at top, newest at bottom
 *   Spacer(1)
 *   Input          ← live fuzzy search; all non-navigation keys go here
 *   Spacer(1)
 *   DynamicBorder
 *
 * Selected row:   "→ <accent text>"
 * Unselected row: "  <plain text>"
 * Scroll indicator: "(N/total)" in muted at top, shown only when older entries are hidden above.
 * Selection wraps top↔bottom.
 *
 * allItems is newest-first (index 0 = newest). viewTop is the highest index currently
 * shown (oldest visible row, rendered at the top). The window shifts by 1 only when the
 * pointer leaves the visible range.
 */
export class HistorySearchOverlay extends Container {
	private searchInput: Input;
	private listContainer: Container;
	private allItems: HistoryEntry[]; // newest-first
	private filtered: HistoryEntry[];
	private selectedIndex = 0;
	private viewTop = 0; // highest (oldest) index currently shown at the top row
	private tui: Tui;
	private theme: Theme;
	private onDone: (result: string | null) => void;

	// Focusable — propagate to searchInput so the IME cursor is positioned correctly
	private _focused = false;
	get focused() {
		return this._focused;
	}
	set focused(v: boolean) {
		this._focused = v;
		this.searchInput.focused = v;
	}

	constructor(entries: HistoryEntry[], tui: Tui, theme: Theme, done: (result: string | null) => void) {
		super();
		this.tui = tui;
		this.theme = theme;
		this.onDone = done;
		this.allItems = [...entries].reverse(); // show newest first
		this.filtered = this.allItems;
		this.resetView();

		// ── Layout (list above, input at bottom) ───────────────────────────
		this.addChild(new DynamicBorder((s: string) => theme.fg("border", s)));

		this.listContainer = new Container();
		this.addChild(this.listContainer);
		this.addChild(new Spacer(1));

		this.searchInput = new Input();
		// Enter in the search box selects the highlighted item (same as model picker)
		this.searchInput.onSubmit = () => {
			const entry = this.filtered[this.selectedIndex];
			if (entry) done(entry.text);
		};
		this.addChild(this.searchInput);
		this.addChild(new Spacer(1));

		this.addChild(new DynamicBorder((s: string) => theme.fg("border", s)));

		this.updateList();
	}

	/** Reset pointer and window to the newest entry. Clamps so viewTop is never -1. */
	private resetView() {
		this.selectedIndex = 0;
		this.viewTop = Math.max(0, Math.min(this.filtered.length - 1, MAX_VISIBLE - 1));
	}

	private filterEntries(query: string) {
		this.filtered = query ? fuzzyFilter(this.allItems, query, (e) => e.text) : this.allItems;
		this.resetView();
		this.updateList();
	}

	private updateSelection(newIndex: number) {
		this.selectedIndex = newIndex;
		// Shift the window by exactly 1 only when the pointer leaves the visible range
		if (this.selectedIndex > this.viewTop) {
			this.viewTop = this.selectedIndex;
		} else if (this.selectedIndex < this.viewTop - MAX_VISIBLE + 1) {
			this.viewTop = this.selectedIndex + MAX_VISIBLE - 1;
		}
		this.updateList();
	}

	private updateList() {
		const { theme } = this;
		this.listContainer.clear();

		if (this.filtered.length === 0) {
			this.listContainer.addChild(new TruncatedText(theme.fg("muted", "  No matching history"), 0, 0));
			return;
		}

		// Render a fixed window: viewTop (top/oldest) down to viewTop-MAX_VISIBLE+1 (bottom/newest).
		// The window only shifts by 1 when the pointer hits an edge (see updateSelection).
		const viewBottom = Math.max(0, this.viewTop - MAX_VISIBLE + 1);

		// Render from viewTop (top/oldest) down to viewBottom (bottom/newest)
		for (let i = this.viewTop; i >= viewBottom; i--) {
			const entry = this.filtered[i]!;
			const isSelected = i === this.selectedIndex;
			const firstLine = entry.text.split("\n")[0]!;
			const line = isSelected
				? theme.fg("accent", "→ ") + theme.fg("accent", firstLine)
				: "  " + firstLine;
			this.listContainer.addChild(new TruncatedText(line, 0, 0));
		}
	}

	handleInput(keyData: string) {
		const kb = getKeybindings();

		if (kb.matches(keyData, "tui.select.up")) {
			if (this.filtered.length === 0) return; // no render needed
			// ↑ = older entry = increment index (allItems is newest-first)
			const next = this.selectedIndex === this.filtered.length - 1 ? 0 : this.selectedIndex + 1;
			this.updateSelection(next);
		} else if (kb.matches(keyData, "tui.select.down")) {
			if (this.filtered.length === 0) return; // no render needed
			// ↓ = newer entry = decrement index
			const next = this.selectedIndex === 0 ? this.filtered.length - 1 : this.selectedIndex - 1;
			this.updateSelection(next);
		} else if (kb.matches(keyData, "tui.select.confirm")) {
			const entry = this.filtered[this.selectedIndex];
			if (entry) this.onDone(entry.text);
			return; // overlay is closing, no render needed
		} else if (kb.matches(keyData, "tui.select.cancel")) {
			this.onDone(null);
			return; // overlay is closing, no render needed
		} else {
			// Everything else: feed to search box, then re-filter
			this.searchInput.handleInput(keyData);
			this.filterEntries(this.searchInput.getValue());
		}

		this.tui.requestRender();
	}
}
