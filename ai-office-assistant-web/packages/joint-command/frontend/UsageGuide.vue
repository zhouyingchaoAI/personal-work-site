<script setup lang="ts">
import { computed, ref } from "vue";
import { resourceUrl } from "../../../src/services/personalWorkApi";
const emit = defineEmits<{
  navigate: [
    tab:
      | "cockpit"
      | "organization"
      | "archive"
      | "relation"
      | "battle",
  ];
  create: [];
}>();
defineProps<{ canWrite: boolean }>();
const query = ref("");
const topic = ref<(typeof articles)[number] | null>(null);
const articles = [
  {
    title: "00 极简工作台：从今天要做的事开始",
    tags: "工作台 客户 商机 跟进 客户总览 停滞",
    lines: [
      "首页默认展示优先跟进，按到期日显示最多八项待办；地图在“工作台 → 经营总览”。批量收集、帮助和刷新归入顶部“更多”；我方组织、区域地图、评分规则及有权限的授权与留痕统一进入“设置”。",
      "管理者在工作台切换“管理视图”，集中处理当前授权范围内的逾期、久未跟进与待协调线索。待协调来自负责人缺失或单点关系风险，不等同于已经创建的协同任务。",
      "历史商机可勾选“仅看客户关联待核对”，编辑时查看名称候选；候选只作建议，选择并保存后才建立关联。取消不修改资料，没有可靠候选时手动选择客户；不会批量按名称覆盖正式数据。",
      "在“客户 → 客户总览”打开客户详情，按概况、联系人、动态查看已授权的下属组织、确认关联的商机、互动和计划。没有明确客户关联的商机不计入客户汇总，可在商机编辑中确认。",
      "在“商机”中新建或编辑商机，选择客户、负责人及销售阶段。销售阶段与项目实施阶段分别维护；赢单、输单、取消分别记录。保存失败时草稿保留，可直接重试。",
      "点击商机名称，或从客户、工作台点“查看商机”，直接打开对应商机详情，集中查看阶段、负责人、下一步及客户联系人。联系人仅来自明确关联客户及下级组织；已登记决策角色优先展示，不代表已确认项目关键人。跨账号同编号商机分别定位和汇总待办；推进建议仍依赖编号唯一，遇到重号会提示核对，不猜测目标。",
      "从商机进入“推进建议”，选好联系人和项目阶段后生成建议；“安排跟进”确认对接关系、负责人和日期后加入待办。计划不计真实互动评分，实际沟通后在“跟进”记录结果。",
      "久未跟进商机默认按14天提示，可切换30天或60天，仅影响当前查看。以该商机的已登记互动为准，无互动从建档日计算；未来计划和未来日期不算已发生互动，缺有效日期时不判断停滞。",
    ],
  },
  {
    title: "09 我方组织：部门、岗位与人员",
    tags: "我方 人员 公司 部门 工号 上级 对接人",
    lines: [
      "Excel和页面信息收集支持我方姓名、公司、部门、岗位；填写后与客户记录一起创建或补全我方人员。已有资料冲突会提示核实，旧版模板仍可使用。部门或人员筛选贯穿档案、关系、待办、图谱和驾驶舱；作战人选按筛选范围推荐，项目覆盖仍按项目全貌计算。",
      "进入“设置 → 我方组织”，先新增负责人，再登记其下属。按公司→部门→岗位→人员查看组织，填写姓名、公司、部门、岗位、负责区域；需要时补充直接上级。汇报架构可逐级展开，系统阻止循环汇报关系。",
      "对接标识留空时使用姓名，同名人员请使用不同工号。标识保存后保持固定；在信息收集和关系登记中选择我方人员，Excel的我方对接人填写同一标识。旧的自由填写内容保留，不根据同名自动合并。",
      "我方人员档案目前由当前账号维护，与平台登录账号和数据权限独立；登记上级不授予客户数据访问权限。",
    ],
  },
  {
    title: "01 首次使用：先建档，再记录，再行动",
    tags: "快速建档 入门",
    lines: [
      "少量联系人：点击顶部“信息收集”，填写公司全称、单位、部门与姓名。字段顺序与Excel一致，按组织人员、历史判断、本周计划、补充资料分组；单位类型默认业主单位，其余信息可后补。已有单位优先从列表选择，避免重复建档。",
      "批量联系人：下载客户经营收集表，一行一位联系人，填好后上传。系统自动关联单位、联系人和我方关系。",
      "建档后进入“关系维系”，记录实际拜访、有效沟通、情报和下一步；再用驾驶舱查看风险、用项目作战地图规划行动。",
    ],
  },
  {
    title: "02 Excel 上传：按公司经营表收集",
    tags: "模板 上传 xlsx 表格 资料",
    lines: [
      "新版直接入库关键项：公司全称、姓名*、单位类型。单位、部门、职务、重要程度、支持程度、跟进轨迹、上次互动时间、本周互动计划及日期可后补。缺少关键项的行会推送到“我方姓名”对应账号的资料补充待办。",
      "新版保留工作表名“经营收集表”和第一行表头，使用模板下拉选项。只支持未加密 .xlsx、文件不超过 5MB；不要填公式，空行会忽略。",
      "跟进轨迹原文存入联系人历史备注，不自动拆成有效动作。上次互动日期产生历史触达记录；本周互动计划产生独立待办，不改变上次触达时间或关系分数。支持程度选择反对、中立、支持、积极支持，不确定可留空。旧数字编码仍可导入，自动转换为对应中文，不换算为系统关系强度。",
      "点击“Excel 收集 → 上传 Excel 自动录入”后，有效行直接录入。结果中的“新增/补全行”是输入行数，不是创建对象总数；一行可能同时创建单位、联系人与关系。",
      "已有记录不覆盖；有错误时按结果中的工作表和行号修改，再次上传即可。重名导致无法唯一匹配时，先到客户档案核实。Word、PDF、照片不能通过此入口直接导入，请将业务信息整理到模板。",
    ],
  },
  {
    title: "03 数据如何组织：五种记录分清楚",
    tags: "数据 单位 联系人 关系 动作 项目",
    lines: [
      "经营区域：按公司口径选择东区、西区、中区或广东区，与城市分别填写。未填归入未分区；驾驶舱与客户档案可按区域筛选。新版以公司全称 → 单位 → 部门组织客户资料，旧版模板仍可使用。",
      "客户组织：公司全称是最高级组织；单位归属公司，部门归属单位。五类类型是业务协作分类，不代表固定上下级：主管单位、业主单位、总包单位、设计单位、厂商。",
      "联系人：记录单位中的具体人员及职务、部门、决策角色、职业轨迹。职务不等于实际决策权；不确定的信息先留空，后续核实。",
      "关系：记录“我方对接人—客户联系人”的连接，包括认识渠道与引荐路径。同一联系人可以对应多位我方人员。",
      "动作：记录发生了什么、何时发生、获得哪些业务信息，以及下一步、负责人和跟进日期。不要把未发生的计划填成已完成动作。",
      "项目关联：使用团队统一的项目编号，将客户联系人与实际决策节点关联。跨表名称和项目编号保持一致；项目阶段与权责以实际合同和授权为准。",
    ],
  },
  {
    title: "04 四级客户组织架构怎么填",
    tags: "组织 架构 部门 上级 汇报",
    lines: [
      "在“客户信息 → 客户组织架构”中维护公司全称和单位的上级关系，切换“联系人档案”维护联系人；只登记已确认的隶属关系，协作方不要误填为上级。系统不允许自己作为上级或形成循环。",
      "在联系人中补充所属部门、直接上级和岗位职责，形成三级组织视图与汇报关系。部门是单位内部机构，不需要重复创建客户单位。",
      "新版 Excel 可填写所属部门，但不包含上下级关联字段；导入后在页面补充即可。暂不清楚组织结构时，可以先建联系人再完善。",
    ],
  },
  {
    title: "05 关系强度、维系预警与待办",
    tags: "L0 L5 评分 预警 跟进 待办",
    lines: [
      "关系等级 L0–L5 由系统根据动作记录计算，不是人工自评。双向互动、动作深度、情报等因素共同影响评分，不能仅靠增加无效记录提高关系质量。",
      "收集表中重要客户默认14天、一般客户默认21天维系，可自定义1到365天；达到周期预警、两倍周期告警。未指定周期时按人员层级区分：高层 90 天、中层 45 天、基层 21天。驾驶舱显示待维系、单点风险与逾期跟进，具体记录在“关系维系”中查看。",
      "记录动作时补充“下一步事项、负责人、跟进日期”；待办会汇总到“关系维系 → 我的待办”和驾驶舱。完成后可直接在“我的待办”标记完成，实际沟通内容另记动作。",
    ],
  },
  {
    title: "06 驾驶舱与项目作战地图",
    tags: "看板 驾驶舱 大屏 图谱 作战地图",
    lines: [
      "驾驶舱展示本人客户布局、关系网络、L3+ 占比、风险和行动。点击指标进入对应页面；点击“大屏模式”放大，退出按钮返回。空数据不会生成虚构业绩。",
      "在“关系统筹”中可按公司层级展开客户单位，筛选待指派关系并批量明确负责人；人员变化时使用“转移关系”，系统会移交未完成计划并保留历史互动留痕。关系网络支持按单位类型筛选和查找引荐路径。",
      "进入项目作战地图，填写项目编号、选择阶段与目标联系人，补全决策链后生成建议，查看“打谁、谁去、走哪条路、第一步做什么”。关系覆盖不等于工程完成，建议需要结合现场实际判断。",
    ],
  },
  {
    title: "07 权限与保密：谁负责开通",
    tags: "权限 管理员 保密 只读 导入 到期",
    lines: [
      "超级管理员指定或撤销客户经营管理员；客户经营管理员管理普通用户的只读、编辑、编辑与导入权限及到期日，并查看审计。客户经营管理员不能任命其他管理员。",
      "只读用户可以查看；编辑用户可以维护档案与动作；批量上传还需要导入权限。上传按钮不可用时，联系客户经营管理员。",
      "安全权限名单默认只显示已开通用户；首次开通或恢复授权时，由管理人员打开“显示未开通 / 已到期用户”。",
      "客户数据以当前账号的授权范围为准，可能为本人、指定组织、区域或全部；功能权限与数据范围分别配置。页面筛选不会扩大授权。仅收集业务所需信息，不在备注或表格中填写账号密码等秘密。",
    ],
  },
  {
    title: "08 常见问题与修正方法",
    tags: "错误 失败 重复 表头 模板 空白",
    lines: [
      "提示表头不匹配：重新下载模板，把原数据按列复制过去，不改表头或工作表名称。提示值无效：使用单位类型和决策角色的下拉选项。",
      "部分行失败：成功行已保存，先看结果再修正错误行，不需要重复手工新建。已有档案需要修改时，到页面编辑；再次上传不会覆盖已有信息。",
      "图谱没有连线或驾驶舱为空：先核对当前登录账号、客户联系人及关系是否已保存，再点击刷新。点击“经营驾驶舱”页签返回看板。",
      "看不到新功能：刷新页面；页面长期打开时，可使用 Ctrl + Shift + R 强制刷新。出现权限拒绝时由客户经营管理员检查授权及到期日。",
    ],
  },
];
const results = computed(() =>
  articles
    .filter((a) =>
      `${a.title} ${a.tags} ${a.lines.join(" ")}`
        .toLowerCase()
        .includes(query.value.trim().toLowerCase()),
    )
    .sort((a, b) => a.title.localeCompare(b.title, "zh")),
);
</script>
<template>
  <section class="usage-guide">
    <header>
      <span>上手指南 · 操作手册</span>
      <h2>从一张客户表，开始经营关系资产</h2>
      <p>先录入已确认的信息，组织层级与业务细节可以逐步补全。</p>
      <div class="guide-actions">
        <el-button type="primary" :disabled="!canWrite" @click="emit('create')"
          >信息收集</el-button
        ><a
          class="el-button"
          :href="resourceUrl('/api/crm/excel/template?v=20260911-no-subsidiary')"
          download
          >下载客户经营收集表</a
        ><el-button @click="emit('navigate', 'archive')"
          >管理客户档案</el-button
        >
      </div>
    </header>
    <details class="guide-example">
      <summary>查看收集表填写示例</summary>
      <h3>公司经营收集表 · 一行一位联系人</h3>
      <p>
        蓝色组织人员 → 青色历史与判断 →
        金色未来计划。公司全称、姓名、单位类型齐全可直接入库；其他层级可逐步补齐。
      </p>
      <div class="guide-table">
        <table>
          <thead>
            <tr>
              <th>区域</th>
              <th>公司全称</th>
              <th>单位</th>
              <th>部门</th>
              <th>职务</th>
              <th>姓名*</th>
              <th>重要程度</th>
              <th>支持程度</th>
              <th>本周互动计划</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>东区</td>
              <td>示例轨道集团有限公司</td>
              <td>示例轨道集团</td>
              <td>设备部</td>
              <td>技术负责人</td>
              <td>张工</td>
              <td>重要</td>
              <td>支持</td>
              <td>确认接口资料</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        示例仅供说明。完整模板另含跟进轨迹、上次互动时间、计划日期、我方对接人、单位类型、城市及维系周期；下载文件自带填写说明和不参与导入的示例页。
      </p>
    </details>
    <nav aria-label="功能快捷入口">
      <el-button @click="emit('navigate', 'organization')">组织架构</el-button
      ><el-button @click="emit('navigate', 'relation')">关系维系</el-button
      ><el-button @click="emit('navigate', 'cockpit')">经营驾驶舱</el-button
      ><el-button @click="emit('navigate', 'battle')">项目作战地图</el-button>
    </nav>
    <el-input
      v-model="query"
      placeholder="搜索说明：上传、组织架构、权限、预警…"
      clearable
      aria-label="搜索使用说明"
    />
    <p class="guide-count">{{ results.length }} 个说明主题</p>
    <div class="guide-topics">
      <button v-for="a in results" :key="a.title" @click="topic = a">
        {{ a.title }} <span>查看 →</span>
      </button>
    </div>
    <el-drawer
      :model-value="!!topic"
      @close="topic = null"
      :title="topic?.title"
      size="min(640px,96vw)"
      append-to-body
      ><ol class="guide-topic-content">
        <li v-for="line in topic?.lines || []" :key="line">{{ line }}</li>
      </ol></el-drawer
    >
    <el-empty
      v-if="!results.length"
      description="没有匹配说明，试试“上传”“权限”或清空搜索"
    />
  </section>
