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

规范仓库是 [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)。发布 `v0.4.0-beta`（Python 包版本 `0.4.0b1`）之前，应配置分支保护、安全报告、Tag 和 Release 设置。

直接前序版本验证必须使用真实 `v0.3.2-beta` Tag 创建受控项目，在不重新
初始化的前提下由 v0.4 读取，证明 `tailor --preview` 零写入，再将流程重新
裁剪为 Schema `2.0`，同时保留 accepted 状态、证据和评审历史。启用
Capability 后，只能新增 planned 工作，Dashboard 必须显示 Provenance；绑定
契约发生变化时必须先 Fail-closed，只有经授权的人类明确采纳新基线后才能通过。

同时保留长期兼容性所需的 v0.3.1 项目原地升级回归：项目已有 Dirty Critical 文件，
验证单一 Owner Binding，预览并记录获得授权的 Baseline Adoption，使一个真实
v0.3.1 无 Window Active Claim 过期并完成恢复，再完成两轮完整 Claim 迭代，
并证明 Context、Dashboard、Reconcile 与 Verify 给出的
Eligibility 一致。Adoption 不得创建 Claim 或修改 Git/SVN。

只有在模拟完整项目生命周期通过，且没有缺失产物或一级流程阻塞问题后，才能发布。发布资产限定为一个 Skill ZIP、一个 wheel、一个 sdist 和校验和；构建产物不得提交进仓库。

如果撤回某次发布，应在 GitHub 与 Changelog 中明确标记，禁止复用或静默移动已发布 Tag。
