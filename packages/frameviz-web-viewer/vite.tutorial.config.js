import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const license = [
  'LICENSE',
  'THIRD_PARTY_LICENSES/three-MIT.txt',
].map(path => readFileSync(new URL(path, import.meta.url), 'utf8')).join('\n\n');

export default defineConfig({
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: {
      entry: resolve('tutorial.ts'),
      name: 'FrameVizTutorial',
      formats: ['iife'],
      fileName: () => 'tutorial.js',
    },
    rollupOptions: { output: { banner: '/*!\n' + license + '\n*/' } },
  },
});
