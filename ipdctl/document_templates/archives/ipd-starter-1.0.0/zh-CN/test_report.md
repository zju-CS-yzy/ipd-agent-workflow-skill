---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'test_report'
template_id: 'ipd-starter.test_report'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 测试报告 — {{title}}

> 草稿。请用项目事实填写所有 [[TODO: ...]]，不得编造结果或批准。

<!-- ipd-section:subject -->
## 被测基线与执行配置

记录实际被测版本、环境、工具、数据和执行者。

[[TODO: subject]]

<!-- ipd-section:results -->
## 逐用例实际结果

填写用例版本、实际结果、判定和不可变证据引用；未运行不得写通过。

[[TODO: results]]

| 用例版本 | 需求 / 判据 | 实际结果 | 判定（通过/失败/跳过/未知） | 证据摘要 |
| --- | --- | --- | --- | --- |
| [[TODO: results-1]] | [[TODO: results-2]] | [[TODO: results-3]] | [[TODO: results-4]] | [[TODO: results-5]] |

<!-- ipd-section:defects -->
## 缺陷、偏差与复测

关联缺陷、严重度、处置决定、修复版本及复测证据。

[[TODO: defects]]

<!-- ipd-section:coverage -->
## 需求覆盖与限制

列出通过、失败、跳过、未知和未覆盖需求，分别计数。

[[TODO: coverage]]

<!-- ipd-section:conclusion -->
## 结论与待决事项

仅按实际证据提出结论；人类批准由正式 Review 记录。

[[TODO: conclusion]]

<!-- ipd-section:records -->
## 版本化记录

| ID / 版本 | 来源 / 判据 | 结果 / 处置 | 证据 / 决定引用 |
| --- | --- | --- | --- |
| [[TODO: id]] | [[TODO: criterion]] | [[TODO: unknown]] | [[TODO: evidence]] |

