/**
 * Minimal ANSI escape code to HTML span converter.
 * Handles standard 8-color foreground/background and bold/reset.
 */

const ANSI_COLORS: Record<number, string> = {
  30: "#1f2937", // black
  31: "#ef4444", // red
  32: "#10b981", // green
  33: "#f59e0b", // yellow
  34: "#3b82f6", // blue
  35: "#a855f7", // magenta
  36: "#06b6d4", // cyan
  37: "#e5e7eb", // white
  90: "#6b7280", // bright black (gray)
  91: "#fca5a5", // bright red
  92: "#6ee7b7", // bright green
  93: "#fde68a", // bright yellow
  94: "#93c5fd", // bright blue
  95: "#d8b4fe", // bright magenta
  96: "#67e8f9", // bright cyan
  97: "#f9fafb", // bright white
};

const ANSI_BG_COLORS: Record<number, string> = {
  40: "#1f2937",
  41: "#ef4444",
  42: "#10b981",
  43: "#f59e0b",
  44: "#3b82f6",
  45: "#a855f7",
  46: "#06b6d4",
  47: "#e5e7eb",
};

// eslint-disable-next-line no-control-regex
const ANSI_REGEX = /\x1b\[([0-9;]*)m/g;

interface AnsiSpan {
  text: string;
  style: string;
}

export function parseAnsiLine(line: string): AnsiSpan[] {
  const spans: AnsiSpan[] = [];
  let currentColor: string | null = null;
  let currentBg: string | null = null;
  let bold = false;
  let lastIndex = 0;

  ANSI_REGEX.lastIndex = 0;

  let match: RegExpExecArray | null;
  while ((match = ANSI_REGEX.exec(line)) !== null) {
    // Push text before this escape
    if (match.index > lastIndex) {
      const text = line.slice(lastIndex, match.index);
      spans.push({ text, style: buildStyle(currentColor, currentBg, bold) });
    }
    lastIndex = match.index + match[0].length;

    // Parse SGR codes
    const codes = match[1].split(";").map(Number);
    for (const code of codes) {
      if (code === 0) {
        currentColor = null;
        currentBg = null;
        bold = false;
      } else if (code === 1) {
        bold = true;
      } else if (code === 22) {
        bold = false;
      } else if (ANSI_COLORS[code]) {
        currentColor = ANSI_COLORS[code];
      } else if (ANSI_BG_COLORS[code]) {
        currentBg = ANSI_BG_COLORS[code];
      } else if (code === 39) {
        currentColor = null;
      } else if (code === 49) {
        currentBg = null;
      }
    }
  }

  // Push remaining text
  if (lastIndex < line.length) {
    spans.push({ text: line.slice(lastIndex), style: buildStyle(currentColor, currentBg, bold) });
  }

  // If no spans were created, push the whole line
  if (spans.length === 0) {
    spans.push({ text: line, style: "" });
  }

  return spans;
}

function buildStyle(color: string | null, bg: string | null, bold: boolean): string {
  const parts: string[] = [];
  if (color) parts.push(`color:${color}`);
  if (bg) parts.push(`background-color:${bg}`);
  if (bold) parts.push("font-weight:bold");
  return parts.join(";");
}

/** Strip ANSI escape codes for plain-text operations (e.g., download) */
export function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;]*m/g, "");
}
