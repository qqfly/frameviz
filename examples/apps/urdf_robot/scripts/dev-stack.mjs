#!/usr/bin/env node
import { spawn } from 'node:child_process'

const argv = process.argv.slice(2)

const readFlag = (flag, fallback) => {
  const idx = argv.indexOf(flag)
  if (idx < 0 || idx + 1 >= argv.length) return fallback
  return argv[idx + 1]
}

const mode = readFlag('--mode', 'web')
const backend = readFlag('--backend', 'py')

if (!['web', 'tauri'].includes(mode)) {
  console.error(`[dev-stack] invalid --mode=${mode}, expected web|tauri`)
  process.exit(1)
}

if (!['py', 'cpp'].includes(backend)) {
  console.error(`[dev-stack] invalid --backend=${backend}, expected py|cpp`)
  process.exit(1)
}

const uiScript = mode === 'tauri' ? 'tauri:dev' : 'dev'
const backendScript = backend === 'cpp' ? 'backend:cpp' : 'backend:py'
const children = []

let shuttingDown = false
let exitCode = 0

const spawnPnpmScript = (scriptName, label) => {
  const child = spawn('pnpm', ['run', scriptName], {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: process.env,
  })
  child.__label = label
  children.push(child)
  return child
}

const shutdown = (reason, code = 0) => {
  if (shuttingDown) return
  shuttingDown = true
  exitCode = code

  if (reason) {
    console.log(`[dev-stack] stopping: ${reason}`)
  }

  for (const child of children) {
    try {
      child.kill('SIGTERM')
    } catch {
      // Ignore if already exited.
    }
  }

  setTimeout(() => {
    for (const child of children) {
      try {
        child.kill('SIGKILL')
      } catch {
        // Ignore if already exited.
      }
    }
  }, 1500).unref()

  setTimeout(() => process.exit(exitCode), 1800).unref()
}

const bindExit = (child, name) => {
  child.on('exit', (code, signal) => {
    if (shuttingDown) return
    const normalizedCode = signal ? 0 : (code ?? 0)
    shutdown(`${name} exited (code=${normalizedCode}${signal ? `, signal=${signal}` : ''})`, normalizedCode)
  })
}

console.log(`[dev-stack] mode=${mode}, backend=${backend}`)
console.log(`[dev-stack] backend script: ${backendScript}`)
console.log(`[dev-stack] ui script: ${uiScript}`)

const backendProcess = spawnPnpmScript(backendScript, 'backend')
bindExit(backendProcess, 'backend')

setTimeout(() => {
  if (shuttingDown) return
  const uiProcess = spawnPnpmScript(uiScript, 'ui')
  bindExit(uiProcess, 'ui')
}, 300)

process.on('SIGINT', () => shutdown('SIGINT', 0))
process.on('SIGTERM', () => shutdown('SIGTERM', 0))

