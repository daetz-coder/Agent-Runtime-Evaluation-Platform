import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

const apiTarget = process.env.VITE_EVAL_API_BASE || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router'],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // Single source of truth for Wiki UI (also used by standalone wiki_agent frontend)
      '@wiki': path.resolve(__dirname, '../app/wiki_agent/frontend/src/wiki'),
    },
  },
  server: {
    port: 3000,
    fs: {
      // Allow importing Wiki UI from app/wiki_agent/frontend outside this package root
      allow: [path.resolve(__dirname, '..')],
    },
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/health': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ['legacy-js-api'],
      },
    },
  },
})
