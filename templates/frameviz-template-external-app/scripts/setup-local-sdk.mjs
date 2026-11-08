import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'

function fail(message) {
  console.error(`[setup:local-sdk] ${message}`)
  process.exit(1)
}

const repoRootArg = process.argv[2]
const repoRoot = path.resolve(repoRootArg ?? process.env.FRAMEVIZ_REPO ?? '')

if (!repoRootArg && !process.env.FRAMEVIZ_REPO) {
  fail(
    'missing FrameViz repo path. Use: FRAMEVIZ_REPO=/path/to/FrameViz pnpm run setup:local-sdk',
  )
}

const requiredPackages = [
  ['@frameviz/protocol', path.join(repoRoot, 'packages/frameviz-protocol')],
  ['@frameviz/core', path.join(repoRoot, 'packages/frameviz-core')],
  ['@frameviz/vue', path.join(repoRoot, 'packages/frameviz-vue')],
]

for (const [name, dir] of requiredPackages) {
  if (!fs.existsSync(path.join(dir, 'package.json'))) {
    fail(`cannot find ${name} at ${dir}`)
  }
}

const addArgs = [
  'add',
  ...requiredPackages.map(([name, dir]) => `${name}@link:${dir}`),
]

console.log(`[setup:local-sdk] linking packages from ${repoRoot}`)
const result = spawnSync('pnpm', addArgs, {
  stdio: 'inherit',
  shell: process.platform === 'win32',
})

if (result.status !== 0) {
  fail('pnpm add failed')
}

console.log('[setup:local-sdk] done')
