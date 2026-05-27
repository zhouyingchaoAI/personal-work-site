import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const defaultBackendUrl = 'https://yfdemo.chencytech.com/personal-office-assistant'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = (process.env.VITE_PERSONAL_WORK_BACKEND_URL || env.VITE_PERSONAL_WORK_BACKEND_URL || defaultBackendUrl).replace(/\/$/, '')
  const backend = new URL(backendUrl)
  const backendBasePath = backend.pathname === '/' ? '' : backend.pathname

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: 8746,
      strictPort: true,
      proxy: {
        '/personal-work-api': {
          target: backend.origin,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-api/, `${backendBasePath}/api`),
        },
        '/personal-work-download': {
          target: backend.origin,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-download/, `${backendBasePath}/download`),
        },
        '/personal-work-resource': {
          target: backend.origin,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-resource/, backendBasePath),
        },
        '/openclaw': {
          target: backend.origin,
          changeOrigin: true,
        },
        '/api': {
          target: backend.origin,
          changeOrigin: true,
        },
      },
    },
  }
})
