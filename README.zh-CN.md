# IPD Agent Workflow Framework

[English](README.md) | [简体中文](README.zh-CN.md)

本仓库提供统一的双语 Codex Skill 与 Python 执行层，用于以可追溯证据管理集成产品开发（IPD）。它能够分层编译裁剪流程、控制交付件与评审状态、生成交互式 Dashboard，并将工程变更与 IPD 事实进行核对。

当前预发布目标：`v0.5.1-beta`（Python 包 `0.5.1b1`）。

英文与简体中文使用同一套代码、Schema、Policy、ID 和状态数据。项目在初始化时选择展示语言；机器契约始终保持英文。

运行时有一条不可突破的边界：AI Agent 可以准备并验证 Gate，但 TR/DCP 的最终批准必须包含获得授权的人类批准记录。

## 能力

- 根据 `task_profile.yaml` 生成 Phase、TR、DCP、Gate、Activity、Deliverable、Dependency 和 Review requirement。
- 支持 `software`、`hardware`、`embedded`、`robotics`、`ai_system` 和 `material_change` 类型。
- 按固定的 `core -> task_type -> capability -> project` 顺序确定性编译流程，并支持 `capability_patterns` 与追加式项目扩展。
- 在不丢失父节点历史、也不猜测项目模块划分的前提下，把已评审的项目 Deliverable 渐进细化为显式 Activity 与子 Deliverable；子节点可包含留待后续细化的显式 Placeholder 中间层。
- 记录节点 `provenance`、阶段派生的 `maturity`、独立 TR/DCP Criteria，并验证依赖的阶段单调性。
- 严格串行执行 `context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify` 协议。
- 强制执行八状态交付件生命周期、依赖闭合、证据、评审记录及人类授权验收。
- 保留全部评审决定，并以最新一条获得授权的人类决定作为当前结果，使被拒绝的工作可以修正、重新评审并批准，而不抹除历史记录。
- 每轮评审只锁定一个规范 Deliverable 或 Gate Subject，只有当前阶段所需治理检查通过后才能推进 Phase。
- 在 `.ipd/dashboard/` 生成离线交互式 Dashboard，包含阶段泳道、类型化 SVG、节点详情、Deliverable Matrix、Gate Matrix、标准 JSON 投影以及由事实生成的治理登记表与 Gate 计划。
- 在不改变 YAML/JSON 字段、ID、状态、关系和图拓扑的前提下，以 `en` 或 `zh-CN` 展示 CLI 与 Dashboard 文案。
- 只读检查 Git/SVN 的 branch、revision、dirty 和 remote 信息，并根据显式绑定核对变更。
- 对 Critical Artifact 执行单一 Owner、逐轮 Claim Window 与已有 Dirty 项目的人工授权迁移基线约束。
- 区分能够授权 Claim 的唯一 Binding Owner 与可供多个 Deliverable 引用、但不授权 Claim 的非 Critical `shared_evidence`。
- Re-tailor 时保留 Claim 追溯关系，在 Preview 中显示追溯新增、删除与重定向，并在无法解释的 Claim Link 丢失前 Fail-closed。
- 支持把旧 Generic Gate 显式迁移到 Canonical 或项目 Gate，也支持经授权的精确同 ID 依赖修正；两者都保留历史，并要求受影响工作重新评审。
- 原子化持久化 YAML 事实文件，使生成视图与事实来源保持分离。

此 Beta 版本不提供托管服务、企业身份认证或可写 Web UI，也不会自动执行 Git/SVN 的提交、打标签、推送、拉取、抓取或更新操作。

## 快速开始

需要 Python 3.10 或更高版本：

```bash
git clone https://github.com/zju-CS-yzy/ipd-agent-workflow-skill.git
cd ipd-agent-workflow-skill
python -m pip install -e .
```

初始化中文项目并生成首个流程：

