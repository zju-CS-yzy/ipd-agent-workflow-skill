# 架构

[English](architecture.md) | [简体中文](architecture.zh-CN.md)

仓库包含两个协同表面：`SKILL.md` 指导 Agent 的决策，`ipdctl` 提供确定性的流程裁剪、状态迁移、生成视图和本地版本库核对。

## 组件

| 组件 | 职责 | 禁止行为 |
| --- | --- | --- |
| `SKILL.md` 与 `references/` | 路由 IPD 工作、证据判断和人类 Gate 边界 | 替代项目事实或授予额外修改权限 |
| `ipdctl.state` | 创建、加载并原子化保存状态 | 接受部分写入或静默修复无效状态 |
| `ipdctl.validation` | 验证结构、引用、证据、依赖闭合和 Gate 不变量 | 修改状态 |
| `ipdctl.engine` | 为合法迁移返回修订副本 | 在没有人类授权记录时完成最终批准 |
| `ipdctl.process_model` / `tailoring` | 按 `core -> task_type -> capability -> project` 编译稳定流程事实并生成纯 Diff | 在可复用 Policy 中嵌入项目实例或推测迁移 |
| `ipdctl.process_extensions` | 加载并验证 `.ipd/process_extensions.yaml` 中追加的 Activity、Deliverable、Relation、Criteria 与 Migration | 删除或覆盖之前层的实体 |
| `ipdctl.refinement` | 验证带 Fingerprint 的 `expand` Plan、计算结构叶节点闭包，并把已评审新增项合并到项目层 | 猜测分解、修改运行时状态，或把 `refines` 当成执行顺序 |
| `ipdctl.dependencies` | 查找依赖环和未满足的交付件依赖 | 推测缺失依赖 |
| `ipdctl.runtime` | 记录 Agent Claim、Lease 和命令事件 | 认证人类身份或提供分布式锁 |
| `ipdctl.transaction` | 串行执行单个项目的 CLI 修改并恢复被中断的多文件写入 | 协调不同检出副本或替代 VCS 锁 |
| `ipdctl.i18n` / `messages.yaml` | 通过显式 Translator 解析 `en` 或 `zh-CN` 展示文字 | 翻译机器契约、修改事实或保存进程级全局 locale |
| `ipdctl.dashboard` | 编排并原子发布 Dashboard 目录及哈希 | 成为可写事实来源 |
| `ipdctl.dashboard_model` | 将流程、状态和运行时事实投影为标准状态与类型化图 | 发明事实或修改源状态 |
| `ipdctl.dashboard_svg` | 生成分层泳道、类型化节点和关系边 SVG | 调用 Graphviz 或直接读取项目文件 |
| `ipdctl.dashboard_html` | 生成离线 Dashboard、矩阵、筛选器、缩放和节点详情 | 持久化编辑或依赖在线资源 |
| `ipdctl.traceability` | 解析全局实体 ID 和悬空链接 | 把自由文本当作有效实体引用 |
| `ipdctl.policy` | 加载并验证安全裁剪规则 | 允许禁用不可裁剪控制项 |
| `ipdctl.repository` | 只读获取 Git/SVN root、revision 和 dirty 状态 | 提交、更新、打标签、推送或修改版本库 |
| `ipdctl.reconcile` | 验证 Binding、捕获精确路径快照，并把变更路径核对到单一 Deliverable Owner | 根据文件名猜测权威归属 |
| `ipdctl.eligibility` | 把生命周期与 Binding Readiness 投影为 Context、Claim 和 Dashboard 共用的决定 | 修改状态或授权人类基线决定 |
| `ipdctl.cli_v2` | 暴露完整裁剪与执行生命周期 | 隐藏验证错误或隐式覆盖状态 |

## 数据流

Agent 初始化项目，根据 Task Profile 与项目扩展编译流程，读取上下文，领取可执行工作，附加证据并提交评审。编译按固定 `core -> task_type -> capability -> project` 顺序确定性追加；每个流程节点带有 Layer/Source Provenance 与阶段派生的 Maturity，TR 和 DCP 保留各自独立的 Criteria。依赖验证拒绝环路，也拒绝早期 Phase 的 Deliverable 依赖后期 Phase Deliverable。

`tailor --preview` 以纯函数方式生成五部分 Diff，不写入文件。存在活动 Claim 时禁止实际 Re-tailor。首次真正移除已有历史的 Deliverable 时，必须有显式项目 Migration Mapping，并由人类授权应用。旧节点作为 State-only `superseded` 节点保留 Evidence 与 Review；新目标从 `planned` 开始，单条只追加 `process_migration` Event 记录该决定。框架不会用启发式方法分发历史 Acceptance。

同一边界也禁止普通 Re-tailor 在保留旧 Approval 的同时，以相同 ID 改写现有
Deliverable 的语义；此类变化必须使用新 ID 和显式 Migration。指向已批准或已关闭
Phase 的语义变化（包括 TR/DCP Criteria）会在写入前被拒绝，Preview 仍可用于设计
受控替代方案。Schema `1.0` 升级到 `2.0` 时，仅允许确定性的 Core Provenance、
Maturity 与规范 Readiness Criteria 补齐。

