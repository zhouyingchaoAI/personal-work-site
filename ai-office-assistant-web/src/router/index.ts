import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView/index.vue'
import WorkspaceView from '../views/WorkspaceView/index.vue'
import { authState, ensureSession } from '../services/authSession'
import { defaultMenuForUser, isMenuId, isMenuVisible } from '../layout/menu'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/workspace/weekly' },
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/workspace/:menu?', component: WorkspaceView },
  ],
})

router.beforeEach(async (to) => {
  await ensureSession()
  if (to.path === '/login') {
    return authState.user ? '/workspace/weekly' : true
  }
  if (!authState.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path.startsWith('/workspace')) {
    const menu = String(to.params.menu || 'weekly')
    if (!isMenuId(menu) || !isMenuVisible(menu, authState.user)) {
      return `/workspace/${defaultMenuForUser(authState.user)}`
    }
  }
  return true
})
