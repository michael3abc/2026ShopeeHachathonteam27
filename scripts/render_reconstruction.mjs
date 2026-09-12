// Render only reconstruction diagram sources. No application code or raster edits.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(join(tmpdir(), 'reconstruction-diagrams-'));
try {
  const config = join(temporary, 'config.json');
  const browser = join(temporary, 'browser.json');
  writeFileSync(config, JSON.stringify({ theme: 'neutral', fontFamily: 'Noto Sans CJK TC', flowchart: { useMaxWidth: false } }));
  writeFileSync(browser, JSON.stringify({ args: ['--no-sandbox'] }));
  for (const name of ['architecture', 'sequence']) {
    const prefix = join(root, 'docs/reconstruction/diagrams', name);
    execFileSync('npx', ['--yes', '--package', '@mermaid-js/mermaid-cli@11.16.0', 'mmdc', '-i', prefix + '.mmd', '-o', prefix + '.png', '-c', config, '-p', browser, '-s', '3', '-w', '2400', '-b', 'white'], { stdio: 'inherit' });
    const png = readFileSync(prefix + '.png');
    console.log(JSON.stringify({ name, width: png.readUInt32BE(16), height: png.readUInt32BE(20) }));
  }
} finally {
  rmSync(temporary, { recursive: true });
}
