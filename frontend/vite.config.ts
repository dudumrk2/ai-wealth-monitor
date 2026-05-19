/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React runtime — cached across all pages
          'vendor-react':     ['react', 'react-dom', 'react-router-dom'],
          // Firebase SDK — large but rarely changes
          'vendor-firebase':  ['firebase/app', 'firebase/auth', 'firebase/firestore'],
          // Charts — heavy, only needed on dashboard/stocks pages
          'vendor-charts':    ['recharts'],
          // Animation — needed on most pages but separate from charts
          'vendor-animation': ['framer-motion'],
          // UI utilities — tiny, but worth isolating
          'vendor-ui':        ['lucide-react', 'clsx', 'tailwind-merge'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['tests/**', 'node_modules/**'],
  },
})

