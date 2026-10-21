---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'sr_spec'
template_id: 'ipd-starter.sr_spec'
template_version: '1.1.0'
template_sha256: '{{template_sha256}}'
locale: 'zh-CN'
scope: '{{scope}}'
---

# SR 系统需求管理表 — {{title}}

> 草稿。这是一份覆盖多条需求的管理表，不是一条需求一份文件。两行仅演示填写与合并方式，可按本轮范围增删。不得编造结果或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表范围与输入基线：[[TODO: register_scope_and_input_versions]]

一行一条 SR；精确引用上层 IR 版本。将用户场景转换成可验证的系统行为、性能边界及模块分配。系统验证方法与判据须包含判据 ID、条件及预期值；模块测试不能自动代替系统级验证。派生 SR 须引用登记的派生理由，不能伪造上层关系。

使用 HTML `rowspan` 在 Markdown 中合并共享单元格；增删行时同步调整跨度。每条需求的 ID / 版本不得合并，合并不得掩盖不同的判据和责任。保留列标识 `data-ipd-column`。

表中每个精确需求引用须与本实例元数据的 `requirements` 清单逐条对应。`.ipd/requirements.yaml` 保存规范需求事实；修改本表不自动变更需求、分解状态、验证结果或批准记录。

<!-- ipd-section:register -->
## 需求管理表

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">SR ID / 版本</th>
<th data-ipd-column="parent">上层 IR 精确版本</th>
<th data-ipd-column="scenario_scope">需求场景、触发与异常</th>
<th data-ipd-column="system_behavior">系统行为与输出</th>
<th data-ipd-column="measures_limits">量化指标与边界条件</th>
<th data-ipd-column="interfaces_constraints">接口、约束与非功能要求</th>
<th data-ipd-column="module_allocation">模块分配与协作责任</th>
<th data-ipd-column="verification">系统验证方法与判据</th>
<th data-ipd-column="priority_owner">优先级、理由与责任人</th>
<th data-ipd-column="increment_status">增量、成熟度与延期范围</th>
<th data-ipd-column="child_ar">AR 精确版本与分配缺口</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: parent_shared]]</td>
<td rowspan="2">[[TODO: scenario_scope_shared]]</td>
<td>[[TODO: system_behavior_1]]</td>
<td>[[TODO: measures_limits_1]]</td>
<td>[[TODO: interfaces_constraints_1]]</td>
<td>[[TODO: module_allocation_1]]</td>
<td>[[TODO: verification_1]]</td>
<td>[[TODO: priority_owner_1]]</td>
<td>[[TODO: increment_status_1]]</td>
<td>[[TODO: child_ar_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: system_behavior_2]]</td>
<td>[[TODO: measures_limits_2]]</td>
<td>[[TODO: interfaces_constraints_2]]</td>
<td>[[TODO: module_allocation_2]]</td>
<td>[[TODO: verification_2]]</td>
<td>[[TODO: priority_owner_2]]</td>
<td>[[TODO: increment_status_2]]</td>
<td>[[TODO: child_ar_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

对照本轮 IR 检查 SR 覆盖、场景遗漏与冲突；记录模块分配理由、跨模块接口及 AR 分配缺口。不能以表格行数代替覆盖分析。

[[TODO: coverage_changes_and_open_items]]

不适用字段须写明理由；待决项须记录责任人和计划。共享内容只适用于对应合并的行。

