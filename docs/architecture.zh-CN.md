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
| `ipdctl.process_model` / `tailoring` | 将通用 Task Profile 编译为稳定的 IPD 流程事实 | 嵌入具体项目实例数据 |
| `ipdctl.dependencies` | 查找依赖环和未满足的交付件依赖 | 推测缺失依赖 |
| `ipdctl.runtime` | 记录 Agent Claim、Lease 和命令事件 | 认证人类身份或提供分布式锁 |
| `ipdctl.i18n` / `messages.yaml` | 通过显式 Translator 解析 `en` 或 `zh-CN` 展示文字 | 翻译机器契约、修改事实或保存进程级全局 locale |
| `ipdctl.dashboard` | 编排并原子发布 Dashboard 目录及哈希 | 成为可写事实来源 |
| `ipdctl.dashboard_model` | 将流程、状态和运行时事实投影为标准状态与类型化图 | 发明事实或修改源状态 |
| `ipdctl.dashboard_svg` | 生成分层泳道、类型化节点和关系边 SVG | 调用 Graphviz 或直接读取项目文件 |
| `ipdctl.dashboard_html` | 生成离线 Dashboard、矩阵、筛选器、缩放和节点详情 | 持久化编辑或依赖在线资源 |
| `ipdctl.traceability` | 解析全局实体 ID 和悬空链接 | 把自由文本当作有效实体引用 |
| `ipdctl.policy` | 加载并验证安全裁剪规则 | 允许禁用不可裁剪控制项 |
| `ipdctl.repository` | 只读获取 Git/SVN root、revision 和 dirty 状态 | 提交、更新、打标签、推送或修改版本库 |
| `ipdctl.reconcile` | 依据显式绑定将变更路径映射到交付件 | 根据文件名猜测权威归属 |
| `ipdctl.cli_v2` | 暴露完整裁剪与执行生命周期 | 隐藏验证错误或隐式覆盖状态 |

## 数据流

Agent 初始化项目，根据 Task Profile 裁剪流程，读取上下文，领取可执行工作，附加证据并提交评审。Deliverable 与 Gate 都是显式评审 Subject。获得授权的人类决定只追加、不覆盖；最新一条获得授权的人类决定控制当前结果，完整历史仍可审计。只有当前阶段的必要 Gate Subject 满足控制要求时，`advance-phase` 才能成功。`refresh` 根据流程和状态事实生成 Dashboard；`verify` 检查流程、状态、证据路径、输出哈希和版本库核对。最终 Deliverable 与 TR/DCP 批准不能来自 Agent 身份。

状态写入先在目标目录生成临时文件，再原子替换。成功的引擎操作只将 `revision` 增加一次，并返回新对象，不修改输入对象。

Dashboard 刷新先构建完整暂存树，再替换已有生成树。`data/state.json` 和 `data/graph.json` 是经过净化的只读投影，不是备用状态仓库。SVG 和 HTML 消费相同事实，所有受管理文件均被 Dashboard manifest 覆盖。

## 语言边界

语言只属于展示层。`init --locale` 写入 `task_profile.presentation.locale`，后续命令为当前项目解析 Translator，并显式传给 CLI 与 Dashboard。v0.2 Profile 缺少 locale 时按 `en` 处理，但不会自动改写文件。

切换 locale 会使已生成 Dashboard 过期，但不得重新裁剪流程，也不得改变状态、证据、评审、Claim、图节点 ID 或拓扑。

命令、参数、文件名、YAML/JSON 字段、Schema 路径、ID、状态、关系和报告 Code 在所有 locale 下保持英文。框架展示标签可以本地化；用户输入的名称、路径、证据和说明保持原样。机器可读 JSON 即使含本地化 `display_label`，字段和枚举仍保持稳定英文。

## 契约边界

[project_state.schema.json](../schemas/project_state.schema.json) 是可移植的结构契约。Python 验证还负责依赖环、全局实体 ID 唯一性、引用完整性、按顺序解析最新人类授权决定和 Phase 推进就绪度等 JSON Schema 不便表达的约束。

[tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) 保存不可裁剪的治理不变量，通用任务类型扩展位于 `policies/task-types/`。运行时使用 PyYAML 安全加载并执行确定性原子写入。

运行时会为事件和 Claim Lease 自动记录 UTC 时间戳，但不会推断评审人权限，也不会在状态中捕获个人检出路径。调用方只能记录获得认可的外部标识或不可变 VCS Revision 作为证据。
