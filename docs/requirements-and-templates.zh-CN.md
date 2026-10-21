# 渐进需求、增量交付与 Markdown 模板

v0.5.3-beta 开发版增加显式启用的 IR/SR/AR 模型。已有项目默认继续原流程；不会从文件名推断需求，也不会补造历史批准。发布资格记录见 RELEASE_CHECKLIST.md。

## 先看模板

```console
ipdctl templates --type interface_spec --locale zh-CN
ipdctl templates --type interface_spec --locale en
ipdctl templates --json
```

公共资源位于 `ipdctl/document_templates/zh-CN/` 和 `en/`。两种语言具有相同的模板 ID、版本、章节 ID、字段及表格含义；正文和表头本地化，内容摘要各自锁定。

IR/SR/AR 模板现为多条需求管理表，支持 HTML `rowspan` 共享单元格；每条需求保留独立 ID / 版本。四份新增总体文档草稿及阶段组合见 [TR1—TR4 草稿索引](stage-deliverable-drafts.zh-CN.md)。总体文档解释分析与设计，需求表管理逐条规格。

| 类型 | 主要填写内容 |
| --- | --- |
| [`ir_spec` 中文](../ipdctl/document_templates/zh-CN/ir_spec.md) / [EN](../ipdctl/document_templates/en/ir_spec.md) | 背景与价值、用户场景、验收意图、分批交付、待决事项 |
| [`sr_spec` 中文](../ipdctl/document_templates/zh-CN/sr_spec.md) / [EN](../ipdctl/document_templates/en/sr_spec.md) | 系统边界、行为接口、量化指标与单位、AR 分配、系统验证 |
| [`ar_spec` 中文](../ipdctl/document_templates/zh-CN/ar_spec.md) / [EN](../ipdctl/document_templates/en/ar_spec.md) | 分配责任、模块要求与预算、接口、实现追踪、模块验证与回归 |
| [`architecture_design` 中文](../ipdctl/document_templates/zh-CN/architecture_design.md) / [EN](../ipdctl/document_templates/en/architecture_design.md) | 架构视图、组件职责、接口预算、方案比较、验证策略 |
| [`detailed_design` 中文](../ipdctl/document_templates/zh-CN/detailed_design.md) / [EN](../ipdctl/document_templates/en/detailed_design.md) | 数据结构、状态与算法、错误恢复、实现决策、测试关联 |
| [`interface_spec` 中文](../ipdctl/document_templates/zh-CN/interface_spec.md) / [EN](../ipdctl/document_templates/en/interface_spec.md) | 接口实例、双方角色、数据契约、时序、错误、安全与兼容性 |
| [`implementation_record` 中文](../ipdctl/document_templates/zh-CN/implementation_record.md) / [EN](../ipdctl/document_templates/en/implementation_record.md) | 输入版本、变更与仓库引用、实际自检、偏差及追踪 |
| [`test_plan` 中文](../ipdctl/document_templates/zh-CN/test_plan.md) / [EN](../ipdctl/document_templates/en/test_plan.md) | 范围、分层验证、环境、覆盖、准入退出及风险 |
| [`test_procedure` 中文](../ipdctl/document_templates/zh-CN/test_procedure.md) / [EN](../ipdctl/document_templates/en/test_procedure.md) | 用例版本、前置条件、输入步骤、预期结果、判据与证据采集 |
| [`test_report` 中文](../ipdctl/document_templates/zh-CN/test_report.md) / [EN](../ipdctl/document_templates/en/test_report.md) | 被测版本、逐用例实际结果、缺陷复测、覆盖和限制 |
| [`system_verification_report` 中文](../ipdctl/document_templates/zh-CN/system_verification_report.md) / [EN](../ipdctl/document_templates/en/system_verification_report.md) | SR 指标实测、系统配置、集成回归、偏差及证据 |
| [`acceptance_report` 中文](../ipdctl/document_templates/zh-CN/acceptance_report.md) / [EN](../ipdctl/document_templates/en/acceptance_report.md) | IR 使用场景、交付版本、实际体验、未满足目标和决定引用 |
| [`change_impact` 中文](../ipdctl/document_templates/zh-CN/change_impact.md) / [EN](../ipdctl/document_templates/en/change_impact.md) | 基础基线、前后版本、上下游影响、处置与正式决定引用 |
| [`trace_review` 中文](../ipdctl/document_templates/zh-CN/trace_review.md) / [EN](../ipdctl/document_templates/en/trace_review.md) | 精确版本清单、双向追踪、检查发现、覆盖及评审决定引用 |

