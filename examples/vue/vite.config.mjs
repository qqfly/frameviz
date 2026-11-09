import {fileURLToPath} from 'node:url';
const path = relative => fileURLToPath(new URL(relative, import.meta.url));
export default {
  root: path('./'), base: './',
  resolve: {alias: {
    '@frameviz/vue': path('../../packages/frameviz-vue/dist/index.js'),
    'vue': path('../../packages/frameviz-vue/node_modules/vue/dist/vue.esm-bundler.js'),
  }},
  build: {outDir: path('./dist'), emptyOutDir: true,
    rollupOptions: {input: path('./embedded_viewer.html')}},
};
