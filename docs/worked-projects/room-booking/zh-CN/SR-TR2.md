---
instance_id: 'room-sr-tr2-zh-cn'
increment: 'mvp'
requirements: 'sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1'
owner: 'demo-doc-owner'
document_type: 'sr_spec'
template_id: 'ipd-starter.sr_spec'
template_version: '1.1.1'
template_sha256: '9087bd24906e3e4ea277b5a870b90d11ecdd427e4036ca06d6a8191e4f17e93e'
locale: 'zh-CN'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# SR 系统需求管理表 — 离线单会议室预约器


> 已填写的合成教学表，文档修订 1；TR2 完成时点快照。表内教学编号不代表真实治理受理或批准。

<!-- ipd-section:guidance -->
## 填写口径与基线

本表输入为 [BRIEF@1](source-brief.md)、[教学登记 catalog@1](../catalog.json) 与 [TR2 总体文档](TR2.md)。`requirements` 与本表所有行完全对应；一个 Owner 为 demo-doc-owner（教学角色文本，不是认证身份）。后续版本不改写本快照。

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
<td>sr-01@1</td>
<td rowspan="2">ir-01@1</td>
<td>SC-1; <a href="TR2.md#d-sr-01">D-SR-01</a></td>
<td>系统只接受 HH:MM 格式、真实时钟值且满足 08:00≤start&lt;end≤18:00、端点均在 15 分钟网格上的预约。</td>
<td>将 SC-1 的输入转为距午夜分钟 m=60h+min。开放容量=(18−8)×60=600 分钟，共 600/15=40 格；合法端点为 480+15k，k=0…40，且开始端点小于结束端点。格式、时钟值与业务窗口须分层检查。</td>
<td>使用整数分钟避免浮点边界；09:20 虽是时钟值，仍因不在网格上被拒绝。</td>
<td>validation</td>
<td>test / C-SR-01 / V-SR-01</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
<tr>
<td>sr-02@1</td>
<td>SC-1; <a href="TR2.md#d-sr-02">D-SR-02</a></td>
<td>合法且无冲突的请求应创建一条有效预约，返回本进程内不复用的 ID、起止时间和时长；拒绝不得改变有效列表或消耗 ID。</td>
<td>用户必须能把确认与后续取消对象对应，所以确认含稳定 ID 和输入窗口；仅返回成功标志不够。先检查再写入，避免错误路径留下预约或跳过编号。</td>
<td>递增编号只保证本进程唯一；不宣称跨重启唯一或磁盘事务原子性。</td>
<td>ledger</td>
<td>test / C-SR-02 / V-SR-02</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
<tr>
<td>sr-03@1</td>
<td rowspan="2">ir-02@1</td>
<td>SC-2; <a href="TR2.md#d-sr-03">D-SR-03</a></td>
<td>按半开区间 [start,end) 判断冲突；相邻端点允许，任意正长度重叠拒绝且原列表不变。</td>
<td>两段不相交当且仅当 b≤c 或 d≤a；取反得到 a&lt;d 且 c&lt;b。用严格小于才能使 [08:00,09:00) 与 [09:00,09:30) 相邻而不重叠；包含、被包含和相同区间仍冲突。</td>
<td>扫描当前有效预约，复杂度 O(n)；本例最多 40 条正长度预约，无需区间树。</td>
<td>ledger</td>
<td>test / C-SR-03 / V-SR-03</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
<tr>
<td>sr-04@1</td>
<td>SC-2; <a href="TR2.md#d-sr-04">D-SR-04</a></td>
<td>取消已存在 ID 应移除其有效预约并释放时段；未知或重复取消返回 NOT_FOUND，不影响其他预约且旧 ID 不再复用。</td>
<td>释放意味着该条记录不再参与冲突扫描；立即以相同窗口重新创建必须成功。若复用旧 ID，延迟到达的重复取消可能误删新预约，因此编号在取消后也只能继续递增。</td>
<td>未知取消明确报错，不把重试说成已再次取消；不设计分布式幂等协议。</td>
<td>ledger</td>
<td>test / C-SR-04 / V-SR-04</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
<tr>
<td>sr-05@1</td>
<td rowspan="2">ir-03@1</td>
<td>SC-3; <a href="TR2.md#d-sr-05">D-SR-05</a></td>
<td>日程只列有效预约，按开始分钟、结束分钟、ID 排序，输出标准 HH:MM 及时长；修改返回数据不得改变系统状态。</td>
<td>SC-3 可以先预订晚会议再订早会议，故创建顺序不等于日程顺序。每条输出来自当前有效集；返回新字典而不暴露内部对象，使查看操作保持只读。</td>
<td>稳定排序规则显式声明；单房间无重叠时同开始时间不会共存，但次级键使格式确定。</td>
<td>presentation</td>
<td>test / C-SR-05 / V-SR-05</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
<tr>
<td>sr-06@1</td>
<td>SC-3; <a href="TR2.md#d-sr-06">D-SR-06</a></td>
<td>以 600 分钟为固定分母，计算有效预约的占用/空闲分钟、15 分钟格数及一位小数的利用率；取消后即时重算。</td>
<td>SR-03 保证有效区间不重叠，所以并集长度=Σ(end−start)。两段 08:00—09:00 与 09:30—10:30 共 60+60=120 分钟，空闲 480，已用格 8，空闲格 32，利用率 120/600×100=20.0%。</td>
<td>每格占比 15/600×100=2.5%，一位小数足够精确；不以当天最早/最晚会议跨度作分母。；SR-06 共享 SR-03 不重叠约束</td>
<td>metrics</td>
<td>test / C-SR-06 / V-SR-06</td>
<td>high / demo-systems</td>
<td>mvp；定义完成；验证待TR4</td>
<td>AR尚未形成；demo-dev在TR3分配</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## 变更、覆盖与待决事项

本快照包含 6 条 SR，无重复 ID、缺行或待填占位。背景或父版本的合并不合并 ID、判据和责任。 六条SR覆盖三条IR；此时AR尚未形成，后续分配见TR3第5章。
