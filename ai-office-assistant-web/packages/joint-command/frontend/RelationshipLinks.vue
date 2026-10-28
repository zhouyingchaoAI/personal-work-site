<script setup lang="ts">
import {computed} from 'vue'
import type {CrmRelation, CrmPerson} from '../../../src/services/personalWorkApi'
import PersonFlags from './PersonFlags.vue'
const props=defineProps<{relations:CrmRelation[];people?:CrmPerson[]}>()
const personById=computed(()=>new Map((props.people||[]).map(p=>[p.id,p])))
const identity=(r:CrmRelation)=>r.our_staff?.username||r.our_member
const groups=computed(()=>{
 const map=new Map<string,CrmRelation[]>()
 for(const r of props.relations){const list=map.get(r.person_id)||[];list.push(r);map.set(r.person_id,list)}
 return [...map].map(([id,rows])=>({id,rows,person:personById.value.get(id),people:new Set(rows.map(identity).filter(Boolean)).size}))
})
const staffCount=computed(()=>new Set(props.relations.map(identity).filter(Boolean)).size)
const departmentCount=computed(()=>new Set(props.relations.filter(r=>r.our_staff?.department).map(r=>`${r.our_staff!.company} / ${r.our_staff!.department}`)).size)
const jobCount=computed(()=>new Set(props.relations.map(r=>r.our_staff?.title).filter(Boolean)).size)
const multi=computed(()=>groups.value.filter(g=>g.people>1))
</script>
<template>
<details class="relationship-links">
 <summary>关系链路统计：{{relations.length}} 条记录 · {{staffCount}} 位我方对接人 · {{departmentCount}} 个部门 · {{jobCount}} 种岗位 · {{multi.length}} 位客户联系人由多人对接 <span>展开链路</span></summary>
 <p>按当前可见关系统计；同一账号的工号与用户名合并计人数，关系记录分别保留。未识别账号按原对接标识计数，缺失部门及岗位不计入覆盖数。</p>
 <div class="rl-groups"><article v-for="g in groups" :key="g.id"><strong>{{g.rows[0]?.person_name||'客户联系人'}} · {{g.people}} 位对接人 / {{g.rows.length}} 条关系</strong><PersonFlags v-if="g.person" compact :importance="g.person.importance" :support="g.person.support_level"/><div v-for="r in g.rows" :key="r.id" class="rl-path"><b>{{r.our_staff?.name||r.our_member_label||r.our_member||'未指派'}}</b><span>{{r.our_staff?.company||'公司待补充'}} / {{r.our_staff?.department||'部门待补充'}} / {{r.our_staff?.title||'岗位待补充'}}</span><small>→ {{r.person_name||'客户联系人'}} · L{{r.strength}} · {{r.last_touch||'暂无互动日期'}}</small></div></article><p v-if="!groups.length">当前范围暂无关系链路</p></div>
</details>
</template>
<style scoped>
.relationship-links{margin:12px 0;padding:12px;border:1px solid #cbddeb;border-radius:8px;background:#f3f8ff;color:#315877;font-size:13px}.relationship-links summary{cursor:pointer;line-height:1.8}.relationship-links summary span{color:#2466b7;margin-left:12px}.relationship-links p{font-size:12px;color:#70849a}.rl-groups{max-height:320px;overflow:auto}.rl-groups article{padding:10px;background:white;border-bottom:1px solid #dce7f2}.rl-path{display:flex;gap:12px;flex-wrap:wrap;margin-top:9px}.rl-path b{min-width:80px}.rl-path small{color:#72859a}
</style>
