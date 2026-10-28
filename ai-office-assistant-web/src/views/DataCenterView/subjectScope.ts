import { computed, inject, type ComputedRef, type InjectionKey, type Ref } from 'vue'
import type { DcStorageMap, DcSubject } from '../../services/personalWorkApi'

export interface SubjectScope {
  selected: Ref<string>
  snapshot: Ref<DcStorageMap | null>
  subject: ComputedRef<DcSubject | undefined>
  subjects: ComputedRef<DcSubject[]>
}

export const subjectScopeKey: InjectionKey<SubjectScope> = Symbol('datacenter-subject')

export function useSubjectScope() {
  const scope = inject(subjectScopeKey)
  if (!scope) throw new Error('缺少数据中台助手上下文')
  const scoped = computed(() => scope.selected.value !== 'all')
  const label = computed(() => scope.subject.value?.label || '全部助手与平台')
  return { ...scope, scoped, label }
}
