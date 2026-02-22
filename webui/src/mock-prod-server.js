import { createProdMockServer } from 'vite-plugin-mock/es/createProdMockServer'
//https://cn.vitejs.dev/guide/features.html#glob-import
const modulesFiles = import.meta.glob('../mock/*', { eager: true })
let modules = []
for (const filePath in modulesFiles) {
  modules = modules.concat(modulesFiles[filePath].default)
}
export function setupProdMockServer() {
  createProdMockServer([...modules])
}
