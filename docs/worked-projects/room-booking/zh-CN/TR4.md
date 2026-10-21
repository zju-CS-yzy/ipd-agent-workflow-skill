---
instance_id: 'room-tr4-zh-cn'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1, sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1, ar-01@1, ar-02@1, ar-03@1, ar-04@1, ar-05@1, ar-06@1, ar-07@1, ar-08@1, ar-09@1, ar-10@1, ar-11@1, ar-12@1'
owner: 'demo-doc-owner'
document_type: 'tr4_detail_implementation_test'
template_id: 'ipd-starter.tr4_detail_implementation_test'
template_version: '0.2.1'
template_sha256: '63059b2ad163898d1a229bb0e7bfcf41c6df2de2e6af3a4abcc9a98631e189d3'
locale: 'zh-CN'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# TR4 详细设计、实现与测试验收（讨论稿） — 离线单会议室预约器

> 已填写的合成教学示例，文档修订 1。需求编号来自本例 catalog.json，不声明已在真实 IPD 项目受理；无真实用户批准。各阶段文件是其完成时点快照，后续产物只在后续阶段出现。

<!-- ipd-section:baseline -->
## 1. 明确交付范围与设计输入

输入是 [TR3@doc1](TR3.md)、[AR-TR3@doc1](AR-TR3.md)及SR/IR阶段快照。21条需求内容均为@1，未用代码结果倒改需求。实际实现IMPL-1为 [booking.py](../implementation/booking.py)，SHA-256 `4c4dabae0c4b3e6028b8aecf83a04afd1efbc2badd39e8adfd4cf6609ef3afc4`。

环境与执行时间、两份源码摘要均保存在 [E1](../evidence/verification.json)。E1是实际运行的软件合成夹具证据，不是用户验收签字或IPD批准。

<!-- ipd-section:detail -->
## 2. 逐项完成 AR 对应的详细设计

<a id="impl-ar-01"></a>
### IMPL-AR-01 · ar-01@1

**具体设计：** SR-01 的业务比较需先得到统一整数。08:00=480、09:15=555、18:00=1080；9:00 缺前导零，09:75 分钟越界，二者不能被宽松转换为预约。

**算法与接口定位：** [booking.py](../implementation/booking.py)::parse_time

**满足理由与边界：** 解析器只判断时钟合法性，开放时段交由 AR-02，避免职责混杂。 预期来自 C-AR-01，实际用例 V-AR-01 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-02"></a>
### IMPL-AR-02 · ar-02@1

**具体设计：** SR-01 直接给出窗口与网格。17:45=1065，18:00=1080，持续 15 分钟有效；零长度、07:45、18:15 越界或 09:20 脱网格均拒绝。

**算法与接口定位：** [booking.py](../implementation/booking.py)::validate_window

**满足理由与边界：** 两端校验保证最短正长度自动为 15 分钟，无须独立浮点时长阈值。 预期来自 C-AR-02，实际用例 V-AR-02 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-03"></a>
### IMPL-AR-03 · ar-03@1

**具体设计：** 成功次数 k 对应下一编号 k+1；拒绝不增加成功次数，取消不减少历史成功次数，因此确认可稳定定位且不复用。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.book

**满足理由与边界：** 编号至少三位，超过 999 可增长；本例最多 40 个同时有效预约，但允许多次取消和再创建。 预期来自 C-AR-03，实际用例 V-AR-03 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-04"></a>
### IMPL-AR-04 · ar-04@1

**具体设计：** 先校验再创建保证被拒绝请求没有部分有效记录。08:00—09:00 的确认必须是 B001、08:00、09:00、60，且日程中恰有同一条。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.book/Booking.record

**满足理由与边界：** 只承诺预期输入错误下的单进程行为，不声称内存耗尽或断电后的持久事务。 预期来自 C-AR-04，实际用例 V-AR-04 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-05"></a>
### IMPL-AR-05 · ar-05@1

**具体设计：** 将 SR-03 的区间论证直接落实为纯函数。480—540 对 540—555 为假；对 525—555、相同区间、内部区间及覆盖区间为真；对 465—480 为假。