每份模板包含版本化元数据、专用章节和适合该类型的表格；逐条需求规格在管理表中填写，阶段分析在总体文档中填写。`[[TODO: ...]]` 表示必须填写的内容。模板不会预填通过、签名或批准；删除占位符而不填事实不能通过检查。表格单元格不得留空；不适用项须写明理由，并引用适用的人类决定。结构检查不评判论证质量，独立内容就绪评审仍属于后续版本。

## 事实与阶段

`.ipd/requirements.yaml` 是规范登记；Dashboard 与 `requirements --json` 为派生视图。IR、SR、AR 的内容以 `id@version` 引用，版本只能追加。需求父子关系必须为 IR→SR→AR；派生 SR/AR 可无父节点，但必须显式标记并说明理由，由相应 Deliverable/Gate 评审其版本清单。执行依赖仍使用已有 `depends_on`；同阶段交付件细化仍使用 `refines`。

定义成熟度、分解状态、交付件状态和验证结果分开记录。`defined` 与 `complete` 是待治理检查的声明，不表示人类批准。`decomposition` 操作用于在需求内容不变时，显式更新分解成熟度；它不修改内容版本。声明仍会进入对应 Gate 的输入清单。

默认参考映射为 concept→TR1、plan→TR2、develop→TR3、qualify/launch/lifecycle→TR4；每个现有 TR/DCP Gate 都保留。可在任何 Gate 获批前通过 `stage_map` 显式配置全部规范 Gate ID。这是本项目的参考映射，不宣称是所有华为项目的通用阶段编号。

- TR1：本轮 IR 已定义；不要求未来 AR 全部已知。
- TR2：IR 分解声明完成，并存在本轮 SR；SR 有独立判据与方法。
- TR3：SR 分解声明完成，并存在本轮 AR；需求有显式实现分配关联。
- TR4：本轮 IR、SR、AR 的承诺判据分别具有最新的通过结果及匹配证据。模块通过不会推导出系统验证或用户验收通过。

`context --json` 包含需求投影。结构性 `verify` 通过不代表所有需求通过：报告中的
`requirements.acceptance`、诊断和独立覆盖字段另行说明增量就绪程度，Gate 及人类决定仍为必需。

## 请求、预览与应用

所有新增事实写入都先生成计划，再使用该计划应用。保存计划文件时，将 CLI 标准输出原样保存为 UTF-8 JSON；不要编辑计划中的哈希。请求和计划应放在项目外或项目指定的私有请求目录。

启用请求：

```yaml
request_id: enable-mvp
operation: enable
reason: 明确启用渐进需求模型
increment: mvp
product_version: '0.1'
```

```console
ipdctl requirements PROJECT --request enable.yaml --json
ipdctl requirements PROJECT --apply enable.plan.json --actor project-maintainer --authorized
```

预览不会写项目文件。计划绑定状态 revision、控制文件、需求登记、模板与当前证据指纹；过期输入会被拒绝。`--authorized` 沿用已有显式授权声明的信任边界，不是经过平台认证的身份。实际应用记录请求 ID、操作者、原因及版本；同一计划精确重试不重复创建文件或事件，变更输入需新请求 ID。

启用会保存原状态、Runtime、过程配置与已有证据的冻结迁移快照，列出未关联的原交付件。已有 Claim/Review 必须先完成，ID、Owner 和历史不会被猜测映射。`link` 操作可逐项显式关联。

需求请求示例：

```yaml
request_id: add-ir-1
operation: requirement
reason: 记录首个用户需求
requirement:
  id: ir-1
  version: 1
  kind: IR
  title: 现场快速测量
  statement: 产品应在指定环境下于两秒内给出测量结果。
  source: customer-interview-1
  rationale: 支持现场决策
  priority: high
  owner: systems-team
  module: sensor
  parent: null
  derived: false
  acceptance:
    - id: response
      criterion: 在 20 摄氏度条件下，响应时间不超过 2 秒。
      method: test
  maturity: defined
  decomposition: open
```

SR 使用 `kind: SR`、`parent: ir-1@1`；AR 引用 SR 的精确版本。每条需求至少有一个独立判据，方法为 `test/analysis/inspection/demonstration`。

所有请求共同包含 `request_id/operation/reason`，其余字段如下；未知字段被拒绝。查看 JSON Schema 可获得完整字段和枚举。

