---
instance_id: 'room-ir-tr1-zh-cn'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1'
owner: 'demo-doc-owner'
document_type: 'ir_spec'
template_id: 'ipd-starter.ir_spec'
template_version: '1.1.1'
template_sha256: 'f0b798c9724e55a2513221105c96441bca1fad42490f4db03588fbc6d0d1cc40'
locale: 'zh-CN'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# IR 原始需求管理表 — 离线单会议室预约器


> 已填写的合成教学表，文档修订 1；TR1 完成时点快照。表内教学编号不代表真实治理受理或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表输入为 [BRIEF@1](source-brief.md)、[教学登记 catalog@1](../catalog.json) 与 [TR1 总体文档](TR1.md)。`requirements` 与本表所有行完全对应；一个 Owner 为 demo-doc-owner（教学角色文本，不是认证身份）。后续版本不改写本快照。

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
<td>ir-01@1</td>
<td rowspan="3">BRIEF@1/U1–U3；同一房间/一天</td>
<td rowspan="3">SC-1/SC-2/SC-3；08:00—18:00，15min</td>
<td>在单日开放时段内，用户可按 15 分钟粒度创建预约并获得明确确认；无效输入必须明确拒绝。</td>
<td>BRIEF@1/U1 要求能预约并知道结果；C1/C2 将范围限定为一间房、08:00—18:00 和 15 分钟粒度。把“能预约”整理为合法输入被确认、非法输入被拒绝两个可观察结果。</td>
<td>C-IR-01；在单日开放时段内，用户可按 15 分钟粒度创建预约并获得明确确认；无效输入必须明确拒绝。</td>
<td>高；MVP必要</td>
<td>demo-systems</td>
<td>mvp; 不含多房间/跨日</td>
<td>尚未分解；demo-systems 在 TR2 形成；<a href="TR1.md#d-ir-01">D-IR-01</a></td>
<td>采用命令/API 演示而非图形界面；不承诺交互耗时或持久保存。</td>
</tr>
<tr>
<td>ir-02@1</td>
<td>有效预约不得重叠，相邻预约允许；用户取消有效预约后可立即重新预约该时段。</td>
<td>BRIEF@1/U2 关心抢占与取消后的可用性。C3 明确相邻边界不冲突，C4 只讨论单进程串行调用，因而目标可分为冲突控制和取消释放两部分。</td>
<td>C-IR-02；有效预约不得重叠，相邻预约允许；用户取消有效预约后可立即重新预约该时段。</td>
<td>高；MVP必要</td>
<td>demo-systems</td>
<td>mvp; 不含多房间/跨日</td>
<td>尚未分解；demo-systems 在 TR2 形成；<a href="TR1.md#d-ir-02">D-IR-02</a></td>
<td>不扩展为并发锁或认证；相邻是否冲突必须在输入中明确，不能由代码猜测。</td>
</tr>
<tr>
<td>ir-03@1</td>
<td>用户可查看按时间排序的有效预约，以及当天已用/空闲分钟数、时段数和利用率。</td>
<td>BRIEF@1/U3 需要安排后续会议。C1 给出固定开放容量；有效列表与利用率分别回答“什么时候空闲”与“用了多少”，不能只显示一个百分数。</td>
<td>C-IR-03；用户可查看按时间排序的有效预约，以及当天已用/空闲分钟数、时段数和利用率。</td>
<td>高；MVP必要</td>
<td>demo-systems</td>
<td>mvp; 不含多房间/跨日</td>
<td>尚未分解；demo-systems 在 TR2 形成；<a href="TR1.md#d-ir-03">D-IR-03</a></td>
<td>只汇总当前进程的一天，不做跨日统计或人员数据分析。</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

本快照包含 3 条 IR，无重复 ID、缺行或待填占位。背景或父版本的合并不合并 ID、判据和责任。 TR1 尚无 SR，不在此快照预填后续版本。后续完整分解见 TR2 第3章。
