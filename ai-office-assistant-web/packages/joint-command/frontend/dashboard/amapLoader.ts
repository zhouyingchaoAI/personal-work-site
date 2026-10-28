// Only one SDK instance per page. The security secret is injected by our server proxy.
let pending: Promise<any> | undefined
let loadedKey = ''
export function loadAmap(key: string): Promise<any> {
  const host = window as any
  if (loadedKey && loadedKey !== key) return Promise.reject(new Error('高德 Key 已更新，请刷新页面'))
  if (pending) return pending
  loadedKey = key
  host._AMapSecurityConfig = { serviceHost: `${location.origin}/personal-office-assistant/api/crm/amap-proxy/_AMapService` }
  pending = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const timer = window.setTimeout(() => fail(), 20000)
    const fail = () => { clearTimeout(timer); script.remove(); pending = undefined; loadedKey = ''; reject(new Error('高德加载失败，请检查凭据、域名白名单和网络')) }
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&plugin=AMap.DistrictSearch,AMap.Scale,AMap.ToolBar`
    script.onload = () => { clearTimeout(timer); host.AMap ? resolve(host.AMap) : fail() }
    script.onerror = fail
    document.head.appendChild(script)
  })
  return pending
}
