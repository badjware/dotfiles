// Shared truncation helper for browser skill scripts.
// 2000 lines or 50KB, whichever is hit first.
const fs = require("fs");

const MAX_LINES = 2000;
const MAX_BYTES = 50 * 1024;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

// Truncates content to MAX_LINES/MAX_BYTES. If truncated, writes full content
// to tempFile and appends a notice pointing the agent to it.
function truncate(content, tempFile) {
  const totalBytes = Buffer.byteLength(content, "utf8");
  const lines = content.split("\n");
  const totalLines = lines.length;

  if (totalLines <= MAX_LINES && totalBytes <= MAX_BYTES) return content;

  let out = lines.slice(0, MAX_LINES).join("\n");
  if (Buffer.byteLength(out, "utf8") > MAX_BYTES) {
    out = Buffer.from(out, "utf8").slice(0, MAX_BYTES).toString("utf8");
    out = out.slice(0, out.lastIndexOf("\n"));
  }

  const outputLines = out.split("\n").length;
  const outputBytes = Buffer.byteLength(out, "utf8");

  fs.writeFileSync(tempFile, content, "utf8");

  out += `\n\n[Output truncated: showing ${outputLines} of ${totalLines} lines`;
  out += ` (${formatSize(outputBytes)} of ${formatSize(totalBytes)}).`;
  out += ` Full output saved to: ${tempFile}]`;

  return out;
}

module.exports = { truncate };
