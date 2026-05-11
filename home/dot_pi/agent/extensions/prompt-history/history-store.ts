import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";

const MAX_ENTRIES = 2000;

export interface HistoryEntry {
	text: string;
	timestamp: number;
}

/**
 * Read all entries from disk. Called once at session_start.
 */
export function loadHistory(file: string): HistoryEntry[] {
	if (!existsSync(file)) return [];
	return readFileSync(file, "utf-8")
		.split("\n")
		.filter(Boolean)
		.flatMap((line) => {
			try {
				return [JSON.parse(line) as HistoryEntry];
			} catch {
				return [];
			}
		});
}

/**
 * Append one entry to disk and return the updated in-memory array.
 * Skips empty text and consecutive duplicates.
 * Compacts the file when MAX_ENTRIES is exceeded.
 */
export function appendHistory(file: string, entries: HistoryEntry[], text: string): HistoryEntry[] {
	const trimmed = text.trim();
	if (!trimmed) return entries;

	// Dedup: skip if identical to the last entry
	if (entries.length > 0 && entries[entries.length - 1].text === trimmed) return entries;

	const entry: HistoryEntry = { text: trimmed, timestamp: Date.now() };

	try {
		appendFileSync(file, JSON.stringify(entry) + "\n", "utf-8");
	} catch {
		// Non-fatal: continue with in-memory history even if the write fails
		return [...entries, entry];
	}

	const updated = [...entries, entry];

	if (updated.length > MAX_ENTRIES) {
		const compacted = updated.slice(-MAX_ENTRIES);
		try {
			writeFileSync(file, compacted.map((e) => JSON.stringify(e)).join("\n") + "\n", "utf-8");
		} catch {
			// Non-fatal: keep the over-limit in-memory list; compaction will retry next time
		}
		return compacted;
	}

	return updated;
}
