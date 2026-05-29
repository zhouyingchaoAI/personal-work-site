import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import './styles/element/index.scss'
import './styles/index.scss'
import App from './App.vue'
import { router } from './router'

createApp(App).use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