**算法与接口定位：** [booking.py](../implementation/booking.py)::overlaps

**满足理由与边界：** 使用严格小于而非小于等于；后者会错误拒绝相邻预约。 预期来自 C-AR-05，实际用例 V-AR-05 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-06"></a>
### IMPL-AR-06 · ar-06@1

**具体设计：** 只检查某一条会漏掉其他占用区间；扫描所有当前有效记录后才提交。已有 B001 时拒绝重叠请求，下次合法请求应为 B002 而非 B003。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.book

**满足理由与边界：** 最多 40 条有效记录，线性扫描可解释且足够；不把此结论推广到大型并发服务。 预期来自 C-AR-06，实际用例 V-AR-06 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-07"></a>
### IMPL-AR-07 · ar-07@1

**具体设计：** SR-04 的释放对应有效集合减去该 ID。删除 B001 后有效集为空；取消 missing 仍为空，明确错误避免误导。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.cancel

**满足理由与边界：** 以 ID 定位而非时间模糊匹配，防止误删相邻预约。 预期来自 C-AR-07，实际用例 V-AR-07 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-08"></a>
### IMPL-AR-08 · ar-08@1

**具体设计：** B001 删除后同窗口可建 B002，表明取消已移出冲突集。再次 cancel(B001) 必须 NOT_FOUND 且 B002 保留，联合验证释放和不复用。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.cancel/book

**满足理由与边界：** 由单调编号与有效集组合实现，无需新增另一套取消状态数据库。 预期来自 C-AR-08，实际用例 V-AR-08 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-09"></a>
### IMPL-AR-09 · ar-09@1

**具体设计：** 先建 09:30—10:30 为 B001，再建 08:00—09:00 为 B002，预期顺序为 B002、B001，不能直接遍历插入顺序。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.agenda

**满足理由与边界：** n≤40，O(n log n) 排序可接受；取消项自然不在输入集合中。 预期来自 C-AR-09，实际用例 V-AR-09 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-10"></a>
### IMPL-AR-10 · ar-10@1

**具体设计：** 分钟 m 输出为 m//60 与 m%60 的两位字符串，时长=end−start。对返回值改写 00:00 或追加 ghost 后，再读取仍为原预约，证明只读边界。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Booking.record/Calendar.agenda

**满足理由与边界：** 用不可变记录和新输出对象隔离调用者，避免复制整个服务状态。 预期来自 C-AR-10，实际用例 V-AR-10 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-11"></a>
### IMPL-AR-11 · ar-11@1

**具体设计：** SR-03 保证不重叠，故可直接求和。两个 60 分钟区间之和为 120；取消其中一项后为 60，而不是把 08:00—10:30 的 150 分钟全部计入。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.occupied_minutes

**满足理由与边界：** 显式依赖不重叠不变量；未来若允许重叠必须改为区间并集算法。 预期来自 C-AR-11，实际用例 V-AR-11 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<a id="impl-ar-12"></a>
### IMPL-AR-12 · ar-12@1

**具体设计：** 每格为 2.5%，故十分之一百分比单位=occupied×1000/600，是整数，不需舍入。空日为 0/600=0.0%，满日为 600/600=100.0%，120 分钟为 20.0%。

**算法与接口定位：** [booking.py](../implementation/booking.py)::Calendar.summary

**满足理由与边界：** 使用整数十分位，避免浮点显示误差；600 固定且非零，无空列表除零。 预期来自 C-AR-12，实际用例 V-AR-12 见第4章；设计位置内容版本为IMPL-1，摘要见第1章。

<!-- ipd-section:implementation -->
## 3. 记录实际实现、构建与集成

实际代码包含parse_time、validate_window、overlaps、不可变Booking和Calendar。源码只使用标准库，无网络、数据库或界面。复现命令从本目录运行：

```console
python ../implementation/verify_demo.py
```

默认输出JSON不改写保存证据；传 --output 到指定临时文件可保存新运行。当前E1实际21/21通过；不是构建工具安装或跨平台资格结论。