```bash
ipdctl init /path/to/project --name my-project --task-type software --locale zh-CN
ipdctl tailor /path/to/project --preview
ipdctl tailor /path/to/project
ipdctl context /path/to/project
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

初始化英文项目时改用 `--locale en`。如果不安装包，可在仓库根目录使用 `python -m ipdctl ...`。要让 Codex 发现此 Skill，请将仓库放到 `$CODEX_HOME/skills/ipd-agent-workflow-skill` 或等效的用户 Skill 目录。

## 受控执行

运行时最多允许一个活动 Claim。正常的验收或返工迭代不得跳步：

```bash
ipdctl claim DELIVERABLE --project-root /path/to/project
# 执行已授权的工作
ipdctl close DELIVERABLE --project-root /path/to/project --evidence evidence/DELIVERABLE/result.md
ipdctl review DELIVERABLE --project-root /path/to/project --reviewer REVIEWER
ipdctl render-dashboard /path/to/project
ipdctl approve DELIVERABLE --project-root /path/to/project --reviewer HUMAN --actor-type human --authorized --evidence evidence/DELIVERABLE/approval.md
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

需要记录真实的人类拒绝时，将 `approve` 改为 `reject`。Agent 可以准备评审，
但不能冒充人类做最终决定。`close --status blocked` 是明确的中止路径，之后
仍须完成 `refresh` 和 `verify` 才能开始新 Claim。`context --json` 会把失去
活动 Lease 的 `in_progress` 交付件列入 `recoverable_claims`；使用
`claim DELIVERABLE --recover` 恢复。其他 Actor 尚未过期的 Lease 不能被接管。
如果过期的是没有 Binding Window 的 v0.3.1 Claim，必须先记录精确且由人类
授权的迁移基线；首次恢复会生成不可变的 Migration Window，后续恢复继续
复用该 Window。

`close` 会把规范 Deliverable ID 绑定为
`project.current_iteration_subject`；Gate Review 则绑定解析后的规范 Gate ID。
在人工决定清除此锁之前，`review`、`approve` 与 `reject` 对其他对象都会零写入
失败。已经停在 `review` 的 v0.5.0 项目不能安全推断缺失对象，必须由获得授权的
人类明确选择仍满足条件的现有 ID 并记录原因：

```bash
ipdctl review SUBJECT --project-root /path/to/project --reviewer HUMAN \
  --actor-type human --authorized --recover-subject --reason TEXT
```

该命令只记录恢复事件，不记录评审决定；之后仍须执行正常 Review 与批准或驳回。

面向机器的 `context --json` 会区分 `waiting_items`（未满足的 `depends_on`
前置项）、`explicit_blockers`（生命周期状态为 `blocked`）和
`governance_blockers`（Binding、Refinement、Claim Provenance 或协议失败）。
`blocked_items` 继续作为仅限 Deliverable 范围的去重兼容并集；
`project.claim_readiness` 等项目级条目只进入 `governance_blockers`。不能用兼容
汇总字段推断具体根因。

`advance-phase` 要求当前 Phase 的全部 Gate 已批准，而且最近一次通过的验证
同时匹配当前 State Revision 与重新计算的验证输入指纹。该命令只推进一个
Phase，并把 Workflow 留在 `refresh`；继续 Claim 或 Gate 评审前必须再次执行
`refresh` 和 `verify`。在最终 `lifecycle` Phase 中，全部 Gate 获批且验证通过
时，运行时只记录一次 `lifecycle_complete` 事件。
每个 Phase 的 canonical 决策固定为先 TR、后 DCP；手工篡改而失效的 Gate
指针会被拒绝。当前 Phase 还必须与有序 `advance_phase` 事件历史一致，因此
同时修改整组 Phase 指针也不能跳过治理流程。

完整 CLI 命令面是 `init`、`tailor`、`refine`、`context`、`status`、`adopt-baseline`、`claim`、
`close`、`review`、`approve`、`reject`、`render-dashboard`、`refresh`、`verify`、
`advance-phase`、`repository`、`reconcile` 和 `validate`。`validate --json`
输出稳定的机器可读结果；普通 CLI 与 Dashboard 文案继续遵循项目 Locale。精确参数请运行
`ipdctl COMMAND --help`，规范摘要见
[references/state-contract.md](references/state-contract.md)。

