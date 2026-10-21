---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'interface_spec'
template_id: 'ipd-starter.interface_spec'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 接口设计说明 — {{title}}

> 草稿。请用项目事实填写所有 [[TODO: ...]]，不得编造结果或批准。

<!-- ipd-section:identity -->
## 接口标识与两端角色

写明独立接口实例键、提供方、使用方及关联 AR 精确版本。

[[TODO: identity]]

<!-- ipd-section:contract -->
## 协议与数据契约

定义操作、字段、类型、单位、范围、必填性和示例。

[[TODO: contract]]

| 操作 / 字段 | 方向 | 类型 / 格式 | 单位 / 范围 | 必填 / 默认值 | 兼容性 |
| --- | --- | --- | --- | --- | --- |
| [[TODO: contract-1]] | [[TODO: contract-2]] | [[TODO: contract-3]] | [[TODO: contract-4]] | [[TODO: contract-5]] | [[TODO: contract-6]] |

<!-- ipd-section:timing -->
## 时序与状态

说明调用顺序、握手、超时、幂等、并发和性能边界。

[[TODO: timing]]

<!-- ipd-section:errors -->
## 错误、安全与兼容性

列出错误码、重试规则、认证授权、版本协商和兼容策略。

[[TODO: errors]]

<!-- ipd-section:verification -->
## 接口验证与未决问题

记录双方测试、异常用例、判据、证据和未决问题。

[[TODO: verification]]

<!-- ipd-section:records -->
## 版本化记录

| ID / 版本 | 来源 / 判据 | 结果 / 处置 | 证据 / 决定引用 |
| --- | --- | --- | --- |
| [[TODO: id]] | [[TODO: criterion]] | [[TODO: unknown]] | [[TODO: evidence]] |

