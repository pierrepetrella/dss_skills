# `vite.config.ts` (Code Studio base path)

Replace your `vite.config.ts` with this pattern:

```ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dotenv from 'dotenv'

dotenv.config()

const clientPort = String(process.env['VITE_CLIENT_PORT'] ?? '4200')
const basePath = process.env[`DKU_CODE_STUDIO_BROWSER_PATH_${clientPort}`]
  ? String(process.env[`DKU_CODE_STUDIO_BROWSER_PATH_${clientPort}`]) + '/'
  : ''

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: Number(clientPort),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  base: basePath,
})
```
