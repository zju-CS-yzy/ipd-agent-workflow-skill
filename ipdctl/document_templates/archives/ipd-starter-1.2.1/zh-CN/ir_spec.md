---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ir_spec'
template_id: 'ipd-starter.ir_spec'
template_version: '1.1.1'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# IR 原始需求管理表 — {{title}}

> 草稿。这是一份覆盖多条需求的管理表，不是一条需求一份文件。两行仅演示填写与合并方式，可按本轮范围增删。不得编造结果或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表范围与输入基线：[[TODO: register_scope_and_input_versions]]

一行一条 IR；ID / 版本填写 `ir-id@1` 形式的精确引用。验收意图描述用户在何种场景下达到什么目标，并引用登记的判据 ID。共享背景和用户场景可以跨行合并；不同的验收目标、责任人和交付承诺应分别保留。

使用 HTML `rowspan` 在 Markdown 中合并共享单元格；增删行时同步调整跨度。每条需求的 ID / 版本不得合并，合并不得掩盖不同的判据和责任。保留列标识 `data-ipd-column`。

表中每个精确需求引用须与本实例元数据的 `requirements` 清单逐条对应。`.ipd/requirements.yaml` 保存规范需求事实；修改本表不自动变更需求、分解状态、验证结果或批准记录。

阶段尚未形成的下层需求、设计、实现或结果，填写“未形成 / 未执行”、责任人与计划阶段，不预填未来 ID、版本或通过结论。为分解论证设置唯一记录编号：SR 可在场景 / 约束单元格回指 TR2 论证，AR 可在设计引用单元格回指 TR3 论证。后续补充内容时保留本阶段快照或精确文档版本；需求内容未改不等于文档修订未改。

<!-- ipd-section:register -->
## 需求管理表

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">IR ID / 版本</th>
<th data-ipd-column="shared_context">来源与共享背景</th>
<th data-ipd-column="scenario_scope">用户场景与范围</th>
<th data-ipd-column="statement">原始需求陈述</th>
<th data-ipd-column="value">用户价值与目标</th>
<th data-ipd-column="acceptance_intent">验收意图与判据 ID</th>
<th data-ipd-column="priority">优先级与理由</th>
<th data-ipd-column="owner">需求责任人</th>
<th data-ipd-column="increment">承诺增量与延期范围</th>
<th data-ipd-column="decomposition">SR 精确版本与分解状态</th>
<th data-ipd-column="open_questions">约束、风险与待决事项</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: shared_context_shared]]</td>
<td rowspan="2">[[TODO: scenario_scope_shared]]</td>
<td>[[TODO: statement_1]]</td>
<td>[[TODO: value_1]]</td>
<td>[[TODO: acceptance_intent_1]]</td>
<td>[[TODO: priority_1]]</td>
<td>[[TODO: owner_1]]</td>
<td>[[TODO: increment_1]]</td>
<td>[[TODO: decomposition_1]]</td>
<td>[[TODO: open_questions_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: statement_2]]</td>
<td>[[TODO: value_2]]</td>
<td>[[TODO: acceptance_intent_2]]</td>
<td>[[TODO: priority_2]]</td>
<td>[[TODO: owner_2]]</td>
<td>[[TODO: increment_2]]</td>
<td>[[TODO: decomposition_2]]</td>
<td>[[TODO: open_questions_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

核对本轮 IR 是否覆盖原始来源；逐条解释新增、修改、撤回及延期，关联 SR 精确版本。分解尚未完成时写明缺口、责任人与计划；不要把未分解写成已完成。

[[TODO: coverage_changes_and_open_items]]

不适用字段须写明理由；待决项须记录责任人和计划。共享内容只适用于对应合并的行。

