#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const targets = [
  'node_modules',
  'dist',
  path.join('cpp', 'build'),
  path.join('src-tauri', 'target'),
  path.join('src-tauri', 'resources', 'cpp'),
]

for (const target of targets) {
  const abs = path.join(root, target)
  if (fs.existsSync(abs)) {
    fs.rmSync(abs, { recursive: true, force: true })
    console.log(`[clean] removed ${target}`)
  }
}

console.log('[clean] done')
