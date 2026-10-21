---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'tr2_scenarios_allocation'
template_id: 'ipd-starter.tr2_scenarios_allocation'
template_version: '0.1.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# TR2 需求场景分析与模块分配（讨论稿） — {{title}}

> 讨论稿 0.1.0。按项目提出的 TR1—TR4 阶段口径编排，供共同补充；不是华为原版模板，也不是现有六 Phase / TR-DCP 门禁的新定义。请用真实项目内容替换占位，不得编造结论、结果或批准。

<!-- ipd-section:baseline -->
## 文档范围与 TR1 输入基线

引用 TR1 分析文档、IR 管理表 / 规范需求的精确版本及已接受决定。列明当前增量、发生的变更和未关闭事项。

[[TODO: baseline]]

<!-- ipd-section:scenarios -->
## 需求场景与系统边界分析

按场景 ID 说明参与者、前置条件、触发、正常 / 异常流程、输入输出及外部系统。分析跨场景约束和用户目标，不在每条 SR 中重复共享叙述。

[[TODO: scenarios]]

<!-- ipd-section:sr -->
## IR→SR 分解与系统需求管理表

引用配套 SR 表和上层 IR 精确版本，解释覆盖、派生需求理由、冲突及遗漏。分析系统行为、性能边界、接口和质量目标；逐条规格写入 SR 表。

[[TODO: sr]]

<!-- ipd-section:allocation -->
## 模块划分、职责与需求分配

给出候选模块边界、软硬件分工、SR 分配和协作责任，解释方案取舍、跨模块依赖、资源 / 性能预算。未确定的分配须保留问题和责任人。

[[TODO: allocation]]

| 模块 | SR 精确版本 | 职责与边界 | 协作模块 / 接口 | 预算 / 分配理由 | 缺口 / 责任人 |
| --- | --- | --- | --- | --- | --- |
| [[TODO: module]] | [[TODO: sr_versions]] | [[TODO: responsibility_boundary]] | [[TODO: collaboration_interfaces]] | [[TODO: budget_rationale]] | [[TODO: gaps_owner]] |

<!-- ipd-section:interfaces -->
## 系统接口与约束

说明模块间及外部接口的责任、数据 / 控制流、约束和异常响应；引用独立接口文档的版本。若需要硬件选型，说明其对场景和分配的影响。

[[TODO: interfaces]]

<!-- ipd-section:verification -->
## 系统验证与用户确认策划

建立 SR 判据与系统验证方法 / 环境的对应关系，并保留 IR 用户验收计划。列出组合场景、性能边界及尚需试验的假设，执行结果留待实际验证。

[[TODO: verification]]

<!-- ipd-section:deliverables -->
## 交付件、风险与待决清单

建议最小组合：本总体分析文档 + SR 管理表；IR 基线作为输入。按需附场景分析、分配矩阵、系统验证计划、接口或硬件选型文档，并列明缺口和责任。

[[TODO: deliverables]]

| 类型 / 是否必需（草案） | 文档 ID / 路径 | 精确版本 / 摘要 | 覆盖需求 / 范围 | 责任人 | 状态 / 缺口 |
| --- | --- | --- | --- | --- | --- |
| [[TODO: artifact_type]] | [[TODO: artifact_path]] | [[TODO: artifact_version]] | [[TODO: covered_requirements]] | [[TODO: artifact_owner]] | [[TODO: artifact_status]] |

<!-- ipd-section:review -->
## 评审输入摘要与 TR3 设计入口

汇总 IR→SR 覆盖、模块分配成熟度和设计前待决事项；记录拟进入概要设计的范围，引用实际评审决定。不要将 SR 表完整等同于设计完成。

[[TODO: review]]

