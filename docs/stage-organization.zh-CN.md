# v0.5.4：按父需求组织阶段成果

本功能显式采纳后启用。需求登记升级为 Schema 1.1 / 契约 0.5.4；核心状态仍为 2.0，启用模型的 Runtime 仍为 1.1。旧 0.5.3 登记保持原行为，不从文件名或目录猜测父关系，也不移动旧文件。

## 第一次从哪里开始

先运行 `ipdctl context . --json`，确认增量、Phase、Claim、Gate 和规范 Owner ID。新项目仍按原流程 init/tailor，显式 enable 需求模型，并完成模板包的草稿、独立人工评审、授权发布和锁定，详见[需求与模板](requirements-and-templates.zh-CN.md)。本版包 `ipd-starter@1.3.0` 有 23 类、46 份中英文模板；旧包 1.2.1 及更早版本仍可解析。

已有项目若本增量已有接受的工作或批准的 Gate，应先用原流程完成该增量，在基于最新交付基线的新一轮开始时采纳。新一轮没有旧活动实例时，可先明确发布/锁定当前内置包，再采纳组织方式。不强制把已接受的整合文档拆开，也不把旧身份或批准补成新事实。

以下均为需审查的请求文件；`--request` 零写入，应用需要真实、明确的人类授权，`--authorized` 仍只是本地授权声明。

```yaml
# organization.yaml
request_id: adopt-stage-organization
operation: adopt_organization
reason: 采用按父需求组织的本轮交付方式
required_stages: [TR1, TR2, TR3, TR4]
```

```console
ipdctl requirements . --request organization.yaml --json > organization-plan.json
ipdctl requirements . --apply organization-plan.json --actor actual-maintainer --authorized
```

采纳保留原登记、状态、证据及模板的带摘要快照。改变编号政策或组织方式不会产生 Claim、赋予路径权限或批准交付件。

## 先形成需求，再取得正式编号

新的 `numbered_requirement` 请求使用原需求字段，但新需求可以省略 `id`，由预览分配。完整例子：

```yaml
request_id: measurement-ir
operation: numbered_requirement
reason: 登记经澄清的本轮用户目标
requirement:
  version: 1
  kind: IR
  title: 及时得到有效测量
  statement: 用户发起测量后两秒内得到本次有效读数或明确失败信息。
  source: 项目访谈记录的精确版本
  rationale: 支撑现场判断，不能把旧读数当作本次结果。
  priority: high
  owner: systems-team
  module: measurement
  parent: null
  derived: false
  acceptance:
    - id: response
      criterion: 在约定工况下，响应时间不超过两秒。
      method: test
  maturity: defined
  decomposition: open
```

预览会返回编号映射；应用后才能将它当作已登记需求。SR 的 `kind` 为 SR、`parent` 为准确的 IR 引用，例如 `ir-001@1`；AR 的父引用指向准确 SR。仍需用原 `scope` 操作明确选中本增量承诺的需求版本和判据。候选、已登记、结构完整和已批准是不同状态。

默认编号为 `ir-001 → sr-001-001 → ar-001-001-001`。兄弟序号按历史最大值向后分配，空号不复用，超过三位可扩展。内容版本独立，例如 `sr-001-001@2`。修订已有需求必须提供原稳定 `id` 和下一个连续版本；不能通过省略 ID 把内容修订伪装成另一条新需求。

旧 ID 不变；`organization.codes` 给每个精确版本记录层级显示编号。主父调整时规范 ID 保留、显示编号可变化，旧版本映射保留。真实祖先由 `parent` 决定，不由编号前缀或路径决定。无主父的派生条目显式使用 `derived: true` 和派生编号空间，例如 `sr-d-001`，并给出设计依据。

## 按阶段规划，按父需求论证

TR1 保留整合的原始来源/可行性文档和 IR 表。TR2 每个本轮 IR 一份 `ir_decomposition`，配套一份多条 SR 表；TR3 每个本轮 SR 一份 `sr_decomposition`，配套多条 AR 表，同一 IR 的 SR 归入同一子目录。TR4 对相关 AR 的实现与真实验证形成 `delivery_conclusion` 和更新后的 AR 追踪表快照，不新增第四层需求。各阶段另有轻量 `stage_index`，记录范围、共享资料、跨分支一致性和所有成果入口。

```yaml
request_id: plan-tr2
operation: stage_plan
reason: 基于本轮 IR 规划逐父分解与共享材料
stage: TR2
owner: plan.integrated_plan
locale: zh-CN
```

`owner` 示例来自默认核心流程；实际应使用 `context` 给出的、该 TR 映射 Phase 内的规范 ID，不能照搬别的项目的 ID。预览的 `stage_plan.instances` 是建议实例清单，`binding_issues` 解释缺 Owner、路径冲突等问题。计划不创建文件、不自动添加 Owner 绑定、不改变执行依赖。

初次规划时只有上层输入也可以，子需求输出可以为空。新增父需求进入范围后，可用新请求 ID 再运行同一阶段计划，增补新的父分支；已有单元不被覆盖。已有单元的输出集合要通过明确的 `stage_unit` 请求更新。

