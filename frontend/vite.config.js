import { defineConfig } from 'vite'

// Backend tunnel credentials (base64 encoded for Basic Auth)
const BACKEND_USER = 'user'
const BACKEND_PASS = 'd9dfb395521de04779f46acef0a87e13'
const BACKEND_AUTH = Buffer.from(`${BACKEND_USER}:${BACKEND_PASS}`).toString('base64')

export default defineConfig({
  server: {
    host: '0.0.0.0',
    allowedHosts: ['ap-automation-app-tunnel-fobq6juc.devinapps.com', 'localhost'],
    proxy: {
      '/api': {
        target: 'https://codingagent-app-tunnel-m76blv1y.devinapps.com',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Authorization', `Basic ${BACKEND_AUTH}`)
          })
        }
      }
    }
  }
})
