<script setup lang="ts">
import RelationGraph from '../RelationGraph.vue'
import type { CrmGraphEdge, CrmGraphNode } from '../../../services/personalWorkApi'

defineProps<{
  organizationGraph?: { nodes: CrmGraphNode[]; edges: CrmGraphEdge[] }
  nodes: CrmGraphNode[]
  edges: CrmGraphEdge[]
  typeColor: Record<string, string>
  canWrite: boolean
}>()
const emit = defineEmits<{ select: [id: string, kind: string]; create: [] }>()
</script>

<template>
  <div v-if="nodes.length || (organizationGraph?.nodes.length || 0) > 1" class="relationship-center">
    <RelationGraph :organization-graph="organizationGraph" :nodes="nodes" :edges="edges" :type-color="typeColor" :highlight-path="[]" :hidden-types="[]" :only-gaps="false" holographic @select="(id, kind) => emit('select', id, kind)" />
  </div>
  <div v-else class="relationship-center__empty">
    <div class="orbit">五类协同</div><h4>建立第一条客户关系</h4><p>建档后，单位、联系人与关系网络将在这里呈现</p>
    <button v-if="canWrite" @click="emit('create')">＋ 信息收集</button><span v-else>当前为只读权限</span>
  </div>
</template>

<style scoped lang="scss">
.relationship-center{display:flex;min-height:0;flex:1}.relationship-center :deep(.rg-wrap){display:flex;flex:1;min-height:0;flex-direction:column}.relationship-center :deep(.rg-toolbar){flex-shrink:0}.relationship-center :deep(.rg-svg){min-height:290px;flex:1}.relationship-center__empty{display:flex;min-height:330px;flex:1;flex-direction:column;align-items:center;justify-content:center;gap:14px;text-align:center}.relationship-center__empty h4{margin:0;color:var(--text-primary,#edf7ff);font-size:16px}.relationship-center__empty p,.relationship-center__empty span{margin:0;color:var(--text-secondary,#89a9c4);font-size:12px}.relationship-center__empty button{padding:8px 13px;border:1px solid rgba(75,159,183,.75);border-radius:7px;background:#164873;color:#e4f7ff;cursor:pointer}.orbit{margin:10px;border:1px solid var(--cyan,#38e6e6);border-radius:50%;padding:28px 17px;color:#73e9ed;box-shadow:0 0 0 12px rgba(27,83,103,.18),0 0 28px rgba(23,141,179,.2)}
</style>