显式项目 Refinement Trigger 进入 `due` 后，`refine --preview` 会以零写入方式
验证带 Fingerprint 的 `expand` Plan。经授权的应用保留已评审父节点，将其作为
Abstract 历史聚合节点，并追加干净的 Planned 子节点。结构关系 `refines` 会被
展示和审计，但不进入 `depends_on` 图。Gate Readiness 把 Abstract Requirement
解析为具体叶节点；叶节点集合变化会使旧批准失效并增加 Review Epoch，同时原有
Evidence 继续作为历史保留。系统会报告 Binding Impact，但不会推断或转移 Owner。
具体细化子 Deliverable 必须有用户显式编写的 Owner；Placeholder 与 Abstract
节点是不可 Claim 的结构事实，不要求 Owner。

Claim Preflight 与全部读取界面使用同一份 Binding Eligibility 投影。每个新 Claim 记录精确 Binding Window；Verify 成功后把精确 Artifact Baseline 带入下一轮。已有 Dirty 项目通过只追加、由人类明确授权的 Baseline Adoption Event 迁移，而不是伪造 Claim 或修改 VCS。Deliverable 与 Gate 都是显式评审 Subject。获得授权的人类决定只追加、不覆盖；最新一条获得授权的人类决定控制当前结果，完整历史仍可审计。只有当前阶段的必要 Gate Subject 满足控制要求时，`advance-phase` 才能成功。`refresh` 根据流程和状态事实生成 Dashboard，并显示 Provenance、Maturity 与 Checkpoint Criteria 供检查；`verify` 重新编译预期流程，并检查项目扩展、状态、证据路径、输出哈希、Binding Eligibility 和版本库核对。最终 Deliverable 与 TR/DCP 批准不能来自 Agent 身份。

状态写入先在目标目录生成临时文件，再原子替换。成功的引擎操作只将 `revision` 增加一次，并返回新对象，不修改输入对象。框架以项目解析后路径为键，在当前用户的系统临时目录中使用崩溃后自动释放的操作系统互斥锁；它覆盖恢复和完整命令周期，哈希锁文件不是项目产物。修改类 CLI 命令随后在完整的读取、预检、计算和写入周期内持有项目本地事务日志。日志先取得规范名称，再在修改前快照权威文件与生成输出，在异常或进程终止后恢复；提交时先原子退出活动状态，再清理备份。同一本地用户环境中的另一个并发项目命令会明确失败，可在活动命令结束后重试；不同操作系统账号或不同临时目录命名空间不能并发操作同一检出目录。如果操作系统无法确认日志所属进程是否仍在运行，恢复会按安全失败处理并保留日志，不会擅自回滚。

Dashboard 刷新先构建完整暂存树，再替换已有生成树。`data/state.json` 和 `data/graph.json` 是经过净化的只读投影，不是备用状态仓库。SVG 和 HTML 消费相同事实，所有受管理文件均被 Dashboard manifest 覆盖。

## 语言边界

语言只属于展示层。`init --locale` 写入 `task_profile.presentation.locale`，后续命令为当前项目解析 Translator，并显式传给 CLI 与 Dashboard。v0.2 Profile 缺少 locale 时按 `en` 处理，但不会自动改写文件。

切换 locale 会使已生成 Dashboard 过期，但不得重新裁剪流程，也不得改变状态、证据、评审、Claim、图节点 ID 或拓扑。

命令、参数、文件名、YAML/JSON 字段、Schema 路径、ID、状态、关系和报告 Code 在所有 locale 下保持英文。框架展示标签可以本地化；用户输入的名称、路径、证据和说明保持原样。机器可读 JSON 即使含本地化 `display_label`，字段和枚举仍保持稳定英文。

## 契约边界

[project_state.schema.json](../schemas/project_state.schema.json)、[tailored_process.schema.json](../schemas/tailored_process.schema.json)、[process_extensions.schema.json](../schemas/process_extensions.schema.json)、[refinement_plan.schema.json](../schemas/refinement_plan.schema.json) 与 [artifact_bindings.schema.json](../schemas/artifact_bindings.schema.json) 是可移植的结构契约。Python 验证还负责依赖环与 Refinement 环、阶段单调性、全局实体 ID 唯一性、引用完整性、按顺序解析最新人类授权决定、Migration 完整性、Gate 叶节点闭包 Epoch、实际变更路径 Owner 冲突、Claim Window Provenance 和 Phase 推进就绪度等 JSON Schema 不便表达的约束。

[tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) 保存不可裁剪的治理不变量，通用任务类型扩展位于 `policies/task-types/`，可复用且不含项目实例的能力位于 `policies/capabilities/`。通用 Sourced Component 能力只建模 Candidate Validation、Selection Decision 与 Integration Baseline，不包含实例路径或 Owner 推断。运行时使用 PyYAML 安全加载并执行确定性原子写入。

Binding Role 与流程 Provenance 相互独立。未填写 Role 或使用 `role: owner`
时映射唯一 Deliverable，并可授权该 Deliverable 的 Claim；
`role: shared_evidence` 必须为非 Critical，可引用多个 Deliverable，但不能授权
Claim，也不能满足 Critical Path 的 Owner 要求。

新编译输出 Process Schema `2.0`。当语义投影仍匹配不含 Capability 且项目扩展
为空的 Profile 时，Schema `1.0` 继续可读；启用任一层前都必须先 Preview，再
Re-tailor。

运行时会为事件和 Claim Lease 自动记录 UTC 时间戳，但不会推断评审人权限，也不会在状态中捕获个人检出路径。调用方只能记录获得认可的外部标识或不可变 VCS Revision 作为证据。
