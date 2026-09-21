import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEEKLY_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "WeeklyReportView" / "index.vue"
TRIP_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "TripReportView" / "index.vue"
DIARY_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "DiaryView" / "index.vue"
CONTENT_ASSIST_DIALOG = ROOT / "ai-office-assistant-web" / "src" / "components" / "ContentAssistDialog" / "index.vue"
WRITING_STYLE = ROOT / "ai-office-assistant-web" / "src" / "utils" / "aiWritingStyle.ts"
WRITING_STYLE_SELECT = ROOT / "ai-office-assistant-web" / "src" / "components" / "AiWritingStyleSelect" / "index.vue"
AI_POLISH_BUTTON = ROOT / "ai-office-assistant-web" / "src" / "components" / "AiPolishButton" / "index.vue"
DIGITAL_HUMAN = ROOT / "数字人" / "index.html"
DIGITAL_HUMAN_BACKEND = ROOT / "backend" / "digital_human.py"


class WeeklyReportFrontendTests(unittest.TestCase):
    def test_weekly_entries_support_drag_sorting_and_persist_the_new_order(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn('draggable="true"', source)
        self.assertIn('handleRowDragStart', source)
        self.assertIn('handleRowDragOver', source)
        self.assertIn('handleRowDrop', source)
        self.assertIn("'drop-before'", source)
        self.assertIn("'drop-after'", source)
        self.assertIn('section.rows.splice', source)
        self.assertIn('saveWeeklyDraft()', source)

    def test_report_mail_bodies_are_editable_while_preserving_template_html(self):
        for view in (WEEKLY_VIEW, TRIP_VIEW):
            source = view.read_text(encoding="utf-8")
            self.assertIn('handleMailBodyInput', source)
            self.assertIn('contenteditable="true"', source)
            self.assertIn('v-html="mailBodyPreviewHtml"', source)
            self.assertIn('@blur="commitMailBodyEdits"', source)
            self.assertIn('function commitMailBodyEdits()', source)
            self.assertIn('if (mailDraft.body_html !== html) mailDraft.body_html = html', source)

    def test_first_monday_default_period_uses_the_previous_completed_workweek(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn('function weeklyReportingRange(reference = new Date())', source)
        self.assertIn('weekday === 1 ? 7 : 0', source)
        self.assertIn('return weeklyReportingRange(reference)', source)

    def test_member_projects_are_seeded_into_all_three_weekly_sections(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn('function syncMemberProjectsToWeeklyRows', source)
        self.assertIn("for (const sectionId of ['summary', 'follow', 'next'] as SectionId[])", source)
        self.assertIn('category: project.name', source)
        self.assertIn('projectRows.find((row) => row.category === project.name)', source)
        self.assertIn('syncMemberProjectsToWeeklyRows(projectOptions.value)', source)

    def test_removed_project_tasks_stay_removed_from_generated_mail(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn('excludedProjectIdsBySection', source)
        self.assertIn('rememberRemovedProjectTask(section.id, row)', source)
        self.assertIn('excludedProjectIdsBySection[sectionId].has(project.id)', source)
        self.assertIn('excludedProjectIds: serializeExcludedProjectIds()', source)
        self.assertIn('excludedProjectTaskStorageKey', source)
        self.assertIn('persistExcludedProjectIds()', source)
        self.assertIn('restoreExcludedProjectIds(draft.weekly.excludedProjectIds)', source)
        self.assertIn("const content = currentWeeklyContent()", source)
        self.assertIn('weekly_summary: content.summary', source)
        self.assertIn('weekly_follow: content.follow', source)
        self.assertIn('weekly_next: content.next', source)
        self.assertIn('后续生成的邮件正文和附件将同步移除', source)

    def test_ai_polish_result_uses_large_dialog_and_actions_close_it(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn('const optimizeDialogVisible = computed({', source)
        self.assertIn('class="weekly-optimize-dialog"', source)
        self.assertIn('width="min(1080px, 94vw)"', source)
        self.assertIn('class="ai-compare-card ai-compare-card--dialog"', source)
        self.assertIn('activeOptimizeField.value = null', source)

    def test_ai_field_actions_include_summary_formatting_and_confirmed_writeback(self):
        for view in (WEEKLY_VIEW, TRIP_VIEW):
            source = view.read_text(encoding="utf-8")
            self.assertIn('ContentAssistDialog', source)
            self.assertIn('AI 总结', source)
            self.assertIn('openSummaryDialog', source)
            self.assertNotIn('class="ai-format-button"', source)

        dialog = CONTENT_ASSIST_DIALOG.read_text(encoding="utf-8")
        self.assertIn('uploadWritingFile', dialog)
        self.assertIn('rewriteWritingDraft', dialog)
        self.assertIn('generateWritingDraft', dialog)
        self.assertIn('summarizeUploadedMaterials', dialog)
        self.assertIn('>总结</button>', dialog)
        self.assertNotIn('通用总结', dialog)
        self.assertIn('已解析', dialog)
        self.assertIn('AI 处理进度', dialog)
        self.assertIn('processingSteps', dialog)
        self.assertIn('hasGeneratedContent', dialog)
        self.assertIn('确认内容并写入当前字段', dialog)
        self.assertIn('多轮对话', dialog)
        self.assertIn('normalizeWeeklySummary', dialog)
        self.assertIn("summaryMode.value === 'weekly'", dialog)
        self.assertIn('上传文件', dialog)
        self.assertIn('写入当前字段', dialog)
        self.assertIn("emit('apply'", dialog)
        self.assertIn('taskTitle', dialog)
        self.assertIn('整理格式', dialog)
        self.assertIn('formatCandidate', dialog)

    def test_ai_polish_uses_shared_style_preferences_without_changing_structure(self):
        self.assertTrue(WRITING_STYLE.exists())
        style_source = WRITING_STYLE.read_text(encoding="utf-8")
        for label in ["口语清晰", "精炼专业", "正式官方", "详述完整"]:
            self.assertIn(label, style_source)
        self.assertIn("严格保留原文的段落、编号、列表、表格、字段顺序", style_source)
        self.assertIn("localStorage", style_source)
        self.assertIn("getSavedStylePrompt", style_source)
        self.assertIn("saveStylePrompt", style_source)
        self.assertIn("writingStyleInstruction", style_source)
        for view in (WEEKLY_VIEW, TRIP_VIEW, DIARY_VIEW):
            source = view.read_text(encoding="utf-8")
            self.assertIn("AiWritingStyleSelect", source)
            self.assertIn("buildOptimizePrompt", source)
            self.assertIn("writingStyleInstruction", source)
            self.assertIn("stylePromptPreview", source)
            self.assertIn("AI 润色提示词（随行文风格自动变化）", source)
            self.assertIn("syncPromptDraftForStyle", source)

    def test_ai_polish_button_switches_style_by_wheel_then_polishes_by_click(self):
        button = AI_POLISH_BUTTON.read_text(encoding="utf-8")
        self.assertIn("@wheel.prevent", button)
        self.assertIn("setWritingStyle", button)
        self.assertIn("emit('polish')", button)
        self.assertIn("AI 润色·", button)
        self.assertIn("CaretTop", button)
        self.assertIn("CaretBottom", button)
        self.assertIn("switchStyle(-1)", button)
        self.assertIn("switchStyle(1)", button)
        self.assertIn("ai-polish-wheel--", button)
        for style in ["clear", "concise", "formal", "detailed"]:
            self.assertIn(f"&--{style}", button)
        for view in (WEEKLY_VIEW, TRIP_VIEW, DIARY_VIEW):
            source = view.read_text(encoding="utf-8")
            self.assertIn("AiPolishButton", source)

    def test_ai_compare_dialog_supports_iterative_prompted_polishing(self):
        source = WEEKLY_VIEW.read_text(encoding="utf-8")
        self.assertIn("compareRefinePrompt", source)
        self.assertIn("refineOptimizePreview", source)
        self.assertIn("再次润色", source)
        self.assertIn("基于右侧当前内容", source)

    def test_digital_human_weekly_wizard_is_a_multiturn_stage_conversation(self):
        source = DIGITAL_HUMAN.read_text(encoding="utf-8")
        self.assertIn('fetch(API_BASE + "/api/weekly-prefill")', source)
        self.assertIn('weeklyWizard.turns', source)
        self.assertIn('requestWeeklyStageReply', source)
        self.assertIn('确认本阶段，下一步', source)
        self.assertIn('上周重点工作', source)
        self.assertIn('保持上周重点工作，下一步', source)
        self.assertIn('file_ids: attachedFiles.map(file => file.id)', source)

    def test_ai_summary_dialog_uses_a_large_centered_conversation_canvas(self):
        source = CONTENT_ASSIST_DIALOG.read_text(encoding="utf-8")
        self.assertIn('width="min(1320px, 96vw)"', source)
        self.assertIn('top="4vh"', source)
        self.assertIn("'is-initial': messages.length === 1", source)

    def test_weekly_stage_chat_bypasses_one_shot_weekly_agent(self):
        source = DIGITAL_HUMAN_BACKEND.read_text(encoding="utf-8")
        self.assertIn('weekly_stage = str(payload.get("weekly_stage", "")', source)
        self.assertIn('WEEKLY_STAGE_CONVERSATION_PROMPT', source)
        self.assertIn('and not weekly_stage', source)


if __name__ == "__main__":
    unittest.main()