| 模块 / AR 版本 | 详细设计版本 | 实现版本 / 配置 | 构建环境与结果 | 集成状态 | 偏差 / 决定引用 |
| --- | --- | --- | --- | --- | --- |
| validation / ar-01@1 | IMPL-AR-01 / doc1 | IMPL-1 / parse_time | Python 3.12.14 / V-AR-01 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| validation / ar-02@1 | IMPL-AR-02 / doc1 | IMPL-1 / validate_window | Python 3.12.14 / V-AR-02 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-03@1 | IMPL-AR-03 / doc1 | IMPL-1 / Calendar.book | Python 3.12.14 / V-AR-03 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-04@1 | IMPL-AR-04 / doc1 | IMPL-1 / Calendar.book/Booking.record | Python 3.12.14 / V-AR-04 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-05@1 | IMPL-AR-05 / doc1 | IMPL-1 / overlaps | Python 3.12.14 / V-AR-05 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-06@1 | IMPL-AR-06 / doc1 | IMPL-1 / Calendar.book | Python 3.12.14 / V-AR-06 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-07@1 | IMPL-AR-07 / doc1 | IMPL-1 / Calendar.cancel | Python 3.12.14 / V-AR-07 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| ledger / ar-08@1 | IMPL-AR-08 / doc1 | IMPL-1 / Calendar.cancel/book | Python 3.12.14 / V-AR-08 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| presentation / ar-09@1 | IMPL-AR-09 / doc1 | IMPL-1 / Calendar.agenda | Python 3.12.14 / V-AR-09 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| presentation / ar-10@1 | IMPL-AR-10 / doc1 | IMPL-1 / Booking.record/Calendar.agenda | Python 3.12.14 / V-AR-10 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| metrics / ar-11@1 | IMPL-AR-11 / doc1 | IMPL-1 / Calendar.occupied_minutes | Python 3.12.14 / V-AR-11 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |
| metrics / ar-12@1 | IMPL-AR-12 / doc1 | IMPL-1 / Calendar.summary | Python 3.12.14 / V-AR-12 | 实际调用通过（合成输入） | 无观察到的偏差；无批准 |

<!-- ipd-section:ar_verification -->
## 4. 执行 AR 验证并更新管理表

对12条AR分别执行用例，预期是独立写定的值/序列而非复制实现返回值。每行列出实际观测；同一AR可有多个断言。更新 [AR-TR4.md](AR-TR4.md)，不覆盖TR3的未执行快照。

