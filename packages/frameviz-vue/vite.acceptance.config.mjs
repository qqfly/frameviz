import {defineConfig} from 'vite';
import {resolve} from 'node:path';
export default defineConfig({base:'./',build:{outDir:'dist-acceptance',emptyOutDir:true,rollupOptions:{input:resolve('acceptance.html')}}});
