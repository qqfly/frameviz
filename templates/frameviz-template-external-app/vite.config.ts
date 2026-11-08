import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const templateRoot = fileURLToPath(new URL('.', import.meta.url))
const workspaceAliasCandidates: Record<string, string> = {
  '@frameviz/vue': '../../packages/frameviz-vue/src/index.ts',
  '@frameviz/core': '../../packages/frameviz-core/src/index.ts',
  '@frameviz/protocol': '../../packages/frameviz-protocol/src/index.ts',
}

const workspaceAliases = Object.fromEntries(
  Object.entries(workspaceAliasCandidates)
    .map(([pkg, relPath]) => [pkg, path.resolve(templateRoot, relPath)])
    .filter(([, absPath]) => fs.existsSync(absPath)),
)

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: workspaceAliases,
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  build: {
    target: 'esnext',
    minify: false,
    sourcemap: true,
  },
  clearScreen: false,
})