| AR 精确版本 / 判据 ID | 用例 / 环境版本 | 实现配置 | 预期结果 | 实际结果 / 状态 | 证据版本 / 缺陷 |
| --- | --- | --- | --- | --- | --- |
| ar-01@1 / C-AR-01 | V-AR-01 / Python 3.12.14 | IMPL-1 | `[480,555,1080,"INVALID_FORMAT","INVALID_TIME"]` | `[480,555,1080,"INVALID_FORMAT","INVALID_TIME"]` / passed | [E1](../evidence/verification.json) / V-AR-01 |
| ar-02@1 / C-AR-02 | V-AR-02 / Python 3.12.14 | IMPL-1 | `[[1065,1080],"INVALID_WINDOW","INVALID_WINDOW","INVALID_GRID","INVALID_WINDOW"]` | `[[1065,1080],"INVALID_WINDOW","INVALID_WINDOW","INVALID_GRID","INVALID_WINDOW"]` / passed | [E1](../evidence/verification.json) / V-AR-02 |
| ar-03@1 / C-AR-03 | V-AR-03 / Python 3.12.14 | IMPL-1 | `["B001","B002"]` | `["B001","B002"]` / passed | [E1](../evidence/verification.json) / V-AR-03 |
| ar-04@1 / C-AR-04 | V-AR-04 / Python 3.12.14 | IMPL-1 | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` / passed | [E1](../evidence/verification.json) / V-AR-04 |
| ar-05@1 / C-AR-05 | V-AR-05 / Python 3.12.14 | IMPL-1 | `[false,true,true,true,true,false]` | `[false,true,true,true,true,false]` / passed | [E1](../evidence/verification.json) / V-AR-05 |
| ar-06@1 / C-AR-06 | V-AR-06 / Python 3.12.14 | IMPL-1 | `["CONFLICT",true,"B002"]` | `["CONFLICT",true,"B002"]` / passed | [E1](../evidence/verification.json) / V-AR-06 |
| ar-07@1 / C-AR-07 | V-AR-07 / Python 3.12.14 | IMPL-1 | `[{"id":"B001","cancelled":true},[],"NOT_FOUND",[]]` | `[{"id":"B001","cancelled":true},[],"NOT_FOUND",[]]` / passed | [E1](../evidence/verification.json) / V-AR-07 |
| ar-08@1 / C-AR-08 | V-AR-08 / Python 3.12.14 | IMPL-1 | `["B002","NOT_FOUND",["B002"]]` | `["B002","NOT_FOUND",["B002"]]` / passed | [E1](../evidence/verification.json) / V-AR-08 |
| ar-09@1 / C-AR-09 | V-AR-09 / Python 3.12.14 | IMPL-1 | `["B002","B001"]` | `["B002","B001"]` / passed | [E1](../evidence/verification.json) / V-AR-09 |
| ar-10@1 / C-AR-10 | V-AR-10 / Python 3.12.14 | IMPL-1 | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]` | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]` / passed | [E1](../evidence/verification.json) / V-AR-10 |
| ar-11@1 / C-AR-11 | V-AR-11 / Python 3.12.14 | IMPL-1 | `120` | `120` / passed | [E1](../evidence/verification.json) / V-AR-11 |
| ar-12@1 / C-AR-12 | V-AR-12 / Python 3.12.14 | IMPL-1 | `[{"occupied_min":0,"free_min":600,"used_slots":0,"free_slots":40,"utilization_percent":"0.0"},{"occupied_min":600,"free_min":0,"used_slots":40,"free_slots":0,"utilization_percent":"100.0"}]` | `[{"occupied_min":0,"free_min":600,"used_slots":0,"free_slots":40,"utilization_percent":"0.0"},{"occupied_min":600,"free_min":0,"used_slots":40,"free_slots":0,"utilization_percent":"100.0"}]` / passed | [E1](../evidence/verification.json) / V-AR-12 |

<!-- ipd-section:system_acceptance -->
## 5. 完成 SR 系统验证与 IR 用户验收

以下6条SR和3条IR各重新驱动服务场景，并对预期输出作断言；不会读取AR的通过状态推断父层结果。IR层为自动化场景演示，真实人类使用确认、内容评审和批准均未执行。

| 层级 / 需求精确版本 | 判据 / 场景 | 配置 / 环境 | 预期 | 实际结果 / 状态 | 证据 / 决定引用 |
| --- | --- | --- | --- | --- | --- |
| SR / sr-01@1 | C-SR-01 / SC-1 | IMPL-1 / Python 3.12.14 | `["INVALID_GRID",{"id":"B001","start":"17:45","end":"18:00","duration_min":15}]` | `["INVALID_GRID",{"id":"B001","start":"17:45","end":"18:00","duration_min":15}]` / passed (software) | V-SR-01; [E1](../evidence/verification.json); 无人工批准 |
| SR / sr-02@1 | C-SR-02 / SC-1 | IMPL-1 / Python 3.12.14 | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` / passed (software) | V-SR-02; [E1](../evidence/verification.json); 无人工批准 |
| SR / sr-03@1 | C-SR-03 / SC-2 | IMPL-1 / Python 3.12.14 | `["CONFLICT",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},{"id":"B002","start":"09:00","end":"09:30","duration_min":30}]]` | `["CONFLICT",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},{"id":"B002","start":"09:00","end":"09:30","duration_min":30}]]` / passed (software) | V-SR-03; [E1](../evidence/verification.json); 无人工批准 |
| SR / sr-04@1 | C-SR-04 / SC-2 | IMPL-1 / Python 3.12.14 | `["B002","NOT_FOUND",["B002"]]` | `["B002","NOT_FOUND",["B002"]]` / passed (software) | V-SR-04; [E1](../evidence/verification.json); 无人工批准 |
| SR / sr-05@1 | C-SR-05 / SC-3 | IMPL-1 / Python 3.12.14 | `[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}]` | `[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}]` / passed (software) | V-SR-05; [E1](../evidence/verification.json); 无人工批准 |
| SR / sr-06@1 | C-SR-06 / SC-3 | IMPL-1 / Python 3.12.14 | `[{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"},{"occupied_min":60,"free_min":540,"used_slots":4,"free_slots":36,"utilization_percent":"10.0"}]` | `[{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"},{"occupied_min":60,"free_min":540,"used_slots":4,"free_slots":36,"utilization_percent":"10.0"}]` / passed (software) | V-SR-06; [E1](../evidence/verification.json); 无人工批准 |
| IR / ir-01@1 | C-IR-01 / SC-1 | IMPL-1 / Python 3.12.14 | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"INVALID_GRID",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]]` | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"INVALID_GRID",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]]` / passed (software) | V-IR-01; [E1](../evidence/verification.json); 无人工批准 |
| IR / ir-02@1 | C-IR-02 / SC-2 | IMPL-1 / Python 3.12.14 | `["B002","CONFLICT",{"id":"B001","cancelled":true},"B003",2]` | `["B002","CONFLICT",{"id":"B001","cancelled":true},"B003",2]` / passed (software) | V-IR-02; [E1](../evidence/verification.json); 无人工批准 |
| IR / ir-03@1 | C-IR-03 / SC-3 | IMPL-1 / Python 3.12.14 | `{"agenda":[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}],"summary":{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"}}` | `{"agenda":[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}],"summary":{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"}}` / passed (software) | V-IR-03; [E1](../evidence/verification.json); 无人工批准 |

