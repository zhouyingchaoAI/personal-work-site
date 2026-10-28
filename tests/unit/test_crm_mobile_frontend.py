import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CRM_VIEW = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "index.vue"
CRM_STYLES = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "index.scss"
STAFF_PICKER = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "StaffPicker.vue"
IMPORT_COMPLETION = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "ImportCompletionTasks.vue"
SECURITY_PANEL = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "SecurityPanel.vue"
LIAISON_REGIONS = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "liaisonRegions.ts"
COCKPIT = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "Cockpit.vue"


class CrmMobileFrontendTests(unittest.TestCase):
    def test_liaison_region_uses_organization_first_and_disambiguates_guangdong(self):
        regions = LIAISON_REGIONS.read_text(encoding="utf-8")
        security = SECURITY_PANEL.read_text(encoding="utf-8")
        directory = (LIAISON_REGIONS.parent / "LiaisonDirectory.vue").read_text(encoding="utf-8")
        manager_review = (LIAISON_REGIONS.parent / "managerReview.ts").read_text(encoding="utf-8")
        markers = regions.split("const markers", 1)[1]
        self.assertLess(markers.index("['广东区'"), markers.index("['东区'"))
        self.assertIn("organizationLiaisonRegion(profile)", regions)
        self.assertIn("resolveLiaisonRegion(row.r.our_staff,staffRegion,row.regions[0])", directory)
        self.assertIn("organizationLiaisonRegion(m)", manager_review)
        self.assertIn("add(relationsByAccount, r.our_staff?.username, r)", manager_review)

    def test_security_panel_defaults_to_liaison_directory_and_preserves_manual_selection(self):
        source = SECURITY_PANEL.read_text(encoding="utf-8")
        self.assertIn("const defaultNode = flat.find(node => node.key === 'liaisons') || tree[0]", source)
        self.assertIn("selectedNode.value = keep || defaultNode", source)

    def test_security_panel_searches_people_and_auto_locates_a_unique_result(self):
        source = SECURITY_PANEL.read_text(encoding="utf-8")
        self.assertIn("搜索组织 / 姓名 / 账号 / 工号 / 岗位", source)
        self.assertIn("user.name,user.username,user.employee_id,user.company,user.department,user.position", source)
        self.assertIn("matches.length!==1", source)
        self.assertIn("visibleMembers", source)

    def test_security_panel_has_non_region_directory_and_manual_region_override(self):
        source = SECURITY_PANEL.read_text(encoding="utf-8")
        self.assertIn("'非区域人员'", source)
        self.assertIn("crmSaveLiaisonRegion", source)
        self.assertIn("自动：${automaticLiaisonRegion(row)}", source)
        self.assertNotIn("resolveLiaisonRegion(user,explicit,customerRegion)", source)

    def test_region_manager_role_and_batch_assignment_workbench_are_exposed(self):
        security = SECURITY_PANEL.read_text(encoding="utf-8")
        workbench = (CRM_VIEW.parent / "RelationshipWorkbench.vue").read_text(encoding="utf-8")
        api = (ROOT / "ai-office-assistant-web" / "src" / "services" / "personalWorkApi.ts").read_text(encoding="utf-8")
        self.assertIn("regional_manager", security)
        self.assertIn("区域管理员", security)
        self.assertIn("crmBatchAssignRelations", workbench)
        self.assertIn("维系动作监督", workbench)
        self.assertIn("/crm/relations/batch-assign", api)

    def test_mobile_has_a_full_module_switcher_and_compact_task_surfaces(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        styles = CRM_STYLES.read_text(encoding="utf-8")
        self.assertIn("crm-mobile-tab-switch", view)
        self.assertIn("mobileTabOptions", view)
        self.assertIn(".crm-mobile-tab-switch", styles)
        self.assertIn(".crm-tabs > .el-tabs__header", styles)
        self.assertIn(".crm-region-filter", styles)
        self.assertIn(".el-table__body-wrapper", styles)

    def test_usage_guide_uses_a_header_dialog_not_a_module_tab(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("const usageGuideOpen = ref(false)", view)
        self.assertIn('@click="usageGuideOpen = true"', view)
        self.assertIn("使用说明</button>", view)
        self.assertIn('<el-dialog v-model="usageGuideOpen"', view)
        self.assertNotIn('<el-tab-pane label="使用说明"', view)
        self.assertNotIn("{ value: 'help', label: '使用说明' }", view)

    def test_staff_picker_searches_account_and_keeps_assignment_optional(self):
        picker = STAFF_PICKER.read_text(encoding="utf-8")
        self.assertIn("p.username", picker)
        self.assertIn("搜索姓名、账号、工号、部门或岗位", picker)
        self.assertIn("clearable", picker)

    def test_relation_editor_can_explicitly_remove_an_assignee(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("clearRelationMember", view)
        self.assertIn("删除对接人", view)
        self.assertIn("暂不设置对接人", view)

    def test_relation_editor_explains_that_single_point_risk_is_automatic(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("单点风险由系统自动判断", view)
        self.assertNotIn('v-model="relForm.single_point_risk"', view)

    def test_relation_list_surfaces_single_point_risk_next_to_the_contact(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn('class="crm-single-point-tag"', view)
        self.assertIn('singlePoint: rels.filter(r => r.single_point_risk).length', view)
        self.assertIn('{{ relationSummary.singlePoint }}', view)

    def test_relationship_coordination_explains_assignment_transfer_and_unit_hierarchy(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        workbench = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "RelationshipWorkbench.vue").read_text(encoding="utf-8")
        self.assertIn('关系统筹', view)
        self.assertIn('日常维系 → 关系维系', view)
        self.assertIn('人员变化时转移关系，同步交接未完成计划', view)
        self.assertIn('客户单位层级', workbench)
        self.assertIn('toggleRoot', workbench)

    def test_cockpit_offers_three_authorized_command_forms(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("cockpitMode", view)
        self.assertIn("客户经理形态", view)
        self.assertIn("区域指挥形态", view)
        self.assertIn("联合指挥形态", view)
        # 形态随账号数据范围开放：区域/全量才出现区域指挥与联合指挥。
        self.assertIn("capabilities.value.data_scope === 'regions' || capabilities.value.data_scope === 'all'", view)
        self.assertIn("if (capabilities.value.data_scope === 'all') options.push({ value: 'joint'", view)

    def test_cockpit_defaults_to_the_highest_authorized_command_form(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("selectDefaultCockpitMode", view)
        self.assertIn("data_scope === 'all'", view)
        self.assertIn("data_scope === 'regions'", view)

    def test_personal_cockpit_keeps_backend_resolved_legacy_member_names(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("r.our_staff?.username === username", view)
        self.assertIn("map(r => r.our_member)", view)
        self.assertIn("账号 / 工号 / 唯一姓名", view)

    def test_cockpit_keeps_authorized_empty_regions_visible(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("capabilities.value.regions", view)
        self.assertIn("businessRegions", view)
        self.assertIn("cockpitRegionOptions.value.map(name", view)

    def test_cockpit_embeds_the_region_battle_map_inline(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("import RegionMap from './dashboard/RegionMap.vue'", cockpit)
        self.assertIn("<RegionMap", cockpit)
        # 区域筛选就地下发，不跳出驾驶舱。
        self.assertIn("emit('region'", cockpit)

    def test_region_map_covers_the_defined_province_layout(self):
        dashboard = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard"
        data = (dashboard / "chinaMapData.ts").read_text(encoding="utf-8")
        region_map = (dashboard / "RegionMap.vue").read_text(encoding="utf-8")
        self.assertIn("PROVINCES", data)
        self.assertIn("REGION_PROVINCES", data)
        self.assertIn("东区: ['浙江', '江苏', '上海']", data)
        self.assertIn("中区: ['北京', '天津', '河北', '湖北', '河南', '山东', '安徽']", data)
        self.assertIn("广东区: ['广东', '湖南']", data)
        self.assertIn("西区: ['湖南', '四川', '重庆', '陕西']", data)
        self.assertIn("provinceRegions", region_map)
        self.assertIn("REGION_COLORS", region_map)
        # 官方划分按省份边缘描边：区域内省份用区域色加粗描边。
        self.assertIn(":stroke=\"stroke(p.n)\"", region_map)
        self.assertIn("function strokeWidth", region_map)
        self.assertIn("官方指定按省份边缘描边", region_map)

    def test_region_map_can_filter_by_the_five_unit_types(self):
        dashboard = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard"
        region_map = (dashboard / "RegionMap.vue").read_text(encoding="utf-8")
        cockpit = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "Cockpit.vue").read_text(encoding="utf-8")
        self.assertIn("activeType", region_map)
        self.assertIn("['主管单位', '业主单位', '总包单位', '设计单位', '厂商']", region_map)
        self.assertIn("按单位类型查看", region_map)
        # 类型统计基于原始 units/people/relations 即时计算，而非写死数字。
        self.assertIn("function statFor", region_map)
        self.assertIn(":units=\"units\" :people=\"people\" :relations=\"relations\"", cockpit)

    def test_region_inspector_panel_reports_city_and_province_by_unit_type(self):
        dashboard = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard"
        inspector = (dashboard / "RegionInspector.vue").read_text(encoding="utf-8")
        city_map = (dashboard / "cityProvince.ts").read_text(encoding="utf-8")
        cockpit = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "Cockpit.vue").read_text(encoding="utf-8")
        self.assertIn("区域数据明细", inspector)
        self.assertIn("cityProvince", inspector)
        self.assertIn("覆盖省份", inspector)
        # 城市/省份计数来自导入单位的城市字段，非写死。
        self.assertIn("u.region", inspector)
        self.assertIn("CITY_PROVINCE", city_map)
        self.assertIn("import RegionInspector", cockpit)
        self.assertIn("<RegionInspector", cockpit)
        self.assertIn("inspectorOpen", cockpit)

    def test_cockpit_relationship_network_can_open_in_a_larger_view(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("networkExpanded", cockpit)
        self.assertIn("network-modal", cockpit)

    def test_contact_view_does_not_draw_a_connection_for_unassigned_members(self):
        graph = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "organizationGraph.ts").read_text(encoding="utf-8")
        relation_graph = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "RelationGraph.vue").read_text(encoding="utf-8")
        self.assertIn("!r.our_member", graph)
        self.assertIn("对接视图", relation_graph)

    def test_expanded_cockpit_uses_the_command_screen_navigation_and_status_bar(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("cockpit-expanded", cockpit)
        self.assertIn("全屏作战大屏", cockpit)
        self.assertIn("<CommandOverviewScreen", cockpit)

    def test_action_center_uses_existing_playbook_and_relation_data(self):
        action_center = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard" / "ActionCenter.vue").read_text(encoding="utf-8")
        self.assertIn("playbook: CrmPlaybook", action_center)
        self.assertIn("relations: CrmRelation[]", action_center)
        self.assertIn("最近动态", action_center)

    def test_kpi_overview_remains_data_driven_and_navigable(self):
        kpis = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard" / "KpiOverview.vue").read_text(encoding="utf-8")
        self.assertIn("items: Kpi[]", kpis)
        self.assertIn("emit('navigate'", kpis)

    def test_quality_and_network_are_separate_data_driven_dashboard_components(self):
        dashboard = ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "dashboard"
        quality = (dashboard / "RelationshipQuality.vue").read_text(encoding="utf-8")
        center = (dashboard / "RelationshipCenter.vue").read_text(encoding="utf-8")
        self.assertIn("levelColors", quality)
        self.assertIn("#ffc83d", quality)
        self.assertIn("RelationGraph", center)
        self.assertIn("organizationGraph", center)

    def test_cockpit_header_search_reuses_archive_filter_and_has_safe_export_feedback(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("searchCockpit", view)
        self.assertIn("archiveQuery.value = keyword", view)
        self.assertIn("projectId.value = keyword", view)
        self.assertIn("emit('search'", cockpit)
        self.assertIn("emit('export'", cockpit)
        self.assertIn("ElMessage.error(error instanceof Error ? error.message : '导出失败')", view)

    def test_relation_graph_maps_strength_to_visual_weight_and_exposes_focus_restore(self):
        graph = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "RelationGraph.vue").read_text(encoding="utf-8")
        self.assertIn("edgeWidth", graph)
        self.assertIn("edgeOpacity", graph)
        self.assertIn("hoverDetail", graph)
        self.assertIn("恢复全图", graph)

    def test_command_screen_has_a_compact_1366_header_layout_without_global_scale(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("@media(max-width:1500px)", cockpit)
        # 总体信息画布按设计稿等比缩放，其余页签保持流式布局、不整体缩放。
        self.assertIn("useCanvasScale(viewport, 1571, 792, canvasMode)", cockpit)
        self.assertIn("const canvasMode = computed(() => section.value === 'overview' && !narrow.value)", cockpit)

    def test_command_screen_uses_clamped_spacing_for_high_resolution_displays(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("@media(min-width:1300px)", cockpit)
        self.assertIn("clamp(", cockpit)

    def test_command_header_is_a_reusable_shell_component_with_existing_actions(self):
        cockpit = COCKPIT.read_text(encoding="utf-8")
        self.assertIn("import CommandOverviewScreen from './command/CommandOverviewScreen.vue'", cockpit)
        self.assertIn("<CommandOverviewScreen", cockpit)
        for action in ("emit('navigate'", "emit('refresh'", "emit('export'", "emit('search'"):
            self.assertIn(action, cockpit)

    def test_customer_archive_and_organization_tree_use_business_facing_organization_language(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        tree = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "OrganizationTree.vue").read_text(encoding="utf-8")
        self.assertIn("company_full_name", view)
        self.assertIn("organization_unit_name", view)
        self.assertIn("客户组织架构", tree)
        self.assertIn("组织关系", tree)
        self.assertNotIn("公司全称 ·", tree)
        self.assertNotIn("三级组织", tree)
        self.assertIn("parent_unit_id", tree)

    def test_customer_organization_tree_filters_by_unit_type_and_starts_collapsed(self):
        tree = (ROOT / "ai-office-assistant-web" / "packages" / "joint-command" / "frontend" / "OrganizationTree.vue").read_text(encoding="utf-8")
        self.assertIn("typeFilter", tree)
        self.assertIn("全部单位类型", tree)
        self.assertIn("filterOrganization", tree)
        self.assertIn(':default-expand-all="false"', tree)

    def test_customer_archive_reuses_a_compact_organization_tree_and_keeps_people_rows_focused(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        self.assertIn("<OrganizationTree :read-only=\"!capabilities.write\"", view)
        self.assertIn("crm-person-archive", view)
        self.assertIn("联系人档案", view)
        self.assertIn("客户组织架构", view)
        # 联系人表只保留对接人姓名与组织路径，不再逐行扫描全部关系。
        self.assertIn("contactMembers.get(row.id)", view)
        self.assertIn("contactSubPath(row)", view)

    def test_incomplete_excel_rows_have_a_completion_queue_for_assignees_and_managers(self):
        view = CRM_VIEW.read_text(encoding="utf-8")
        tasks = IMPORT_COMPLETION.read_text(encoding="utf-8")
        self.assertIn("ImportCompletionTasks", view)
        self.assertIn("资料补充", view)
        self.assertIn("crmImportCompletionTasks", tasks)
        self.assertIn("crmCompleteImportCompletionTask", tasks)
        self.assertIn("公司全称", tasks)
        self.assertIn("姓名", tasks)
        self.assertIn("单位类型", tasks)
        self.assertIn("接收人", tasks)

    def test_completion_queue_exposes_existing_row_data_before_a_user_fills_missing_fields(self):
        tasks = IMPORT_COMPLETION.read_text(encoding="utf-8")
        self.assertIn("已填资料", tasks)
        self.assertIn("taskSourceEntries", tasks)
        self.assertIn("原始上传资料", tasks)
        self.assertIn("公司全称", tasks)
        self.assertIn("微信 / 其他联系", tasks)


if __name__ == "__main__":
    unittest.main()
