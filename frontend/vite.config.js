import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'
import { outputDir } from './scripts/build-paths.mjs'
import { visualizer } from 'rollup-plugin-visualizer'

const __dirname = import.meta.dirname

// Plugin to stamp sw.js with a build-time cache version so the SW updates on every deploy
const swVersionPlugin = () => {
  const buildTimestamp = `v${Date.now()}`;
  return {
    name: 'sw-version',
    writeBundle(options) {
      const swPath = path.join(options.dir, 'sw.js');
      if (fs.existsSync(swPath)) {
        const content = fs.readFileSync(swPath, 'utf-8');
        fs.writeFileSync(swPath, content.replace(/__SW_CACHE_VERSION__/g, buildTimestamp));
        console.log(`✓ Service worker cache version stamped: ${buildTimestamp}`);
      }
    }
  };
};

// Plugin to serve /data and /output directories in dev mode
const serveDataPlugin = () => ({
  name: 'serve-data',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const url = new URL(req.url, 'http://localhost')
      // Strip base path for dev server routing
      let pathname = url.pathname
      // Serve data directory
      if (pathname.startsWith('/data/')) {
        const filePath = path.resolve(__dirname, '..', pathname.slice(1))
        if (fs.existsSync(filePath)) {
          const content = fs.readFileSync(filePath)
          res.setHeader('Content-Type', 'application/json')
          res.end(content)
          return
        }
      }
      // Serve output/screenshots directory
      if (pathname.startsWith('/output/')) {
        const filePath = path.resolve(__dirname, '..', pathname.slice(1))
        if (fs.existsSync(filePath)) {
          const content = fs.readFileSync(filePath)
          const ext = path.extname(filePath).toLowerCase()
          const mimeTypes = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' }
          res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream')
          res.end(content)
          return
        }
      }
      next()
    })
  }
})

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    serveDataPlugin(),
    swVersionPlugin(),
    mode === 'analyze' && visualizer({ filename: 'bundle-stats.html', gzipSize: true, open: false })
  ],

  // Base URL for custom domain (github-stats.makeboldspark.com)
  base: '/',

  // Public directory for static assets (favicon, etc)
  publicDir: 'public',

  // Build configuration
  build: {
    outDir: outputDir,
    emptyOutDir: true, // Clean build - data will be copied after
    
    // Always copy public directory (CNAME, manifest.json, sw.js, etc.)
    copyPublicDir: true,

    // Single bundle output optimization
    rollupOptions: {
      output: {
        // Generate predictable filenames
        entryFileNames: 'assets/site-[hash].js',
        chunkFileNames: 'assets/site-[hash].js',
        assetFileNames: (assetInfo) => {
          const assetName = assetInfo?.name || ''
          if (assetName.endsWith('.css')) {
            return 'assets/site-[hash].css'
          }
          return 'assets/[name]-[hash][extname]'
        },

        // Optimize chunk splitting
        manualChunks(id) {
          // Vendor chunks for better caching
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id.replaceAll('\\', '/'))) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/chart.js') || id.includes('node_modules/react-chartjs-2')) {
            return 'vendor-charts'
          }
          return undefined
        }
      }
    },

    // Bundle size optimizations
    cssCodeSplit: false, // Single CSS file
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.log in production
        drop_debugger: true
      }
    },

    // Performance budgets (warnings)
    chunkSizeWarningLimit: 170, // 170KB warning threshold (performance budget)

    // Source maps for debugging (disable for production)
    sourcemap: false
  },

  // Development server configuration
  server: {
    port: 5000,
    host: '0.0.0.0',
    open: false,
    allowedHosts: true,
    hmr: {
      clientPort: 443,
      protocol: 'wss'
    },
    fs: {
      // Allow serving files from parent directory (/data)
      allow: ['..']
    }
  },

  // Optimize deps to prevent React resolution issues
  optimizeDeps: {
    include: ['react', 'react-dom', 'react/jsx-runtime', 'react/jsx-dev-runtime'],
    exclude: []
  },

  // CSS Modules configuration
  css: {
    modules: {
      localsConvention: 'camelCase',
      generateScopedName: '[name]__[local]___[hash:base64:5]'
    }
  },

  // Resolve configuration
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@services': path.resolve(__dirname, './src/services'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@styles': path.resolve(__dirname, './src/styles')
    }
  },

  // Test configuration (for Vitest)
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.config.js'
      ]
    }
  }
}))
