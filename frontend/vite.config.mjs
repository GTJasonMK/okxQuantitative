// Vite 配置文件

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: 'dist-renderer',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/monaco-editor/esm/vs/')) {
            const parts = id.split('/monaco-editor/esm/vs/')[1]?.split('/') || [];
            const scope = parts[2] || '';

            if (parts[0] === 'platform') {
              return 'monaco-platform';
            }
            if (parts[0] === 'base' && parts[1] === 'browser') {
              if (scope === 'ui' || scope.startsWith('markdownRenderer')) {
                return 'monaco-base-browser-ui';
              }
            }
            if (parts[0] === 'editor' && parts[1] === 'common') {
              if (scope === 'model' || scope === 'services') {
                return 'monaco-editor-common-runtime';
              }
            }
            if (parts[0] === 'editor' && parts[1] === 'browser') {
              if (scope === 'services' || scope.startsWith('editorExtensions')) {
                return 'monaco-editor-browser-runtime';
              }
            }
            if (parts[0] === 'editor' && parts[1] === 'contrib') {
              if ([
                'snippet',
                'suggest',
                'inlineCompletions',
                'hover',
                'colorPicker',
                'inlayHints',
                'stickyScroll',
              ].includes(scope)) {
                return 'monaco-editor-contrib-assist';
              }
            }
            if (parts[0] === 'editor' || parts[0] === 'base') {
              const chunkKey = parts.slice(0, 3).filter(Boolean).join('-');
              return chunkKey ? `monaco-${chunkKey}` : 'monaco';
            }
            const chunkKey = parts.slice(0, 2).filter(Boolean).join('-');
            return chunkKey ? `monaco-${chunkKey}` : 'monaco';
          }
          if (id.includes('/node_modules/monaco-editor/')) {
            return 'monaco';
          }
          if (id.includes('/node_modules/lightweight-charts/')) {
            return 'vendor-lightweight-charts';
          }
          if (id.includes('/node_modules/echarts/') || id.includes('/node_modules/zrender/')) {
            return 'vendor-echarts';
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src/renderer'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
});