## 分层流程编译

`task_profile.yaml` 选择任务类型和可选的可复用能力。Capability 采用显式启用：
省略 `capability_patterns` 或将其设为 `[]`，都会保留基础 Task-type 流程，不添加
任何 Capability。内置目录如下：

| Capability pattern | 治理范围 |
| --- | --- |
| `sourced_component_integration` | 候选组件验证、选型决策与受控集成基线。 |
| `module_decomposition_and_verification` | 模块分解、证据驱动的模块实现与模块验证。 |
| `interface_contract_and_integration` | 版本化接口契约、集成证据与一致性验证。 |
| `release_and_lifecycle_assurance` | 发布策略、受控候选版本、验证、移交与生命周期保障。 |

例如，以下配置启用模块和接口治理，但不会预设产品分解、仓库路径或 Owner：

```yaml
capability_patterns:
  - module_decomposition_and_verification
  - interface_contract_and_integration
```

模块 Capability 会加入触发式 `placeholder`
`module.implementation_baseline`。当 `module.decomposition_baseline` 被
`accepted` 后，该节点的细化要求进入 `due`。此时应通过 `ipdctl refine`，用经过
审核的项目自有 Activity 与 Deliverable 展开裁剪时未知的模块结构，而不是 Claim
这个 Placeholder。

类型化 `supports` 与 `verifies` 关系用于在 Traceability、Dashboard Graph 和
Review Context 中保留工程语义，不参与 Readiness 或执行拓扑。只有
`depends_on` 会形成执行前置关系。

`ipdctl init` 会创建空的规范 `.ipd/process_extensions.yaml`，作为项目拥有的
第四层。该文件可追加 Activity、必须评审的 Deliverable、类型化关系（`depends_on`、`supports`、`verifies`、
`supersedes`）、独立 TR/DCP Criteria、项目自有 Generic Gate、显式 `replace` 或
`split` Deliverable 迁移、单对单 `gate_migrations` 以及精确的
`dependency_corrections`。
它不能删除或覆盖之前层的事实。重复 ID、依赖环、未知引用，以及早期 Phase 的
Deliverable 依赖后期 Phase Deliverable 都会使验证失败。
对于尚无该文件的 v0.4 之前项目，`tailor --preview` 仍保持零写入；首次成功的
实际 `tailor` 会先生成规范空扩展文件，再发布 Schema `2.0` 流程。

重新裁剪前先执行 `ipdctl tailor PATH --preview`。Preview 是纯只读操作；
`--preview --json` 固定输出 `added`、`removed`、`changed`、`migrations` 和
`ambiguous`。同一 Preview 还会显示 `state.traceability` 的新增、删除和重定向；
没有完整迁移却会丢失 Claim Link 时，结果会在 `ambiguous` 中阻止写入。流程拥有
的关系按新编译结果重建，两个端点仍存在的 Claim Link 则继续保留。存在活动
Claim 时禁止任何实际 Re-tailor。如果改动会删除已有历史
且尚未 `superseded` 的 Deliverable，项目扩展必须提供显式迁移映射；首次应用时
还需由人类明确授权执行：

```bash
ipdctl tailor PATH --apply-migrations --actor HUMAN \
  --actor-type human --authorized --reason TEXT
```

旧状态节点转为 `superseded` 并原位保留 Evidence 与 Review History；新目标节点
保持 `planned`，不得继承 Acceptance、Evidence 或 Review。纯追加变更及已应用
迁移保持幂等，不要求重复授权。

旧 Generic Gate 只能通过单对单 `gate_migrations` 转移到候选流程中存在的目标
Gate，并保留历史。对有历史 Deliverable 做同 ID 依赖修正时，必须声明精确的
`before` 与 `after` 集合、保留历史并要求重新批准。首次有效应用复用同一条人工
授权 `--apply-migrations` 边界：受影响工作变为 `blocked`，未批准的相关 Gate
失效，Evidence 与 Review 全部保留；若相关 Gate 已获批准，则 Fail-closed，而
不会隐式重新打开。