</template>
<style scoped lang="scss">
.usage-guide {
  padding: 12px 4px;
  color: #334861;
  header {
    background: linear-gradient(120deg, #0e2442, #1b4971);
    padding: 26px;
    border-radius: 14px;
    color: #eaf3ff;
    span {
      color: #70e1df;
      font-size: 12px;
      letter-spacing: 2px;
    }
    h2 {
      font-size: 25px;
      margin: 12px 0;
    }
    p {
      color: #c4d7ea;
    }
  }
  p {
    font-size: 13px;
    line-height: 1.8;
  }
  h3 {
    font-size: 17px;
    margin: 0 0 12px;
  }
  .guide-actions,
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 20px;
    .el-button {
      margin-left: 0;
      text-decoration: none;
    }
  }
  nav {
    margin-bottom: 18px;
  }
  .guide-example {
    margin-top: 20px;
    border: 1px solid #dbe6f2;
    padding: 20px;
    border-radius: 12px;
    background: #f5f9fd;
  }
  .guide-table {
    overflow: auto;
  }
  table {
    width: 100%;
    min-width: 750px;
    border-collapse: collapse;
    font-size: 13px;
    background: white;
  }
  th,
  td {
    padding: 12px;
    border: 1px solid #dae4f0;
    text-align: left;
  }
  th {
    background: #e6eef8;
    color: #234f7c;
  }
  .guide-count {
    color: #6c819a;
  }
  .guide-topic {
    border: 1px solid #dde7f2;
    border-radius: 12px;
    padding: 22px;
    margin-top: 14px;
    h3 {
      color: #164f88;
    }
    ol {
      padding-left: 22px;
      margin-bottom: 0;
    }
    li {
      font-size: 14px;
      line-height: 1.9;
      margin: 10px 0;
      padding-left: 5px;
    }
  }
  @media (max-width: 600px) {
    header {
      padding: 18px;
      h2 {
        font-size: 21px;
      }
    }
    .guide-topic,
    .guide-example {
      padding: 15px;
    }
  }
}
.guide-topic summary,
.guide-example summary {
  cursor: pointer;
  font-weight: 600;
  color: #174b91;
  line-height: 1.8;
}
.guide-example summary {
  margin-bottom: 12px;
}
.guide-topics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  button {
    text-align: left;
    padding: 14px;
    border: 1px solid #dce6f2;
    border-radius: 8px;
    background: #f7faff;
    color: #174b91;
    cursor: pointer;
    font: inherit;
    span {
      float: right;
    }
  }
}
.guide-topic-content {
  padding-left: 22px;
  li {
    font-size: 15px;
    line-height: 1.9;
    margin-bottom: 18px;
  }
}
.usage-guide header {
  padding: 16px;
  h2 {
    font-size: 20px;
    margin: 6px 0;
  }
}
.usage-guide .guide-actions {
  margin-top: 10px;
}
.usage-guide .guide-example {
  padding: 10px 14px;
  margin-top: 10px;
}
.usage-guide nav {
  margin: 10px 0;
}
.guide-example summary {
  margin: 0;
}
@media (max-width: 650px) {
  .guide-topics {
    grid-template-columns: 1fr;
  }
}
</style>