拿到对应 Owner 的有效 Claim 后，把所选建议实例作为原 `instantiate` 操作的 `instance` 提交。TR2/TR3 结论草稿可以先只关联父需求；在其中实际逐条推导子需求，记录唯一论证锚点、假设、公式/图例、来源、取舍及验证判据，然后登记选定条目并整理需求表。

首次使用不要求事先知道全部下级需求。当前 Owner 唯一对应一个 TR1—TR3 阶段时，Claim 持有者可通过原有授权预览/应用入口：用 `numbered_requirement` 登记本阶段的新需求（版本 1）、用 `scope` 只增补这些需求的判据、用 `decomposition` 完成本单元父需求的分解。TR3 可将这些需求及其祖先的实现关系指向当前 Owner。每次应用的 actor 必须是 Claim 持有者；不得缩减或改写已承诺范围，不得在 Claim 内修订旧 ID、变更其他阶段、重新规划阶段或替换模板锁定。TR4 不借此新增 AR。已有需求修订和有歧义的阶段配置仍在安全边界处理。

结论文档的输入/输出覆盖清单扩大时，用 `revise_instance`：提供 `old` 实例 ID、保持 Owner/类型/键/语言的 `instance`，为新实例使用新 ID 和新路径。原文件与实例保留。不得覆盖原路径或直接编辑登记来凑元数据。需求表只关联输出子需求，不能把父输入也塞进子需求行集合。

## 把支撑材料和结论关联起来

读取 `ipdctl requirements . --json` 返回的 `organization.units`，选择对应单元；以完整单元作为 `stage_unit` 请求的 `unit`。保留身份字段，明确更新 `outputs`、`arguments`、`supports`、`conclusion`、`register`、`finalized` 和理由。每条输出的论证定位形如 `{"requirement":"sr-001-001@1","anchor":"derive-sr-001-001"}`，结论文档中须有唯一的 `<a id="derive-sr-001-001"></a>` 等明确锚点，避免一份空泛结论冒充全部子需求的逐条推导。

每项支撑记录包含：

```json
{
  "kind": "artifact",
  "target": "docs/shared/selection.md",
  "owner": "plan.integrated_plan",
  "required": true,
  "rationale": "本材料的接口和时延边界支撑这些 SR 的分解结论",
  "anchor": "timing-budget",
  "sha256": null
}
```

`kind: instance` 时 target 为已有受管文档实例 ID；artifact 时为项目相对路径。摘要由控制器读取实际字节生成，不信任请求者声明。允许先记录尚未产生的 Artifact，摘要为 null，但必需材料缺失或变化会阻止相应结论就绪。可选资料仍显示缺失/失效，不伪称通过。

每个实际路径保留唯一 Owner，共享材料用多个引用表达消费者。必需的跨 Owner 材料应有明确核心执行前置关系，或其 Owner 已完成验收；不会把支撑箭头自动转成 `depends_on`。同一 Owner 的材料与结论可以在一次工作/评审中形成，不制造对自身验收的循环。

所有子需求论证、表格、必需支撑和范围核对完成后，才提交 `finalized: true`。这表示单元已准备供原 Deliverable/Gate 流程检查，不是人类批准。阶段最终结论可以早起草、反复修订，最后收敛定稿。

系统架构、接口规范、测试计划、硬件选型等仍是正式专业成果，按项目需要规划与受管。共享材料存一份，跨分支引用。真实代码、硬件与测试程序留在项目正常位置，TR4 用版本/摘要引用；不能为了统一目录复制到 docs，或用总结文件替代实际实现和执行。

## Dashboard 和检查

`refresh` / `render-dashboard` 的区别沿用原流程。采纳组织方式后增加“需求与阶段成果”面板及 `data/requirement_flow.json`，原主图保持原执行语义。面板按真实 IR 祖先分组，可以按阶段、增量和需求/材料筛选，展开查看输入、支撑、结论与子需求。

需求链接定位精确引用，下阶段使用入口跳转到把它作为输入的单元；材料显示全部使用单元，流程交付件按钮转到原矩阵。历史单元链接不可变基线，不拿当前文件冒充旧内容。未关联的专业交付件仍明确显示。

结构就绪、Owner 验收、实现和各层验证分开表达。必需支撑缺失/过期、错父、漏输出、缺阶段索引、未定稿或未知影响不能被显示为通过。改变材料和关系会影响评审及验证上下文；旧结果不能靠重新贴一遍编号或声明完成继续使用。

## 资格与范围

公开合成项目的完整资格入口增加：

```console
python -B scripts/simulate_incremental_development.py --organized --locale zh-CN
python -B scripts/simulate_incremental_development.py --organized --locale en
```

两轮流程使用明确的合成人类决定及实际软件执行，不等于生产验收。DOCX/XLSX、历史批量路径迁移、多 Claim/并发治理及独立内容正确性评审仍在后续范围；本功能没有自动取得真实平台审批身份。