普通 Re-tailor 不能在保留同一 ID 的同时，改写已经具有受治理 Status、Evidence
或 Review 的 Deliverable 语义；应创建新的 Deliverable ID，并使用显式 Migration
路径。任何指向已有 Gate 获得批准或已经关闭的 Phase 的流程改动（包括 TR/DCP
Criteria）也会 Fail-closed；Preview 仍可供审核，所有权威文件保持不变。Legacy
Schema `1.0` 仅允许补齐 Schema `2.0` 所需的确定性 Core Provenance、Maturity 与
规范 Readiness Criteria。

新编译的流程使用 Schema `2.0`。当语义投影仍与不含 Capability 且项目扩展为空
的 Profile 一致时，运行时可以继续读取 Schema `1.0` 的旧流程。启用 Capability
或添加项目扩展内容前，应先 Preview，再执行 Re-tailor。

## 渐进细化

细化要求既可以来自 `.ipd/process_extensions.yaml` 中项目自有的
`refinement_requirements`，也可以来自已选 Capability 中由 Policy 定义的
Placeholder。声明固定 Root、初始 `definition_state`、显式 Trigger 和
`all_children_accepted` 完成规则。内置模块 Capability 中，只有
`module.decomposition_baseline` 被 `accepted` 后，
`module.implementation_baseline` 才会进入 `due`。Task-type 与 Capability Policy
都不会猜测项目中的真实模块或功能；只有项目证据使该要求到期后，Agent 才准备
单独的、可人工审核的 Refinement Plan。

只有 Deliverable 可以成为细化要求的 Root。Trigger Subject 必须在 Root 的 Gate
之前可达：要求 accepted 的 Deliverable 不能处于更晚 Phase，要求 approved 的
Gate 必须处于更早 Phase。Plan 可以加入具体子节点和显式 `placeholder` 中间层；
每个 Placeholder 都必须声明自身可执行的细化要求与 Trigger。Placeholder 不能
以自身为 Trigger，也不能使用依赖该 Placeholder 的 Deliverable 作为 Trigger。
嵌套细化 Root 在当前 Plan 中必须保持为叶节点；其后代必须由下一份单独授权的
Plan 生成。

```bash
ipdctl context PATH --json
ipdctl refine PATH --plan refinement-plan.yaml --preview --json
ipdctl refine PATH --plan refinement-plan.yaml --apply \
  --actor HUMAN --actor-type human --authorized --reason TEXT
ipdctl refresh PATH
ipdctl verify PATH
```

Plan 使用 `mode: expand`，并引用 `context` 返回的精确
`process_fingerprint`。Preview 确定且零写入。存在活动 Claim、Trigger 尚未满足、
Base Fingerprint 过期，或 Root 不在当前 Phase 时，Apply 都会失败。成功 Apply
会把新节点追加到项目扩展，把 Root 变为 Abstract 聚合节点，让子 Deliverable
从 `planned`、空 Evidence、空 Review History 开始，并记录一条人工授权的
`process_refinement_applied` Event。同一 Plan 重放是无写入操作；相同 ID 对应
不同内容则视为冲突。

已经 Apply 或当前已经 `due` 的细化谱系不能通过普通 `tailor` 修改。本 Beta 中，
这类谱系的变化（包括迁移）必须使用新的、经过审核的 `refine` Plan；直接编辑项目
扩展会 Fail-closed。`refine` 还会证明当前 Profile 与 Extension 仍能编译为受治理
流程，并确认重放历史与 Agent Runtime Event 一致。

如果某个 Deliverable 的传递前置节点仍有 `pending` 或 `due` 的细化要求，该
Deliverable 不能被 Claim，并报告 `REFINEMENT_DEPENDENCY_REQUIRED`。Plan 不能
复用历史 Deliverable ID，也不能改写已经具有受治理生命周期历史的现有
Deliverable 依赖关系。

