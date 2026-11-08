#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fs.realpathSync(fileURLToPath(new URL('./dist/', import.meta.url)));
const port = Number(process.env.FRAMEVIZ_HTTP_PORT || 8080);
const mime = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.png':'image/png', '.svg':'image/svg+xml' };
http.createServer((req, res) => {
  try {
    if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405).end(); return; }
    const url = new URL(req.url, 'http://localhost');
    const name = decodeURIComponent(url.pathname);
    if (name.split('/').some(part => part.startsWith('.')) || name.includes('\\')) throw new Error('Invalid path');
    const file = fs.realpathSync(path.join(root, name === '/' ? 'index.html' : name));
    if (!file.startsWith(root + path.sep) || !fs.statSync(file).isFile()) throw new Error('Invalid path');
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer' });
    if (req.method === 'HEAD') res.end(); else fs.createReadStream(file).pipe(res);
  } catch { res.writeHead(404).end('Not found'); }
}).listen(port, '127.0.0.1', () => console.log(`FrameViz: http://127.0.0.1:${port}/`));
