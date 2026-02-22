import path from 'path'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'
import { viteMockServe } from 'vite-plugin-mock'
import Components from 'unplugin-vue-components/vite'
import UnoCSS from 'unocss/vite'
import { presetAttributify, presetIcons, presetUno } from 'unocss'
import mkcert from 'vite-plugin-mkcert'
import AutoImport from 'unplugin-auto-import/vite'
import setting from './src/settings'
const prodMock = setting.openProdMock
// import { visualizer } from 'rollup-plugin-visualizer'
const pathSrc = path.resolve(__dirname, 'src')

import vitePluginSetupExtend from './src/plugins/vite-plugin-setup-extend/index'

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '') // Load environment variables

  return {
    base: setting.viteBasePath,
    define: {
      //define global var
      GLOBAL_STRING: JSON.stringify('i am global var from vite.config.js define'),
      GLOBAL_VAR: { test: 'i am global var from vite.config.js define' }
    },
    clearScreen: false, // Set to false to avoid Vite clearing screen and missing key terminal output
    server: {
      hmr: { overlay: false }, // Set server.hmr.overlay to false to disable development server error overlay for easier error viewing
      port: 8502, // Type: number - specify server port;
      open: false, // Type: boolean | string - automatically open app in browser on server start;
      host: true,
      https: false,
      //https://cn.vitejs.dev/config/server-options.html#server-proxy
      proxy: env.VITE_PROXY_BASE_URL && env.VITE_PROXY_URL ? {
        [env.VITE_PROXY_BASE_URL]: {
          target: env.VITE_PROXY_URL.replace(/\/$/, ''),
          changeOrigin: true,
          rewrite: (path) => path.replace(new RegExp(`^${env.VITE_PROXY_BASE_URL}`), '')
        }
      } : {}
    },
    preview: {
      port: 5006,
      host: true,
      strictPort: true
    },
    plugins: [
      vue(),
      vueJsx(),
      UnoCSS({
        presets: [presetUno(), presetAttributify(), presetIcons()]
      }),
      mkcert(),
      //compatible with old browsers
      // legacy({
      //   targets: ['chrome 52'],
      //   additionalLegacyPolyfills: ['regenerator-runtime/runtime']
      // }),
      createSvgIconsPlugin({
        iconDirs: [path.resolve(process.cwd(), 'src/icons/common'), path.resolve(process.cwd(), 'src/icons/nav-bar')],
        symbolId: 'icon-[dir]-[name]'
      }),
      //https://github.com/anncwb/vite-plugin-mock/blob/HEAD/README.zh_CN.md
      viteMockServe({
        supportTs: true,
        mockPath: 'mock',
        localEnabled: command === 'serve',
        prodEnabled: prodMock,
        injectCode: `
          import { setupProdMockServer } from './mock-prod-server';
          setupProdMockServer();
        `,
        logger: true
      }),
      // VueSetupExtend(),using  DefineOptions instant of it
      //https://github.com/antfu/unplugin-auto-import/blob/HEAD/src/types.ts
      Components({
        dirs: ['src/components', 'src/icons'],
        extensions: ['vue'],
        deep: true,
        dts: './typings/components.d.ts'
      }),
      AutoImport({
        imports: [
          'vue',
          'vue-router',
          {
            'pinia/dist/pinia': ['storeToRefs']
          }
        ],
        dirs: ['src/hooks/**', 'src/utils/**', 'src/store/**',],
        eslintrc: {
          enabled: true, // Default `false`
          filepath: './eslintrc/.eslintrc-auto-import.json', // Default `./.eslintrc-auto-import.json`
          globalsPropValue: true // Default `true`, (true | false | 'readonly' | 'readable' | 'writable' | 'writeable')
        },
        dts: './typings/auto-imports.d.ts'
      }),
      // auto config of index.html title
      // createHtmlPlugin({
      //   inject: { data: { title: setting.title } }
      // }),
      vitePluginSetupExtend({ inject: { title: setting.title } })
      // visualizer({
      //   open: true,
      //   gzipSize: true,
      //   brotliSize: true
      // })
    ],
    build: {
      chunkSizeWarningLimit: 10000, // Suppress chunk size warnings, default 500k
      assetsDir: 'static/assets',
      rollupOptions: {
        output: {
          chunkFileNames: 'static/js/[name]-[hash].js',
          entryFileNames: 'static/js/[name]-[hash].js',
          assetFileNames: 'static/[ext]/[name]-[hash].[ext]'
        }
      }
    },
    resolve: {
      alias: {
        '@/': `${pathSrc}/`,
        'vue-i18n': 'vue-i18n/dist/vue-i18n.cjs.js' //remove i18n waring
      }
    },
    optimizeDeps: {
      //include: [...optimizeDependencies,...optimizeElementPlus] //on-demand element-plus use this
      include: ['moment-mini']
    }
  }
})
