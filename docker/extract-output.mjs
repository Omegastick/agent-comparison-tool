// Extract the assistant-authored text from a Pi NDJSON trace into output.txt.
//
// Pi --mode json emits message_start / message_update / message_end events, each
// carrying a `message` object with a `role` and a `content` array of blocks
// (text / thinking / toolCall / ...). Two gotchas drive this logic:
//
//   1. message_update events are CUMULATIVE snapshots of the in-progress
//      message, NOT incremental deltas. Each successive update for the same
//      message repeats the full text so far. They must be deduplicated (keep
//      only the latest snapshot per message), never concatenated, or the output
//      balloons with megabytes of duplicated text.
//   2. For multi-turn judgment tasks the substantive deliverable is often an
//      earlier assistant turn (e.g. the written-out tickets) followed by a short
//      closing turn, so we preserve the text of EVERY assistant turn in order
//      rather than keeping only the last one.
//
// message_end is the authoritative finalised message; a message_update snapshot
// is only relied on to recover a turn that never reached message_end (e.g. a run
// killed on timeout). The raw trace is always preserved in trace.jsonl.
import { readFileSync, writeFileSync } from "node:fs";

const [, , tracePath, outPath] = process.argv;

function textFrom(content) {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(
        (b) =>
          b && typeof b === "object" && b.type === "text" && typeof b.text === "string",
      )
      .map((b) => b.text)
      .join("");
  }
  if (typeof content === "object" && typeof content.text === "string") {
    return content.text;
  }
  return "";
}

const isAssistant = (message) =>
  message != null && (message.role == null || message.role === "assistant");

// Insertion-ordered map of assistant turns keyed by responseId (present in every
// observed transport). `final` flags a message_end so a stray trailing update
// cannot clobber the authoritative text; for not-yet-final turns each cumulative
// snapshot simply overwrites the previous one.
const turns = new Map();
let anonSeq = 0;
let currentAnonKey = null;

for (const line of readFileSync(tracePath, "utf8").split("\n")) {
  const trimmed = line.trim();
  if (!trimmed) continue;
  let ev;
  try {
    ev = JSON.parse(trimmed);
  } catch {
    continue;
  }
  if (!ev || typeof ev.type !== "string" || !ev.type.startsWith("message")) continue;

  const message = ev.message;
  if (!isAssistant(message)) {
    if (ev.type === "message_end") currentAnonKey = null;
    continue;
  }

  // Fall back to a per-message-start counter only if a transport ever omits
  // responseId, so cumulative updates of one turn still share a key.
  let key = message.responseId;
  if (key == null) {
    if (ev.type === "message_start" || currentAnonKey == null) {
      currentAnonKey = `anon:${anonSeq++}`;
    }
    key = currentAnonKey;
  }

  const isEnd = ev.type === "message_end";
  const text = textFrom(message.content);
  const existing = turns.get(key);
  if (existing == null) {
    turns.set(key, { text, final: isEnd });
  } else if (isEnd || !existing.final) {
    existing.text = text;
    existing.final = existing.final || isEnd;
  }
  if (isEnd) currentAnonKey = null;
}

const output = [...turns.values()]
  .map((t) => t.text)
  .filter((t) => t && t.trim())
  .join("\n\n");

if (!output.trim()) {
  process.stderr.write(
    `extract-output: no assistant text found in ${tracePath}: ` +
      `the full trace is preserved in trace.jsonl\n`,
  );
  process.exit(2);
}

writeFileSync(outPath, output);
