#!/usr/bin/env node
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

if (process.platform !== 'linux') {
  console.error('[deb:install] this command is only available on Linux')
  process.exit(1)
}

const appRoot = process.cwd()
const debDir = path.join(appRoot, 'src-tauri', 'target', 'release', 'bundle', 'deb')

if (!fs.existsSync(debDir)) {
  console.error(`[deb:install] deb directory not found: ${debDir}`)
  console.error('[deb:install] run "pnpm tauri:build" first')
  process.exit(1)
}

const debFiles = fs
  .readdirSync(debDir)
  .filter((name) => name.endsWith('.deb'))
  .map((name) => {
    const fullPath = path.join(debDir, name)
    return {
      name,
      fullPath,
      mtime: fs.statSync(fullPath).mtimeMs,
    }
  })
  .sort((a, b) => b.mtime - a.mtime)

if (debFiles.length === 0) {
  console.error(`[deb:install] no .deb found in ${debDir}`)
  console.error('[deb:install] run "pnpm tauri:build" first')
  process.exit(1)
}

const deb = debFiles[0]
const stagedPath = path.join(os.tmpdir(), deb.name)
fs.copyFileSync(deb.fullPath, stagedPath)
fs.chmodSync(stagedPath, 0o644)

console.log(`[deb:install] staged package: ${stagedPath}`)
console.log('[deb:install] running: sudo apt install <staged package>')

const result = spawnSync('sudo', ['apt', 'install', stagedPath], {
  stdio: 'inherit',
  env: process.env,
})

if (result.error) {
  console.error(result.error)
  process.exit(1)
}
process.exit(result.status ?? 0)
