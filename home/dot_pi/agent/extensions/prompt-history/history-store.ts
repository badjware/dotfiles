import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";

const MAX_ENTRIES = 2000;

export interface HistoryEntry {
	text: string;
	timestamp: number;
}

const serialize = (entries: HistoryEntry[]) => entries.map((e) => JSON.stringify(e)).join("\n") + "\n";

/** Read all entries from disk. Called once at session_start. */
export function loadHistory(file: string): HistoryEntry[] {
	if (!existsSync(file)) return [];
	return readFileSync(file, "utf-8")
		.split("\n")
		.filter(Boolean)
		.map((line) => JSON.parse(line) as HistoryEntry);
}

/**
 * Append one entry, dedup (drop any earlier identical text so the new one moves to the end),
 * and compact when MAX_ENTRIES is exceeded. Returns the updated in-memory array.
 */
export function appendHistory(file: string, entries: HistoryEntry[], text: string): HistoryEntry[] {
	const trimmed = text.trim();
	if (!trimmed) return entries;

	const entry: HistoryEntry = { text: trimmed, timestamp: Date.now() };
	const filtered = entries.filter((e) => e.text !== trimmed);
	const combined = [...filtered, entry];
	const updated = combined.length > MAX_ENTRIES ? combined.slice(-MAX_ENTRIES) : combined;
	const needsRewrite = filtered.length !== entries.length || updated.length !== combined.length;

	try {
		if (needsRewrite) writeFileSync(file, serialize(updated), "utf-8");
		else appendFileSync(file, JSON.stringify(entry) + "\n", "utf-8");
	} catch {
		// Non-fatal: keep in-memory state; next call will retry
	}

	return updated;
}
