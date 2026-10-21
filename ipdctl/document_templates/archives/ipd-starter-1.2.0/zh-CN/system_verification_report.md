---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'system_verification_report'
template_id: 'ipd-starter.system_verification_report'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 系统验证报告 — {{title}}

> 草稿。请用项目事实填写所有 [[TODO: ...]]，不得编造结果或批准。

<!-- ipd-section:subject -->
## 系统与需求基线

标明 SR 精确版本、集成系统版本及代表性配置。

[[TODO: subject]]

<!-- ipd-section:results -->
## 系统指标与边界结果

记录系统测量值、单位、容差、负载、环境和判定。

[[TODO: results]]

| SR 版本 / 判据 | 配置 / 负载 | 实测值 / 单位 | 限值 / 容差 | 判定 | 证据摘要 |
| --- | --- | --- | --- | --- | --- |
| [[TODO: results-1]] | [[TODO: results-2]] | [[TODO: results-3]] | [[TODO: results-4]] | [[TODO: results-5]] | [[TODO: results-6]] |

<!-- ipd-section:integration -->
## 集成与回归覆盖

说明跨模块行为、接口、非功能指标与回归覆盖。

[[TODO: integration]]

<!-- ipd-section:deviations -->
## 偏差、风险与证据

列出失败、跳过、未知、缺陷及精确证据指纹。

[[TODO: deviations]]

<!-- ipd-section:conclusion -->
## 结论与适用限制

不得仅汇总 AR 通过率宣告系统验证通过。

[[TODO: conclusion]]

<!-- ipd-section:records -->
## 版本化记录

| ID / 版本 | 来源 / 判据 | 结果 / 处置 | 证据 / 决定引用 |
| --- | --- | --- | --- |
| [[TODO: id]] | [[TODO: criterion]] | [[TODO: unknown]] | [[TODO: evidence]] |

