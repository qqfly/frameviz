import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
    root: '.',
    base: './',
    build: {
        outDir: 'dist',
        emptyOutDir: true,
        assetsDir: 'assets',
        rollupOptions: {
            input: {
                main: resolve(__dirname, 'index.html'),
                launcher: resolve(__dirname, 'launcher.html'),
            },

        },
    },
    server: {
        fs: {
            allow: ['..'], // Allow access to workspace packages
        },
    },
});
