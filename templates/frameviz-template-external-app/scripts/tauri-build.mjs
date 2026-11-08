#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const argv = process.argv.slice(2)
const backendFlagIndex = argv.indexOf('--backend')
const backend = backendFlagIndex >= 0 && argv[backendFlagIndex + 1] ? argv[backendFlagIndex + 1] : 'py'

if (!['py', 'cpp'].includes(backend)) {
  console.error(`[tauri:build] invalid --backend=${backend}, expected py|cpp`)
  process.exit(1)
}

const appRoot = process.cwd()
const stagedCppDir = path.join(appRoot, 'src-tauri', 'resources', 'cpp')

const resolveBundleTarget = () => {
  const raw = process.env.FRAMEVIZ_TAURI_BUNDLE?.trim()
  if (raw) return raw
  if (process.platform === 'darwin') return 'dmg'
  if (process.platform === 'linux') return 'deb'
  return 'app'
}

const run = (command, args) => {
  const result = spawnSync(command, args, {
    cwd: appRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: process.env,
  })
  if (typeof result.status === 'number' && result.status !== 0) {
    process.exit(result.status)
  }
  if (result.error) {
    console.error(result.error)
    process.exit(1)
  }
}

if (backend === 'cpp') {
  run('pnpm', ['run', 'backend:cpp:build'])
  run('pnpm', ['run', 'backend:cpp:stage'])
} else if (fs.existsSync(stagedCppDir)) {
  fs.rmSync(stagedCppDir, { recursive: true, force: true })
  console.log('[tauri:build] removed staged cpp backend (python mode)')
}

const bundleTarget = resolveBundleTarget()
console.log(`[tauri:build] bundle target: ${bundleTarget}`)
run('pnpm', ['exec', 'tauri', 'build', '--bundles', bundleTarget])
