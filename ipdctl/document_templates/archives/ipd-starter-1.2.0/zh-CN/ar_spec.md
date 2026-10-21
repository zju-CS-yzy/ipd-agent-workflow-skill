---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ar_spec'
template_id: 'ipd-starter.ar_spec'
template_version: '1.1.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# AR 分配需求管理表 — {{title}}

> 草稿。这是一份覆盖多条需求的管理表，不是一条需求一份文件。两行仅演示填写与合并方式，可按本轮范围增删。不得编造结果或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表范围与输入基线：[[TODO: register_scope_and_input_versions]]

一行一条 AR；精确引用上层 SR 版本。TR3 形成分配及概要设计引用，TR4 逐步补充详细设计、实现版本和实际验证证据。尚未实施的内容明确写“未执行”及后续计划；不可填“通过”。判据、实际结果和证据分列管理。

使用 HTML `rowspan` 在 Markdown 中合并共享单元格；增删行时同步调整跨度。每条需求的 ID / 版本不得合并，合并不得掩盖不同的判据和责任。保留列标识 `data-ipd-column`。

表中每个精确需求引用须与本实例元数据的 `requirements` 清单逐条对应。`.ipd/requirements.yaml` 保存规范需求事实；修改本表不自动变更需求、分解状态、验证结果或批准记录。

<!-- ipd-section:register -->
## 需求管理表

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">AR ID / 版本</th>
<th data-ipd-column="parent">上层 SR 精确版本</th>
<th data-ipd-column="assigned_module">分配模块与共享设计背景</th>
<th data-ipd-column="responsibility">责任边界与负责人</th>
<th data-ipd-column="behavior_constraints">模块行为、输入输出与约束</th>
<th data-ipd-column="interfaces_budget">接口、资源预算与异常处理</th>
<th data-ipd-column="design_implementation">概要 / 详细设计与实现版本引用</th>
<th data-ipd-column="verification">模块验证方法、判据 ID 与预期值</th>
<th data-ipd-column="result_evidence">实际结果、证据版本与缺陷</th>
<th data-ipd-column="regression">影响范围与回归范围</th>
<th data-ipd-column="increment_status">增量、成熟度与延期范围</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: parent_shared]]</td>
<td rowspan="2">[[TODO: assigned_module_shared]]</td>
<td>[[TODO: responsibility_1]]</td>
<td>[[TODO: behavior_constraints_1]]</td>
<td>[[TODO: interfaces_budget_1]]</td>
<td>[[TODO: design_implementation_1]]</td>
<td>[[TODO: verification_1]]</td>
<td>[[TODO: result_evidence_1]]</td>
<td>[[TODO: regression_1]]</td>
<td>[[TODO: increment_status_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: responsibility_2]]</td>
<td>[[TODO: behavior_constraints_2]]</td>
<td>[[TODO: interfaces_budget_2]]</td>
<td>[[TODO: design_implementation_2]]</td>
<td>[[TODO: verification_2]]</td>
<td>[[TODO: result_evidence_2]]</td>
<td>[[TODO: regression_2]]</td>
<td>[[TODO: increment_status_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

核对 SR→AR 分配是否完整、责任边界是否冲突；记录设计 / 代码 / 测试版本、缺陷与回归范围。AR 通过不等于 SR 系统验证和 IR 用户验收通过。

[[TODO: coverage_changes_and_open_items]]

不适用字段须写明理由；待决项须记录责任人和计划。共享内容只适用于对应合并的行。

