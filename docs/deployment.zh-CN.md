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

规范仓库是 [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)。发布 `v0.3.0-beta`（Python 包版本 `0.3.0b1`）之前，应配置分支保护、安全报告、Tag 和 Release 设置。

只有在模拟完整项目生命周期通过，且没有缺失产物或一级流程阻塞问题后，才能发布。发布资产限定为一个 Skill ZIP、一个 wheel、一个 sdist 和校验和；构建产物不得提交进仓库。

如果撤回某次发布，应在 GitHub 与 Changelog 中明确标记，禁止复用或静默移动已发布 Tag。