| operation | 附加字段及用途 |
| --- | --- |
| `enable` | `increment`, `product_version`：显式迁移并开始首轮 |
| `requirement` | `requirement`：追加需求内容版本 |
| `scope` | `scope: [{requirement: ir-1@1, criteria: [response]}]`：本轮精确判据；不包含未来范围 |
| `decomposition` | `requirement`, `status: open/complete`：更新分解成熟度 |
| `stage_map` | `stage_map: {规范 Gate ID: TR1/TR2/TR3/TR4}` |
| `link` | `link: {requirement, relation, target, rationale}`；`allocated_to/satisfied_by` 指向核心 Deliverable，`shared_constraint` 指向需求版本 |
| `obligation` | `obligation: {id, requirement, owner, document_type, keys}`：冻结实例键及数量 |
| `instantiate` | `instance`：创建一个交付件实例，字段见下文 |
| `verification` | `verification: {id, requirement, criterion, method, case, environment, result, evidence}` |
| `assess` | `change` 请求 ID、`assessments: [{target, action, rationale}]`；逐项选择 `reverify/unaffected/defer` |
| `pin_templates` | `path`：本地模板包目录，空字符串恢复公共包；不会联网下载 |
| `baseline` | `id`, `source: {backend, repository, revision, path}`：冻结完整交付快照 |
| `begin` | `increment`, `product_version`, `base_baseline`, `scope`：从最新交付基线开始下一轮 |
| `reuse_verification` | `baseline`, `result`, `id`：显式复用同一需求版本的冻结通过证据 |
| `retire` | 无附加字段；结束产品运行跟踪，须无活动增量 |

需求修改产生上下游影响集合，包括设计/实现关联、实例与 Gate；不会自动改写后代或抹除旧批准。未知影响、延期评估、未通过或过期证据阻止相关受理。已经获批的范围不能静默减少；改变已治理输入会被 Verify 发现，应按新的增量和明确变更边界处理。

`reverify` 是待完成的重新验证义务。Skill 为接受的影响评估保存 `assessment_revision`，并为新验证结果生成 `context_sha256`，绑定需求定义、本轮判据、模板锁定、直接追踪/文档输入及适用的重新验证轮次。需求、交付件实例、Owner 成果或 Gate 的重新验证要求映射到相关需求；再次接受 `reverify` 评估会开始新轮次。评估之前登记的结果、失败结果或旧基线证据不能解除本轮义务。完成实际验证后，再用 `verification` 登记当前输入下的新结果；登记命令本身不会执行测试或证明所填事实。

明确评估为 `unaffected` 的对象不会仅因别的需求变化而自动失效，但自身输入变化仍使旧结果失效。历史复用须通过 `reuse_verification`，且历史输入与当前验证上下文一致；不以复制证据文件作为重新执行。未纳入本轮的未来候选版本不影响当前范围；本轮采用更后版本也不能绕过此前尚需履行的重新验证轮次。

需求登记 Schema 1.0 增加两个可选读取字段以保留旧记录兼容性；新写入的摘要/轮次由 Skill 生成，请求不能指定摘要。旧结果缺少上下文时仍可读取，当前就绪检查报告 `VERIFICATION_CONTEXT_UNKNOWN`，不能自动补签；重新验证后登记新记录。冻结基线和旧文件不改写。

SR/AR 管理表的 `parent` 列须只填写规范登记中的精确父版本（可以使用 HTML 链接包裹该版本）。检查按共享单元格展开后逐行进行：悬空版本、错误层级、父关系不一致和缺少规范登记上下文均不能通过。已锁定的合法旧版本不会因存在新版本而被拒绝。显式派生需求须在登记中声明 `derived: true` 且 `parent: null`，表格相应单元格写 `derived: 原因`；一般需求不能靠填写“不适用”绕过父关系。直接调用 Python `lint(..., canonical={精确版本: 规范需求记录})` 时也须提供该上下文；项目门禁会自动传入登记。

若私有或早期 SR/AR 模板根本没有可核对的受控需求/父版本列，报告 `DOCUMENT_PARENT_COLUMN`，不能把普通段落检查当引用完整性通过。旧包仍按原字节解析，冻结历史不改写；活动项目使用此类旧格式时，单 Owner 使用下文的 `replace_templates` 显式转换，多 Owner 使用下一增量；不能静默换包、覆盖已审文件或关闭检查。

## 同一 AR 的两份接口设计

先登记义务：`requirement: ar-1@1`, `document_type: interface_spec`, `keys: [northbound, southbound]`，并指定一个已有核心 Deliverable 为 Owner。

实例请求中的 `instance`：

