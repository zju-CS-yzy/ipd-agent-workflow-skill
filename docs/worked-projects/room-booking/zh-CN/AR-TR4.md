---
instance_id: 'room-ar-tr4-zh-cn'
increment: 'mvp'
requirements: 'ar-01@1, ar-02@1, ar-03@1, ar-04@1, ar-05@1, ar-06@1, ar-07@1, ar-08@1, ar-09@1, ar-10@1, ar-11@1, ar-12@1'
owner: 'demo-doc-owner'
document_type: 'ar_spec'
template_id: 'ipd-starter.ar_spec'
template_version: '1.1.1'
template_sha256: '22f419fc4c4e690a6f7e8f86cef4d8931376cb9db3cb43bc7e3c0683376dc5f6'
locale: 'zh-CN'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# AR 分配需求管理表 — 离线单会议室预约器


> 已填写的合成教学表，文档修订 1；TR4 完成时点快照。表内教学编号不代表真实治理受理或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表输入为 [BRIEF@1](source-brief.md)、[教学登记 catalog@1](../catalog.json) 与 [TR4 总体文档](TR4.md)。`requirements` 与本表所有行完全对应；一个 Owner 为 demo-doc-owner（教学角色文本，不是认证身份）。后续版本不改写本快照。

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
<td>ar-01@1</td>
<td rowspan="2">sr-01@1</td>
<td>validation; SC-1</td>
<td>demo-dev; 解析器只判断时钟合法性，开放时段交由 AR-02，避免职责混杂。</td>
<td>解析器将两位 HH:MM 且 0≤h≤23、0≤m≤59 转为 60h+m；其他输入返回明确格式或时钟错误。</td>
<td>SR-01 的业务比较需先得到统一整数。08:00=480、09:15=555、18:00=1080；9:00 缺前导零，09:75 分钟越界，二者不能被宽松转换为预约。</td>
<td><a href="TR3.md#d-ar-01">D-AR-01</a>; <a href="TR4.md#impl-ar-01">详细设计/实现 E1</a>; booking.py::parse_time</td>
<td>test / C-AR-01 / V-AR-01</td>
<td>V-AR-01 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-02@1</td>
<td>validation; SC-1</td>
<td>demo-dev; 两端校验保证最短正长度自动为 15 分钟，无须独立浮点时长阈值。</td>
<td>窗口校验器强制 480≤start&lt;end≤1080，且 (start−480)%15=(end−480)%15=0，失败不得进入创建。</td>
<td>SR-01 直接给出窗口与网格。17:45=1065，18:00=1080，持续 15 分钟有效；零长度、07:45、18:15 越界或 09:20 脱网格均拒绝。</td>
<td><a href="TR3.md#d-ar-02">D-AR-02</a>; <a href="TR4.md#impl-ar-02">详细设计/实现 E1</a>; booking.py::validate_window</td>
<td>test / C-AR-02 / V-AR-02</td>
<td>V-AR-02 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-03@1</td>
<td rowspan="2">sr-02@1</td>
<td>ledger; SC-1</td>
<td>demo-dev; 编号至少三位，超过 999 可增长；本例最多 40 个同时有效预约，但允许多次取消和再创建。</td>
<td>台账仅在创建成功后分配递增 B001、B002…，拒绝与取消均不推进或回退编号。</td>
<td>成功次数 k 对应下一编号 k+1；拒绝不增加成功次数，取消不减少历史成功次数，因此确认可稳定定位且不复用。</td>
<td><a href="TR3.md#d-ar-03">D-AR-03</a>; <a href="TR4.md#impl-ar-03">详细设计/实现 E1</a>; booking.py::Calendar.book</td>
<td>test / C-AR-03 / V-AR-03</td>
<td>V-AR-03 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-04@1</td>
<td>ledger; SC-1</td>
<td>demo-dev; 只承诺预期输入错误下的单进程行为，不声称内存耗尽或断电后的持久事务。</td>
<td>完成输入与冲突预检后只新增一条预约，返回 ID、标准时间与 end−start 分钟；拒绝路径不修改台账。</td>
<td>先校验再创建保证被拒绝请求没有部分有效记录。08:00—09:00 的确认必须是 B001、08:00、09:00、60，且日程中恰有同一条。</td>
<td><a href="TR3.md#d-ar-04">D-AR-04</a>; <a href="TR4.md#impl-ar-04">详细设计/实现 E1</a>; booking.py::Calendar.book/Booking.record</td>
<td>test / C-AR-04 / V-AR-04</td>
<td>V-AR-04 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-05@1</td>
<td rowspan="2">sr-03@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; 使用严格小于而非小于等于；后者会错误拒绝相邻预约。</td>
<td>冲突谓词对已校验正长度区间返回 start&lt;other_end 且 other_start&lt;end，边界相等不冲突。</td>
<td>将 SR-03 的区间论证直接落实为纯函数。480—540 对 540—555 为假；对 525—555、相同区间、内部区间及覆盖区间为真；对 465—480 为假。</td>
<td><a href="TR3.md#d-ar-05">D-AR-05</a>; <a href="TR4.md#impl-ar-05">详细设计/实现 E1</a>; booking.py::overlaps</td>
<td>test / C-AR-05 / V-AR-05</td>
<td>V-AR-05 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-06@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; 最多 40 条有效记录，线性扫描可解释且足够；不把此结论推广到大型并发服务。</td>
<td>创建前检查全部有效预约，有任意冲突即返回 CONFLICT，且有效列表和下一成功 ID 不变。</td>
<td>只检查某一条会漏掉其他占用区间；扫描所有当前有效记录后才提交。已有 B001 时拒绝重叠请求，下次合法请求应为 B002 而非 B003。</td>
<td><a href="TR3.md#d-ar-06">D-AR-06</a>; <a href="TR4.md#impl-ar-06">详细设计/实现 E1</a>; booking.py::Calendar.book</td>
<td>test / C-AR-06 / V-AR-06</td>
<td>V-AR-06 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-07@1</td>
<td rowspan="2">sr-04@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; 以 ID 定位而非时间模糊匹配，防止误删相邻预约。</td>
<td>取消只删除存在的目标 ID，返回已取消确认；不存在的 ID 返回 NOT_FOUND，其他记录不变。</td>
<td>SR-04 的释放对应有效集合减去该 ID。删除 B001 后有效集为空；取消 missing 仍为空，明确错误避免误导。</td>
<td><a href="TR3.md#d-ar-07">D-AR-07</a>; <a href="TR4.md#impl-ar-07">详细设计/实现 E1</a>; booking.py::Calendar.cancel</td>
<td>test / C-AR-07 / V-AR-07</td>
<td>V-AR-07 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-08@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; 由单调编号与有效集组合实现，无需新增另一套取消状态数据库。</td>
<td>取消后同窗口可用新 ID 再预约；重复取消旧 ID 不得删除新预约。</td>
<td>B001 删除后同窗口可建 B002，表明取消已移出冲突集。再次 cancel(B001) 必须 NOT_FOUND 且 B002 保留，联合验证释放和不复用。</td>
<td><a href="TR3.md#d-ar-08">D-AR-08</a>; <a href="TR4.md#impl-ar-08">详细设计/实现 E1</a>; booking.py::Calendar.cancel/book</td>
<td>test / C-AR-08 / V-AR-08</td>
<td>V-AR-08 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-09@1</td>
<td rowspan="2">sr-05@1</td>
<td>presentation; SC-3</td>
<td>demo-dev; n≤40，O(n log n) 排序可接受；取消项自然不在输入集合中。</td>
<td>日程从当前有效集按 (start,end,id) 升序生成；创建顺序不影响显示顺序。</td>
<td>先建 09:30—10:30 为 B001，再建 08:00—09:00 为 B002，预期顺序为 B002、B001，不能直接遍历插入顺序。</td>
<td><a href="TR3.md#d-ar-09">D-AR-09</a>; <a href="TR4.md#impl-ar-09">详细设计/实现 E1</a>; booking.py::Calendar.agenda</td>
<td>test / C-AR-09 / V-AR-09</td>
<td>V-AR-09 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-10@1</td>
<td>presentation; SC-3</td>
<td>demo-dev; 用不可变记录和新输出对象隔离调用者，避免复制整个服务状态。</td>
<td>输出标准 HH:MM、整数时长和新字典；修改确认或日程列表不得影响内部预约。</td>
<td>分钟 m 输出为 m//60 与 m%60 的两位字符串，时长=end−start。对返回值改写 00:00 或追加 ghost 后，再读取仍为原预约，证明只读边界。</td>
<td><a href="TR3.md#d-ar-10">D-AR-10</a>; <a href="TR4.md#impl-ar-10">详细设计/实现 E1</a>; booking.py::Booking.record/Calendar.agenda</td>
<td>test / C-AR-10 / V-AR-10</td>
<td>V-AR-10 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-11@1</td>
<td rowspan="2">sr-06@1</td>
<td>metrics; SC-3</td>
<td>demo-dev; 显式依赖不重叠不变量；未来若允许重叠必须改为区间并集算法。</td>
<td>对当前有效集累加 end−start 得到占用分钟，空集为零；取消项不得计入。</td>
<td>SR-03 保证不重叠，故可直接求和。两个 60 分钟区间之和为 120；取消其中一项后为 60，而不是把 08:00—10:30 的 150 分钟全部计入。</td>
<td><a href="TR3.md#d-ar-11">D-AR-11</a>; <a href="TR4.md#impl-ar-11">详细设计/实现 E1</a>; booking.py::Calendar.occupied_minutes</td>
<td>test / C-AR-11 / V-AR-11</td>
<td>V-AR-11 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
<tr>
<td>ar-12@1</td>
<td>metrics; SC-3</td>
<td>demo-dev; 使用整数十分位，避免浮点显示误差；600 固定且非零，无空列表除零。</td>
<td>以固定 600 分钟计算 free=600−occupied、used_slots=occupied/15、free_slots=free/15，利用率保留一位小数且不使用不适用分母。</td>
<td>每格为 2.5%，故十分之一百分比单位=occupied×1000/600，是整数，不需舍入。空日为 0/600=0.0%，满日为 600/600=100.0%，120 分钟为 20.0%。</td>
<td><a href="TR3.md#d-ar-12">D-AR-12</a>; <a href="TR4.md#impl-ar-12">详细设计/实现 E1</a>; booking.py::Calendar.summary</td>
<td>test / C-AR-12 / V-AR-12</td>
<td>V-AR-12 / passed (synthetic) / <a href="../evidence/verification.json">E1</a></td>
<td>重跑对应AR、父SR与IR场景；21例</td>
<td>mvp；定义完成；非批准</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

本快照包含 12 条 AR，无重复 ID、缺行或待填占位。背景或父版本的合并不合并 ID、判据和责任。 12条AR均有实际软件用例，6条SR和3条IR场景另行执行；人类验收和治理批准仍未发生。
