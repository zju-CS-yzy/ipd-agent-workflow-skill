---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ir_decomposition'
template_id: 'ipd-starter.ir_decomposition'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# 单条 IR 的 IR→SR 分解论证 — {{title}}

遵循已审查的阶段计划，依据真实事实填写；模板完成不代表批准。

<!-- ipd-section:parent -->
## 理解本文件唯一的上层 IR

从阶段计划与规范登记取得一条 IR 的精确版本，明确原句、本轮判据、使用者、边界及延期范围。共享 TR1 背景按版本引用，不复制全文。此时 SR 可以尚不存在。

[[TODO: parent_ir]]

<!-- ipd-section:support -->
## 开展场景与支撑事实分析

分析正常、异常和边界场景。对资料、选型、原型和方案假设记录版本/摘要、引用章节、结果、限制，以及它如何支持当前 IR 的分解。共用材料引用同一受管实例，不为各 IR 复制文件。

[[TODO: supporting_analysis]]

<!-- ipd-section:derivation -->
## 在本章逐条形成候选 SR

为每条子需求设置唯一论证编号并重复完整过程：IR 目标→场景与假设→系统职责或量化边界→候选 SR 陈述→验证判据。按适用情况给出单位、公式、数据来源、图例或逻辑论证，说明备选方案与待决项。通过编号计划取得子编号；登记和批准分别办理。

[[TODO: each_sr_derivation]]

<!-- ipd-section:register -->
## 登记并整理 SR 集合

完成论证后登记选定条目，引用其精确 id@version。配套多行 SR 表只填写这些子需求，父列与规范 IR 一致；每行回指对应论证锚点，不能把输入 IR 也当作 SR 行。若结论草稿的覆盖清单扩大，显式将受管实例修订到新文件。

[[TODO: sr_register_reference]]

<!-- ipd-section:coverage -->
## 论证组合覆盖并形成最终结论

说明子需求组合后如何覆盖本 IR 适用的正常、异常与边界判据，列出遗漏、重复、冲突、系统依赖和延期项。必需支撑缺口处理后再定稿。本文件可以提前起草并迭代，阶段最终版本并不自动取得人类批准。

[[TODO: combined_ir_coverage]]
