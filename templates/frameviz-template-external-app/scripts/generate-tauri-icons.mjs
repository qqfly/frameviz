import { spawnSync } from 'node:child_process'
import path from 'node:path'
const source = process.argv[2] || path.join('src-tauri', 'icons', 'icon.png')
const result = spawnSync('pnpm', ['exec', 'tauri', 'icon', source], { stdio: 'inherit' })
process.exit(result.status ?? 1)
