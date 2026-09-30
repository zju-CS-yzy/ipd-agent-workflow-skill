# IPD Agent Workflow Framework

[English](README.md) | [简体中文](README.zh-CN.md)

`v0.3.0-beta` 是一个统一的双语 Codex Skill 与 Python 执行层，用于以可追溯证据管理集成产品开发（IPD）。它能够裁剪流程、控制交付件与评审状态、生成交互式 Dashboard，并将工程变更与 IPD 事实进行核对。

英文与简体中文使用同一套代码、Schema、Policy、ID 和状态数据。项目在初始化时选择展示语言；机器契约始终保持英文。

运行时有一条不可突破的边界：AI Agent 可以准备并验证 Gate，但 TR/DCP 的最终批准必须包含获得授权的人类批准记录。

## 能力

- 根据 `task_profile.yaml` 生成 Phase、TR、DCP、Gate、Activity、Deliverable、Dependency 和 Review requirement。
- 支持 `software`、`hardware`、`embedded`、`robotics`、`ai_system` 和 `material_change` 类型。
- 严格串行执行 `context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify` 协议。
- 强制执行八状态交付件生命周期、依赖闭合、证据、评审记录及人类授权验收。
- 保留全部评审决定，并以最新一条获得授权的人类决定作为当前结果，使被拒绝的工作可以修正、重新评审并批准，而不抹除历史记录。
- 显式评审 Deliverable 或 Gate Subject，只有当前阶段所需治理检查通过后才能推进 Phase。
- 在 `.ipd/dashboard/` 生成离线交互式 Dashboard，包含阶段泳道、类型化 SVG、节点详情、Deliverable Matrix、Gate Matrix 和标准 JSON 投影。
- 在不改变 YAML/JSON 字段、ID、状态、关系和图拓扑的前提下，以 `en` 或 `zh-CN` 展示 CLI 与 Dashboard 文案。
- 只读检查 Git/SVN 的 branch、revision、dirty 和 remote 信息，并根据显式绑定核对变更。
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
ipdctl approve DELIVERABLE --project-root /path/to/project --reviewer HUMAN --actor-type human --authorized --evidence evidence/DELIVERABLE/approval.md
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

需要记录真实的人类拒绝时，将 `approve` 改为 `reject`。Agent 可以准备评审，
但不能冒充人类做最终决定。`close --status blocked` 是明确的中止路径，之后
仍须完成 `refresh` 和 `verify` 才能开始新 Claim。`context --json` 会把失去
活动 Lease 的 `in_progress` 交付件列入 `recoverable_claims`；使用
`claim DELIVERABLE --recover` 恢复。其他 Actor 尚未过期的 Lease 不能被接管。

`advance-phase` 要求当前 Phase 的全部 Gate 已批准，而且最近一次通过的验证
同时匹配当前 State Revision 与重新计算的验证输入指纹。该命令只推进一个
Phase，并把 Workflow 留在 `refresh`；继续 Claim 或 Gate 评审前必须再次执行
`refresh` 和 `verify`。在最终 `lifecycle` Phase 中，全部 Gate 获批且验证通过
时，运行时只记录一次 `lifecycle_complete` 事件。
每个 Phase 的 canonical 决策固定为先 TR、后 DCP；手工篡改而失效的 Gate
指针会被拒绝。当前 Phase 还必须与有序 `advance_phase` 事件历史一致，因此
同时修改整组 Phase 指针也不能跳过治理流程。

完整 CLI 命令面是 `init`、`tailor`、`context`、`status`、`claim`、
`close`、`review`、`approve`、`reject`、`refresh`、`verify`、
`advance-phase`、`repository`、`reconcile` 和 `validate`。精确参数请运行
`ipdctl COMMAND --help`，规范摘要见
[references/state-contract.md](references/state-contract.md)。

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

权威事实文件是 `.ipd/task_profile.yaml`、`.ipd/tailored_process.yaml`、`.ipd/project_state.yaml`、`.ipd/agent_runtime.yaml` 和 `.ipd/artifact_bindings.yaml`。`.ipd/dashboard/`、核对报告和验证报告都是派生视图。

每次执行 `tailor` 都会保留用户编写的 Artifact 规则，并为每个已裁剪的
Deliverable 重新生成一条框架托管的 `evidence/<deliverable-id>/**` 绑定。
该规则绑定的是持久证据，不是实现源码。真实的 `src/**`、`tests/**`、文档、
配置、Firmware、Hardware 和工具路径必须由用户在
`.ipd/artifact_bindings.yaml` 中显式绑定；框架不会推断归属，Critical Root
下存在未绑定变更会使验证失败。变更所映射的 Deliverable 还必须在 Agent
Runtime 中存在可审计的 `claim` 事件；仅写一条绑定规则不能伪造领取关系。
有效 Claim 事件必须包含 Deliverable、Actor、UTC 时间和不晚于当前状态的
Revision。

Dashboard 入口是 `.ipd/dashboard/index.html`。独立资源位于 `assets/`，阶段视图位于 `phases/`，矩阵位于 `matrices/`，机器可读投影位于 `data/`。`manifest.json` 记录 locale 并保存全部受管理输出的哈希，使 `ipdctl verify` 能够识别过期或被修改的视图。

结构契约位于 [schemas/](schemas/)。运行时还会验证依赖环、引用完整性、合法状态迁移、评审权限、证据存在性、Dashboard 新鲜度和版本库核对结果。不可裁剪的规则位于 [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml)，通用任务类型规则位于 [policies/task-types/](policies/task-types/)。

禁止在项目状态中保存 Token、密码、私钥或私人评审内容。证据应使用仓库相对路径、不可变 Revision 或获得认可的外部记录标识。

## 仓库结构

```text
SKILL.md                         Skill 单一入口与语言契约
agents/openai.yaml               Codex 界面元数据
references/                      按需读取的 Skill 指南
AGENT_RUNTIME_PROTOCOL.md        Agent 执行与权限契约
ipdctl/                          运行时和统一 messages.yaml 语言表
schemas/                         Profile、流程、状态和运行时契约
policies/                        不可裁剪规则和任务类型规则
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
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

模块边界见 [docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)，干净安装和发布验证见 [docs/deployment.zh-CN.md](docs/deployment.zh-CN.md)。修改契约前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 状态与许可证

在 `1.0` 之前，状态 Schema 和 Python API 仍可能调整。变更记录见 [CHANGELOG.md](CHANGELOG.md)，安全问题按 [SECURITY.md](SECURITY.md) 报告。

本项目使用 Apache-2.0 许可证，详见 [LICENSE](LICENSE)。

规范仓库：[github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)
