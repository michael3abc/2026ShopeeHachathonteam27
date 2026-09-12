// Reproducibly render the canonical Mermaid source; no raster editing or AI redraw.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const markdown = readFileSync(resolve(root, "docs/spec/01-agent-graph.md"), "utf8");
const source = markdown.match(/```mermaid\n([\s\S]*?)\n```/)[1];
const temporary = mkdtempSync(join(tmpdir(), "memory-agent-graph-"));
try {
  const input = join(temporary, "graph.mmd");
  const config = join(temporary, "config.json");
  const browser = join(temporary, "browser.json");
  writeFileSync(input, source);
  writeFileSync(config, JSON.stringify({ theme: "neutral", fontFamily: "Noto Sans CJK TC", flowchart: { useMaxWidth: false } }));
  writeFileSync(browser, JSON.stringify({ args: ["--no-sandbox"] }));
  execFileSync("npx", ["--yes", "--package", "@mermaid-js/mermaid-cli@11.16.0", "mmdc",
    "-i", input, "-o", resolve(root, "docs/spec/01-agent-graph.png"),
    "-c", config, "-p", browser, "-s", "3", "-w", "2800", "-b", "white"], { stdio: "inherit" });
  const png = readFileSync(resolve(root, "docs/spec/01-agent-graph.png"));
  console.log(JSON.stringify({ width: png.readUInt32BE(16), height: png.readUInt32BE(20) }));
} finally {
  // Only this script's freshly created, exact temporary directory.
  rmSync(temporary, { recursive: true });
}
