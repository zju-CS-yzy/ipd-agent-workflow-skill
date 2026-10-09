# 部署与发布验证

[English](deployment.md) | [简体中文](deployment.zh-CN.md)

## 源码检出

使用 Python 3.10 或更高版本。运行时依赖 PyYAML 6.x，以安全地读取和写入可读的流程状态与 Policy 文件。

```bash
python -m pip install -e .
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

将仓库放在 `$CODEX_HOME/skills/ipd-agent-workflow-skill` 或等效用户 Skill 目录即可安装为 Codex Skill。`SKILL.md`、`references/`、`schemas/`、`policies/` 和 Python 包必须放在一起。

仓库只发布一个双语包，不分别维护中英文发行版。每个项目使用 `ipdctl init ... --locale en` 或 `--locale zh-CN` 选择展示语言。

## 干净包验证

按需要安装的能力选择发布包：

| 发布包 | 安装内容 |
| --- | --- |
| Skill ZIP 或源码检出 | 完整 Skill 指令、双语说明与 Python 执行层；将目录放入 Skill 目录 |
| Wheel | Python CLI、消息目录、Policy、Schema 和运行时模板；通过 pip 安装 |
| Sdist | 通过 pip 构建、安装 Python CLI 及其运行时资源的源码 |

在仓库外构建，避免在发布树留下 `build/`、`dist/` 或 `*.egg-info/`：

```bash
python -m pip wheel . --no-deps --wheel-dir <temporary-directory>
python -m pip install --force-reinstall <temporary-wheel>
ipdctl --help
```

从检出目录以外的位置，分别运行英文和简体中文生命周期 Smoke Test。这样可确认命令入口及内置 `ipdctl/messages.yaml` 来自 wheel，而非源码相对路径。

干净包检查必须确认 wheel 和 sdist 包含相同运行时代码和语言表。不得发布 locale 专属的源码包或 wheel。

## GitHub 发布

创建 Tag 前完成 [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)。源 Commit 必须干净，CI 必须通过，包版本与 Changelog 必须一致，发布卫生检查必须确认不存在缓存、构建输出、运行时生成数据、凭据类文件或高置信度 Secret。

规范仓库是 [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)。发布 `v0.5.1-beta`（Python 包版本 `0.5.1b1`）之前，应配置分支保护、安全报告、Tag 和 Release 设置。

直接前序版本验证必须使用真实 `v0.5.0-beta` Tag 创建受控项目，在不重新初始化的
前提下由 v0.5.1 读取。旧版中途 Review 状态必须在授权人类恢复精确评审对象前
Fail-closed，其他对象必须零写入失败；`render-dashboard` 必须保持 State 与 Runtime
字节不变，Review 阶段的 `refresh` 必须零写入失败，一次合法 Refresh 只能推进一个
Revision。该门还必须把 Dashboard Manifest `2.1` 升级到 `2.2`、生成 16 个文件、
发现治理版本/Gate/正文漂移、保持 Profile 与 Process 字节不变，并最终通过
`validate --json` 与 `verify`。

同时保留 v0.4.1 到 v0.5 的 Capability 升级门作为长期兼容回归：继续证明升级不会
隐式启用 Capability、Preview 零写入，而且显式选择只能新增预期节点与 Provenance。

同时保留 v0.3.2 到 v0.4 的流程 Schema 升级门作为长期兼容回归：继续保留
accepted 状态、Evidence 与 Review History；Capability 只能新增 planned 工作；
Dashboard 必须显示 Provenance；Binding Baseline 变化必须在获得授权的人类明确
采纳前保持 Fail-closed。

同时保留长期兼容性所需的 v0.3.1 项目原地升级回归：项目已有 Dirty Critical 文件，
验证单一 Owner Binding，预览并记录获得授权的 Baseline Adoption，使一个真实
v0.3.1 无 Window Active Claim 过期并完成恢复，再完成两轮完整 Claim 迭代，
并证明 Context、Dashboard、Reconcile 与 Verify 给出的
Eligibility 一致。Adoption 不得创建 Claim 或修改 Git/SVN。

只有在模拟完整项目生命周期通过，且没有缺失产物或一级流程阻塞问题后，才能发布。发布资产限定为一个 Skill ZIP、一个 wheel、一个 sdist 和校验和；构建产物不得提交进仓库。

如果撤回某次发布，应在 GitHub 与 Changelog 中明确标记，禁止复用或静默移动已发布 Tag。
