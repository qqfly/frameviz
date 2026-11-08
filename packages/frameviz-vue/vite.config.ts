import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import dts from 'vite-plugin-dts'
import { resolve } from 'path'

export default defineConfig({
    plugins: [
        vue(),
        dts({
            insertTypesEntry: true,
        }),
    ],
    build: {
        lib: {
            entry: resolve(__dirname, 'src/index.ts'),
            name: 'FrameVizVue',
            formats: ['es', 'cjs'],
            fileName: (format) => `index.${format === 'es' ? 'js' : 'cjs'}`,
        },
        rollupOptions: {
            external: ['vue', '@frameviz/core', '@frameviz/protocol'],
            output: {
                globals: {
                    vue: 'Vue',
                    '@frameviz/core': 'FrameVizCore',
                    '@frameviz/protocol': 'FrameVizProtocol',
                },
            },
        },
    },
})