`refines` 只表示结构层级，永远不会成为执行前置关系；只有 `depends_on` 决定
执行顺序。Gate 使用 Abstract Root 的具体叶节点闭包。如果闭包变化，旧 Gate
Evidence 继续作为审计历史保留，但旧批准失效，必须进入新的 Review Epoch。
每个新的具体子 Deliverable 在 Claim 前必须有用户显式编写的 Owner Binding。
Placeholder 和 Abstract 节点仅表达结构，在后续 Plan 生成具体子节点之前不要求
Artifact Owner；框架不会把托管 Evidence Binding 或父节点 Binding 自动转移给
子节点。

## 语言契约

`init --locale` 将语言选择写入 `.ipd/task_profile.yaml`：

```yaml
presentation:
  locale: zh-CN
```

项目初始化前，Skill 跟随用户的会话语言；初始化后，面向用户的 CLI 和生成 Dashboard 使用 `presentation.locale`。没有此字段的 v0.2 项目仍然有效，并默认使用英文，运行时不会自动改写旧文件。

命令、参数、文件名、ID、YAML/JSON 字段、Schema 路径、`in_progress` 等状态值和 `depends_on` 等关系值保持英文。用户输入的名称、证据、路径和说明保持原样。JSON 输出仍是稳定的机器契约。

已有项目仅切换展示语言时，修改 `presentation.locale`，然后执行：

