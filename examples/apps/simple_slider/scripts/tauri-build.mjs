#!/usr/bin/env node
import { spawnSync } from 'node:child_process'

const resolveBundleTarget = () => {
  const raw = process.env.FRAMEVIZ_TAURI_BUNDLE?.trim()
  if (raw) return raw
  if (process.platform === 'darwin') return 'dmg'
  if (process.platform === 'linux') return 'deb'
  return 'app'
}

const bundleTarget = resolveBundleTarget()
console.log(`[tauri:build] bundle target: ${bundleTarget}`)

const result = spawnSync('pnpm', ['exec', 'tauri', 'build', '--bundles', bundleTarget], {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: process.env,
})

if (result.error) {
  console.error(result.error)
  process.exit(1)
}

process.exit(result.status ?? 0)