```yaml
id: interface-northbound
key: northbound
requirements: [ar-1@1]
owner: develop.solution_baseline
document_type: interface_spec
path: docs/mvp/interface-northbound.md
title: 北向测量接口
scope: MVP 测量数据服务
locale: zh-CN
```

第二份使用独立 ID、`key: southbound` 和另一个路径。两份文件锁定同一模板版本；也可将 `locale` 改为 `en` 使用等价英文模板。一个文件可以显式关联多个需求，但路径只有一个 Owner。

实际创建要求 Owner 的有效 Claim、操作者与 Claim 一致、路径受现有绑定授权，且位于 `docs/` 下。禁止覆盖已有文件、路径逃逸、链接、Windows junction 和实例键/路径冲突。事务恢复覆盖新文件、登记、状态与 Runtime。模板不执行 Python、宏、命令或网络访问。完成内容后按原 Close→Review→人类批准流程提交；必填项、章节顺序、表头、元数据及占位符均会检查。

## 模板包、QA 与历史

公共包 `ipd-starter@1.2.1` 提供 18 类、36 份 Markdown（包括四类阶段总体文档讨论稿）。旧 `1.0.0` / `1.1.0` / `1.2.0` 包原样归档，已有锁定继续读取其原始内容。项目显式锁定一个有效包与层级 `core/organization/project`，没有隐含覆盖或逐文件随机选版。QA 可维护本地组织/项目包：完整复制公共包目录后修改 ID/版本、适用范围、章节与正文，并重新计算各文件 SHA-256。修改内容必须使用新版本；计划显示最终有效包。一个增量开始创建实例后不切换包，旧增量与旧文件保持原引用。缺失、篡改、不兼容或不存在的语言/类型失败关闭。

私有包与需求只在项目授权范围内保存；不要复制到本公共 Skill 仓库。交付快照也可能包含私有证据，应与项目事实放在同一受控仓库，不能作为公共 Golden 或发行附件上传。

交付基线与 `adopt-baseline` 的 Artifact 核对基线不同。前者要求完整六阶段治理、全部 Gate 批准和当前 Verify，通过只读 Git/SVN 命令核对指定版本中的规范文件。Git 使用完整 commit ID；SVN 使用一致的数字 revision 与仓库路径。Runtime 的验证/刷新缓存允许在受理源码后重新生成，Claim/Review 等权威事件必须与来源一致。此处的“已接受来源”由明确授权的维护者指定，不提供 v0.6.1 的可信平台审批映射。

快照冻结需求、范围、过程、模板正文、交付件、审计及本地证据字节。单文件上限 16 MiB，总证据上限 100 MiB，超过预算明确拒绝；远程链接不被当作本地不可变证据。下一增量从当前过程重新生成待治理状态，状态 revision 单调增长，历史状态和完整 Runtime 留在带摘要的旧快照。旧阶段没有被重新打开。精确版本证据须通过 `reuse_verification` 显式引用并校验旧快照；当前文件不能替代历史证明。当前复用操作支持 UTF-8 证据，其他二进制保留在快照中。

Dashboard 展示需求树关系、增量、版本、模块、责任、优先级、定义与分解、所有实例/模板和独立验证结果，支持组合文字筛选。JSON 投影的 `coverage` 分别列出定义、分解、实现、验证、已接受判据和全量满足程度。一个 IR 只交付部分判据时，全量状态仍为 `partial`。

## 公开参考

模板正文为本项目原创骨架，不是华为内部 QA 模板的复刻。

