---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'stage_index'
template_id: 'ipd-starter.stage_index'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 阶段范围与成果索引 — {{title}}

遵循已审查的阶段计划，依据真实事实填写；模板完成不代表批准。

<!-- ipd-section:scope -->
## 明确阶段输入与范围

从已接受的上层需求精确版本和本增量承诺判据开始，区分本轮、未来与延期分支。TR1 在尚未形成 IR 时先记录原始来源。本索引初建时可以没有已登记需求，不要求预先存在下游成果。

[[TODO: scope_inputs]]

<!-- ipd-section:products -->
## 规划所需交付件

逐项说明哪些场景分析、实验、架构、接口或选型材料确有必要。记录实例、路径/版本或摘要、Owner、用途、支撑结论及是否必需。共享材料只保留一个规范实例和 Owner，列出全部使用分支。依据已审查的阶段计划安排逐父分解文件与管理表。

[[TODO: work_product_plan]]

<!-- ipd-section:cross_checks -->
## 核对系统整体一致性

检查跨父需求接口、组合预算、共享假设和冲突。系统架构、总体预算等仍有真实的支撑成果；此索引引用其版本与结论，不把各分支详细论证重新拼成一篇长文。

[[TODO: cross_branch_checks]]

<!-- ipd-section:decisions -->
## 汇总阶段结论与缺口

引用各父需求的分解论证、管理表及精确版本，列明未关闭问题。TR4 引用实际实现和已执行验证，包括适用的 SR/IR 检查。区分计划、登记、结构就绪和人类接受；索引填写完成不等于批准。

[[TODO: stage_conclusion]]