<!-- ipd-section:regression -->
## 6. 处理缺陷、需求变化与回归

本次21个独立预期用例均未观察到差异，未创建虚构缺陷关闭记录。覆盖网格/时钟、相邻/重叠/包含、拒绝零状态变化、取消重订与重复取消、排序副本、120分钟示例及空/满日。若修改冲突谓词，影响AR-05/06、SR-03、IR-02，并可能破坏SR-06求和前提；应重跑整套21例。并发、持久化和真实GUI可用性属于C4排除范围，不能据此宣称已测试。

<!-- ipd-section:delivery -->
## 7. 整理交付配置与阶段文件

交付标准库软件核心、复现脚本、E1与本套中英文阶段文档/快照。正常示例120分钟占用、480分钟空闲、8/32格、20.0%；取消B001后60分钟、540分钟、4/36格、10.0%。输入约束和范围限制随包交付。

| 类型 / 必需性（草案） | 文档 ID / 路径 | 精确版本 / 摘要 | 覆盖需求 / 范围 | 责任人 | 状态 / 缺口 |
| --- | --- | --- | --- | --- | --- |
| 总体文档；必要 | [TR4.md](TR4.md) | doc rev 1 | TR4 / mvp | demo-doc-owner | 已填；无批准 |
| 需求表；必要 | [AR-TR4.md](AR-TR4.md) | doc rev 1 | 12 AR | demo-doc-owner | 阶段快照 |
| 实际实现/证据 | [../implementation/booking.py](../implementation/booking.py) | E1 / source SHA-256 | mvp | demo-dev | 已实际执行；合成输入 |
| 实际实现/证据 | [../implementation/verify_demo.py](../implementation/verify_demo.py) | E1 / source SHA-256 | mvp | demo-dev | 已实际执行；合成输入 |
| 实际实现/证据 | [../evidence/verification.json](../evidence/verification.json) | E1 / source SHA-256 | mvp | demo-dev | 已实际执行；合成输入 |

<!-- ipd-section:review -->
## 8. 汇总完成度与验收输入

填写与追踪覆盖：3IR→6SR→12AR，逐条分解、设计和用例均可定位。软件执行结果：12AR+6SR+3IR场景=21/21通过。人类验收：未执行；治理Gate/内容批准：未授予；上线/发布：未进行。此结果证明该合成范围的可执行示例与文档链路，不证明实际生产项目就绪。

