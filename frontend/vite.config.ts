import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Il frontend chiama percorsi relativi sotto /api: in sviluppo Vite li inoltra
// al backend FastAPI (porta 8000) strippando il prefisso. In produzione nginx
// fa lo stesso proxy, così il frontend non ha mai un URL di backend hardcoded.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
