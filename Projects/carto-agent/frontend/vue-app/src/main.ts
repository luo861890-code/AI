/**
 * Vue 3 应用入口
 * 挂载 Pinia 状态管理并启动根组件 App.vue。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
