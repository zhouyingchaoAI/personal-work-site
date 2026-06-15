import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 相对路径 = 生产同源部署（API 跟随访问域名，office/yfdemo/LAN 入口都不跨域）。
const defaultBackendUrl = '/personal-office-assistant'
// 开发模式（vite dev proxy）需要绝对地址才能转发，相对配置时回退到 LAN 后端。
const devProxyFallback = 'http://10.1.6.230:8765'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = (process.env.VITE_PERSONAL_WORK_BACKEND_URL || env.VITE_PERSONAL_WORK_BACKEND_URL || defaultBackendUrl).replace(/\/$/, '')
  const isAbsolute = /^https?:\/\//i.test(backendUrl)
  const backend = new URL(backendUrl, devProxyFallback)
  const proxyTarget = isAbsolute ? backend.origin : devProxyFallback
  const backendBasePath = backend.pathname === '/' ? '' : backend.pathname

  const appBase = backendBasePath ? backendBasePath + '/' : '/'

  return {
    base: appBase,
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: 8746,
      strictPort: true,
      proxy: {
        '/personal-work-api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-api/, `${backendBasePath}/api`),
        },
        '/personal-work-download': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-download/, `${backendBasePath}/download`),
        },
        '/personal-work-resource': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/personal-work-resource/, backendBasePath),
        },
        '/openclaw': {
          target: proxyTarget,
          changeOrigin: true,
        },
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
