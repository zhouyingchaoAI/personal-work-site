import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import './styles/element/index.scss'
import './styles/index.scss'
import App from './App.vue'
import { router } from './router'

createApp(App).use(ElementPlus).use(router).mount('#app')
