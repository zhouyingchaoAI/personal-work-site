import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView/index.vue'
import WorkspaceView from '../views/WorkspaceView/index.vue'
import { authState, ensureSession } from '../services/authSession'
import { defaultMenuForUser, isMenuId, isMenuVisible, lastVisitedMenu, rememberLastMenu } from '../layout/menu'

export const router = createRouter({
  // 路由 base 固定为站点根 '/'，与静态资源 base（/personal-office-assistant/）解耦：
  // 公开 URL 为 office.chencytech.com/workspace/…，不带 /personal-office-assistant 前缀。
  history: createWebHistory('/'),
  routes: [
    // 从站点根进入时固定落到首页，避免上次访问菜单把域名入口带到业务页。
    { path: '/', redirect: '/workspace/dashboard' },
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/workspace/:menu?', component: WorkspaceView },
  ],
})

router.beforeEach(async (to) => {
  await ensureSession(true)
  if (to.path === '/login') {
    return authState.user ? `/workspace/${lastVisitedMenu()}` : true
  }
  if (!authState.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path.startsWith('/workspace')) {
    const menu = String(to.params.menu || 'dashboard')
    if (!isMenuId(menu) || !isMenuVisible(menu, authState.user)) {
      return `/workspace/${defaultMenuForUser(authState.user)}`
    }
  }
  return true
})

router.afterEach((to) => {
  if (to.path.startsWith('/workspace')) {
    const menu = String(to.params.menu || '')
    if (isMenuId(menu)) rememberLastMenu(menu)
  }
})
