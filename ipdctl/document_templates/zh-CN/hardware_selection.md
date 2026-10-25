---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'hardware_selection'
template_id: 'ipd-starter.hardware_selection'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 硬件选型依据 — {{title}}

遵循已审查的阶段计划，依据真实事实填写；模板完成不代表批准。

<!-- ipd-section:constraints -->
## 从需求形成选型约束

以上层精确需求、工作条件、接口和预算为输入，先区分必需边界与假设，再比较器件。

[[TODO: selection_constraints]]

<!-- ipd-section:comparison -->
## 比较候选方案的证据

记录候选型号/版本、数据手册或实验来源及摘要。在实际适用条件下比较相关边界，区分测量事实、规格和估算。

[[TODO: candidate_evidence]]

<!-- ipd-section:decision -->
## 论证所选方案

给出计算、取舍、余量、接口与风险，明确此材料支撑哪些 IR→SR 或 SR→AR 结论并关联全部使用单元。选型完成不等于需求已批准。

[[TODO: selection_argument]]

<!-- ipd-section:validation -->
## 说明验证与后续工作

引用已有原型实际证据，列出不确定性、责任人和验证计划；未执行检查保持未执行。

[[TODO: selection_validation]]