```bash
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

不要仅为切换语言重新运行 `tailor`。流程事实、评审、证据、Claim 和状态历史不得因此改变。

## 项目契约

权威事实文件是 `.ipd/task_profile.yaml`、`.ipd/process_extensions.yaml`、`.ipd/tailored_process.yaml`、`.ipd/project_state.yaml`、`.ipd/agent_runtime.yaml` 和 `.ipd/artifact_bindings.yaml`。`.ipd/dashboard/`、核对报告和验证报告都是派生视图。

每次执行 `tailor` 都会保留用户编写的 Artifact 规则，并为每个已裁剪的
Deliverable 重新生成一条框架托管的 `evidence/<deliverable-id>/**` 绑定。
该规则绑定的是持久证据，不是实现源码。真实的 `src/**`、`tests/**`、文档、
配置、Firmware、Hardware 和工具路径必须由用户在
`.ipd/artifact_bindings.yaml` 中显式绑定；框架不会推断归属，Critical Root
下存在未绑定变更会使验证失败。实际发生变化的 Critical Path 只能解析到一个
Deliverable Owner。新 Claim 事件会记录精确 Binding Window；旧的历史 Claim
不能永久证明后续变更的归属。

如果具体 Capability Deliverable 明确要求 Owner、却没有用户编写的规则，
Eligibility 会报告 `ARTIFACT_OWNER_REQUIRED`；由 Refinement 生成的具体子节点继续
使用更精确的 `REFINEMENT_OWNER_REQUIRED`。

未填写 `role` 的 Binding 与显式 `role: owner` 都保持单一 Owner 契约，并使用
唯一 `deliverable`。`role: shared_evidence` 改用 `deliverables` 列表，且必须
设置 `critical: false`；它只记录多个 Deliverable 对同一证据的引用关系。
Shared Evidence 不能授权 Claim，不能满足 Critical Path 所需的 Owner，也不会
削弱 Owner 冲突检查。

Artifact Binding 的 Glob 以项目根目录为锚点。例如 `README.md` 只匹配根文件，
`docs/*.md` 只匹配一层目录；只有完整的 `**` 路径段可以跨越零层或多层目录。

升级已有项目时，如果受治理文件已经处于 Dirty 状态，应先验证显式单一 Owner
规则，再使用 `ipdctl adopt-baseline` 预览并记录由人类授权的迁移基线。
基线只把精确路径哈希写入只追加的 Runtime 历史，不创建 Claim，也不修改
Git/SVN。如果旧 Claim 恢复前受治理文件再次变化，授权人员可以重新采纳经审核
的当前精确基线；失效采纳仍保留为历史，但不会遮蔽后续匹配记录。成功 Verify
后，精确 Artifact Baseline 会带入下一轮迭代。

修改类 CLI 命令使用项目本地恢复日志，串行执行完整的读取、预检、计算和写入
周期。并发修改会明确失败并可重试；多文件命令中断后，下一个命令读取事实前
会先恢复原有项目 Bundle。

Dashboard 入口是 `.ipd/dashboard/index.html`。独立资源位于 `assets/`，阶段视图位于 `phases/`，矩阵位于 `matrices/`，机器可读投影位于 `data/`。`manifest.json` 记录 locale、Binding/Eligibility 哈希以及全部受管理输出的哈希，使 `ipdctl verify` 能够识别过期或被修改的视图。生成的 `governance.md` 登记表与 Gate 计划还会根据规范版本、流程、状态、Deliverable 和 Gate 事实重新构造，因此即使同时修改正文与 Manifest Hash 也会校验失败。

活动迭代期间需要查看当前界面时使用 `render-dashboard`；它保持 State 与 Runtime 字节不变。正式 `refresh` 只接受 `context`、`refresh` 或 `verify` 工作流边界，会同步版本库事实、只增加一次 State Revision，并进入 `verify`。

结构契约位于 [schemas/](schemas/)。运行时还会验证依赖环、引用完整性、合法状态迁移、评审权限、证据存在性、Dashboard 新鲜度和版本库核对结果。不可裁剪的规则位于 [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml)，通用任务类型规则位于 [policies/task-types/](policies/task-types/)，可复用 Capability Policy 位于 [policies/capabilities/](policies/capabilities/)。

禁止在项目状态中保存 Token、密码、私钥或私人评审内容。证据应使用仓库相对路径、不可变 Revision 或获得认可的外部记录标识。

## 仓库结构

```text
SKILL.md                         Skill 单一入口与语言契约
agents/openai.yaml               Codex 界面元数据
references/                      按需读取的 Skill 指南
AGENT_RUNTIME_PROTOCOL.md        Agent 执行与权限契约
ipdctl/                          运行时和统一 messages.yaml 语言表
schemas/                         Profile、流程、细化、状态和运行时契约
policies/                        不可裁剪、任务类型与 Capability 规则
templates/project/               项目脚手架参考
templates/hooks/                 可选验证钩子
scripts/release_check.py         发布、版本和仓库边界检查
tests/                           标准库行为测试
docs/                            英文与简体中文说明
RELEASE_CHECKLIST.md             发布与模拟测试准入清单
```

## 验证

```bash
python -B -m compileall -q ipdctl tests scripts
python -B -m unittest discover -s tests -v
python -B scripts/simulate_progressive_refinement.py --json
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

模块边界见 [docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)，干净安装和发布验证见 [docs/deployment.zh-CN.md](docs/deployment.zh-CN.md)。修改契约前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 状态与许可证

在 `1.0` 之前，状态 Schema 和 Python API 仍可能调整。变更记录见 [CHANGELOG.md](CHANGELOG.md)，安全问题按 [SECURITY.md](SECURITY.md) 报告。

本项目使用 Apache-2.0 许可证，详见 [LICENSE](LICENSE)。

规范仓库：[github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)

### Dashboard 连线筛选与文件导航

交互 Dashboard 默认仅显示“前置项 → 依赖项”连线，可多选支持、验证、
取代和细化关系。筛选不改变节点位置或工作流事实，阶段切换保留本次会话的
筛选与缩放。交互图内联到 HTML，支持离线使用；独立 SVG 导出仍保留声明的
图关系。

点击交付物后，侧栏显示归属文件、共享证据、绑定规则及已有证据。存在的
文件提供打开和复制路径入口；缺失文件不生成打开链接。链接从
`.ipd/dashboard/index.html` 相对定位到项目根目录，HTTP 使用时应提供项目
根目录。浏览器支持的格式可以直接查看，其他格式可能下载；剪贴板不可用
时保留可选择复制的路径。不展开文件系统链接、派生 Dashboard 和 `.ipd/generated` 目录，
不把文件正文或电脑绝对路径复制到 Dashboard。

[Dashboard 测试与本地 Golden 验收](docs/dashboard-testing.md)说明自包含回归、浏览器及外部本地项目的测试门。
