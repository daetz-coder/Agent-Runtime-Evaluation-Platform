import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('./wiki/WikiAgentApp.vue'),
    },
  ],
})

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
