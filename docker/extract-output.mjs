// Extract the final assistant text from a Pi NDJSON trace.
//
// Pi emits a stream of `message_*` events. The exact field layout can vary by
// version, so we pull text defensively from the common locations. A "finalish"
// event (`message`, or any `*_end`/`*_final`/`*_complete`/`*_stop`) is treated
// as the authoritative full message; otherwise we accumulate incremental
// deltas. The precise schema should be confirmed via the smoke test.
import { readFileSync, writeFileSync } from "node:fs";

const [, , tracePath, outPath] = process.argv;

function textFrom(node) {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textFrom).filter(Boolean).join("");
  if (typeof node === "object") {
    if (typeof node.text === "string") return node.text;
    if (node.content != null) return textFrom(node.content);
    if (node.delta != null) return textFrom(node.delta);
    if (node.message != null) return textFrom(node.message);
  }
  return "";
}

function isAssistant(ev) {
  const role = ev.role ?? ev.message?.role;
  return role == null || role === "assistant";
}

const isFinalish = (type) =>
  type === "message" || /(_end|_final|_complete|_stop)$/.test(type);

let finalText = "";
let deltaText = "";

for (const line of readFileSync(tracePath, "utf8").split("\n")) {
  const trimmed = line.trim();
  if (!trimmed) continue;
  let ev;
  try {
    ev = JSON.parse(trimmed);
  } catch {
    continue;
  }
  if (!ev || typeof ev.type !== "string") continue;
  if (!ev.type.startsWith("message")) continue;
  if (!isAssistant(ev)) continue;

  const text = textFrom(ev);
  if (!text) continue;
  if (isFinalish(ev.type)) {
    finalText = text;
  } else {
    deltaText += text;
  }
}

writeFileSync(outPath, finalText || deltaText);
