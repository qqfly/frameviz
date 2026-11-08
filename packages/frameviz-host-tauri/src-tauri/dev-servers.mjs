#!/usr/bin/env node
/**
 * Start dev servers for Tauri:
 * - Web viewer HTTP server (8080)
 * - Rust WebSocket host is started by Tauri (9527)
 *
 * This keeps running until terminated, and prints cross-platform
 * instructions when a port is already in use.
 */
import { spawn } from 'child_process';
import net from 'net';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../../..');

const HTTP_PORT = 8080;

function portAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.on('error', (err) => {
      if (err && err.code === 'EADDRINUSE') {
        resolve(false);
      } else {
        resolve(false);
      }
    });
    server.listen({ port, host: '127.0.0.1' }, () => {
      server.close(() => resolve(true));
    });
  });
}

function printPortInUse(port) {
  console.error(`[DEV] Port ${port} is already in use.`);
  console.error('[DEV] Stop the process using this port, then retry.');
  console.error('[DEV] macOS/Linux: lsof -iTCP:' + port + ' -sTCP:LISTEN');
  console.error('[DEV]             kill -9 <pid>');
  console.error('[DEV] Windows:   netstat -ano | findstr :' + port);
  console.error('[DEV]            taskkill /PID <pid> /F');
}

async function main() {
  const httpFree = await portAvailable(HTTP_PORT);
  if (!httpFree) {
    printPortInUse(HTTP_PORT);
    process.exit(1);
  }

  const httpScript = path.join(repoRoot, 'packages', 'frameviz-web-viewer', 'serve.mjs');
  const httpProc = spawn(process.execPath, [httpScript], {
    stdio: 'inherit',
  });

  let shuttingDown = false;
  const shutdown = (code = 0) => {
    if (shuttingDown) return;
    shuttingDown = true;
    if (httpProc && !httpProc.killed) {
      httpProc.kill();
    }
    process.exit(code);
  };

  httpProc.on('exit', (code) => shutdown(code ?? 0));
  process.on('SIGINT', () => shutdown(0));
  process.on('SIGTERM', () => shutdown(0));
}

main().catch((err) => {
  console.error('[DEV] Failed to start dev servers:', err);
  process.exit(1);
});
