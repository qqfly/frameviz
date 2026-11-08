#!/usr/bin/env node
// Bundle only reachable runtime assets; never copy the repository into an app.
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
for (const name of ['@frameviz/protocol', '@frameviz/core', '@frameviz/web-viewer']) {
  execFileSync('pnpm', ['--filter', name, 'build'], { cwd: root, stdio: 'inherit' });
}
