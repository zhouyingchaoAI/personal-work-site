// Public administrative geometry only: no customer records or API credentials.
type Point = [number, number]
type Geometry = { name: string; level: string; center?: Point; boundaries: Point[][] }
const memory = new Map<string, { at: number; value: Geometry }>()
const pending = new Map<string, Promise<Geometry | null>>()
const queue: (() => void)[] = []
let active = 0
const lifetime = 24 * 60 * 60 * 1000
const prefix = 'crm-public-district-v1:'
const normalize = (name: string) => name.replace(/(?:壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$/, '')
function point(value: any): Point | undefined {
  const lng = Number(value?.getLng?.() ?? value?.lng ?? value?.[0])
  const lat = Number(value?.getLat?.() ?? value?.lat ?? value?.[1])
  return Number.isFinite(lng) && Number.isFinite(lat) ? [lng, lat] : undefined
}
function drain() { while (active < 4 && queue.length) { active++; queue.shift()!() } }
export function searchDistrict(sdk: any, name: string, level: string, extensions: 'base' | 'all'): Promise<Geometry | null> {
  const key = `${level}:${extensions}:${name}`
  let entry = memory.get(key)
  if (!entry) {
    try { entry = JSON.parse(sessionStorage.getItem(prefix + key) || 'null') || undefined } catch { /* storage unavailable */ }
  }
  if (entry && Date.now() - entry.at < lifetime && Array.isArray(entry.value?.boundaries)) {
    memory.set(key, entry)
    return Promise.resolve(entry.value)
  }
  if (pending.has(key)) return pending.get(key)!
  const request = new Promise<Geometry | null>(resolve => {
    const run = () => {
      let finished = false
      const finish = (value: Geometry | null) => {
        if (finished) return
        finished = true; clearTimeout(timer)
        if (value) {
          const entry = { at: Date.now(), value }
          memory.set(key, entry)
          if (memory.size > 256) memory.delete(memory.keys().next().value!)
          try { sessionStorage.setItem(prefix + key, JSON.stringify(entry)) } catch { /* memory cache still works */ }
        }
        active--; resolve(value); drain()
      }
      const timer = setTimeout(() => finish(null), extensions === 'all' ? 12000 : 10000)
      try {
        new sdk.DistrictSearch({ level, subdistrict: 0, extensions }).search(name, (status: string, result: any) => {
          const record = status === 'complete' ? result?.districtList?.find((item: any) =>
            typeof item.name === 'string' && normalize(item.name) === normalize(name) &&
            (item.level === level || (level === 'city' && item.level === 'province'))) : null
          if (!record) { finish(null); return }
          const center = point(record.center)
          const boundaries = (record.boundaries || []).map((path: any[]) => path.map(point).filter(Boolean)) as Point[][]
          finish((extensions === 'all' ? boundaries.length : center) ? { name: record.name, level: record.level, center, boundaries } : null)
        })
      } catch { finish(null) }
    }
    // User-requested city markers take priority over background boundary work.
    if (extensions === 'base') queue.unshift(run)
    else queue.push(run)
    drain()
  }).finally(() => pending.delete(key))
  pending.set(key, request)
  return request
}