- [华为云 CodeArts Req 基本概念](https://support.huaweicloud.com/intl/zh-cn/productdesc-projectman/codeartsreq_07_2008.html)：IR/SR/AR 术语及分层需求组织。
- [NASA 需求管理](https://www.nasa.gov/reference/6-2-requirements-management/)：分层追踪、版本控制和变更影响分析。
- [NASA 需求验证矩阵](https://www.nasa.gov/reference/appendix-d-requirements-verification-matrix/)：稳定 ID、来源和验证方法的矩阵组织。
- [NASA 软件设计说明指南](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695674/5.13+-+SwDD+-+Software+Design+Description)：设计视图、接口、理由和追踪内容。

参考资料用于确定字段和组织原则；不代表这些机构认可或认证本 Skill。

## 模板草案、评审、发布与显式转换

启用模型时选中的内置包是待项目采纳的模板来源，不代表 QA 已批准。所有包（包括内置包）在新建受管实例前，均需完成以下三个独立请求；每个请求仍先 `--request` 零写入预览，再用保存的计划 `--apply --actor <同一声明人> --authorized`。以下身份仅为示意，实际使用时填写真实授权人员的项目身份；作者与评审者必须不同。

```yaml
request_id: qa-draft-request
operation: draft_templates
reason: QA 编写并提交中英文模板包
id: qa-draft-1
path: '' # 内置包；私有包使用项目相对目录
actor: qa-author
actor_type: human
```

```yaml
request_id: qa-review-request
operation: review_templates
reason: 已逐项审查中英文结构、适用性、字段与填写说明
id: qa-review-1
source: qa-draft-1
actor: qa-reviewer
actor_type: human
decision: approved # 或 rejected；拒绝结果不得发布
```

```yaml
request_id: qa-publish-request
operation: publish_templates
reason: 授权发布本次已评审的精确模板包
id: qa-publication-1
source: qa-review-1
actor: qa-publisher
actor_type: human
```

发布后再用 `pin_templates` 选择相同 `path`。记录保存在 `.ipd/template_publications/`，由规范登记引用其 SHA-256，并进入交付快照及仓库来源核对。每份记录绑定包 ID、版本、manifest 摘要、前序记录、声明人员、决定、理由和受理 revision。同版本内容改变、较新的拒绝评审、缺失/篡改记录、过期计划和不匹配的应用人均阻止受理；精确重试不重复写入。记录是显式本地声明，未提供平台认证或可信审批映射。旧包不会自动追认一份并未发生的 QA 评审。

旧活动实例需要转换时，先完成目标包的评审与发布。人工 QA 可在当前 Owner 的 `work` 期间办理这三类记录，保持 Claim 和有效模板不变；Review 期间仍禁止更改输入。在仍持有该 Owner Claim 的 `work` 步骤提交：

```yaml
request_id: convert-current-documents
operation: replace_templates
reason: 为旧格式补齐受控需求父引用列
path: ''
replacements:
  - old: old-sr-instance
    instance:
      id: new-sr-instance
      key: system
      requirements: [sr-1@1]
      owner: plan.integrated_plan
      document_type: sr_spec
      path: docs/mvp/SR-v2.md
      title: 系统需求管理表
      scope: 本轮已承诺系统需求
      locale: zh-CN
```

必须明确列出当前增量全部有效实例，且它们属于同一个当前 Owner；保留每份实例的键、需求范围、Owner、类型和语言。预览列出新文件内容及指纹；授权应用为新路径创建未填写模板，并以 `supersedes` 关联旧实例。旧文件和登记保留，新实例通过填写和检查后才能 Close/Review；旧格式不再计入本轮有效文档的数量。多 Owner 或已完成评审的成果使用下一增量：应在升级前用原工具完成并冻结旧轮，再升级并为新轮锁定新包。本版不支持直接转换尚未完成的跨 Owner 开发态历史增量；不能用转换绕过 Claim、批准或原路径保护。该操作不移动旧文件，不是通用路径迁移。

## 增量审计与阶段输入

启用模型后的 Runtime 使用 `1.1`，新事件携带 `increment_context`：增量 ID、基础交付基线和本轮精确范围 SHA-256；完整范围仍在规范增量登记与冻结快照中。`increment_context_start` 划出新契约事件起点，之前事件保持原文。Claim、Close、Review、批准、阶段推进、Refresh、Verify、生命周期完成和需求操作均使用同一规则。交付基线事件保留被接受增量；下一轮明确绑定前一基线；产品退役是独立事件。

未启用模型的项目保留 Runtime `1.0`。旧工具读取 `1.1` 时拒绝，不允许继续写入；不要通过手改 schema 降级。历史需求登记未包含 `template_records` 时仍可读取，但新建/继续受管文档需补齐显式发布记录。历史验证结果仍遵循上下文匹配规则。

早期 Owner/Gate 的批准只绑定当期规范输入：TR1 不要求 SR/AR 的未来分解，TR2 不要求未来实现分配，TR3 绑定实现关联，TR4 绑定本轮验证结果。改变早期需求内容或共享约束仍会使相关批准失效。持有当前 Claim 的执行者可在 `work` 中登记实际验证结果，以便先写完文档、执行测试、再 Close/Review；其他人的验证写入被拒绝，评审期间仍不得改变输入。

完整双增量合成验证入口：`python -B scripts/simulate_incremental_development.py --locale zh-CN`；英语使用 `--locale en`。它实际执行会议室软件测试，逐阶段创建总体文档与需求表，并分别完成两轮六阶段、B1/B2 和独立退役；其中人类决定均明确为测试声明，不代表生产项目或真实 QA 已验收。
