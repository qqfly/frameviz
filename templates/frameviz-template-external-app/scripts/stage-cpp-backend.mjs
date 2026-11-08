#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'

const appRoot = process.cwd()
const defaultBinaryName = process.platform === 'win32' ? 'frameviz_external_backend.exe' : 'frameviz_external_backend'
const sourceBinary =
  process.env.FRAMEVIZ_BACKEND_CPP_BIN?.trim() ||
  path.join(appRoot, 'cpp', 'build', 'bin', defaultBinaryName)
const srcPath = path.resolve(appRoot, sourceBinary)
const targetDir = path.join(appRoot, 'src-tauri', 'resources', 'cpp')
const targetPath = path.join(targetDir, defaultBinaryName)

if (!fs.existsSync(srcPath) || !fs.statSync(srcPath).isFile()) {
  console.error(`[backend:cpp:stage] backend binary not found: ${srcPath}`)
  console.error('[backend:cpp:stage] build first: pnpm backend:cpp:build')
  process.exit(1)
}

fs.mkdirSync(targetDir, { recursive: true })
fs.copyFileSync(srcPath, targetPath)
if (process.platform !== 'win32') {
  fs.chmodSync(targetPath, 0o755)
}

console.log(`[backend:cpp:stage] staged: ${targetPath}`)
