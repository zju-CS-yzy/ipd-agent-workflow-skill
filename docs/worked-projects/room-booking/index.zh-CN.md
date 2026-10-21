# 离线单会议室预约器：TR1—TR4 完整填写示例

[English](index.md) · [首次填写走查](walkthrough.zh-CN.md) · [合成原始输入](zh-CN/source-brief.md)

本例用 **3 条 IR → 6 条 SR → 12 条 AR** 展示逐条分解、计算/论证、需求表整理、详细设计和实际软件验证。不是一个 IR 或 AR 一份文件：同一总体文档包含多条论证，同一管理表包含多条需求。

项目只管理一间房一天的串行内存预约：08:00—18:00、15 分钟网格、半开区间允许相邻、取消释放、按时间查看和计算利用率。全部输入由作者合成，没有私人项目、客户访谈或真实批准。教学编号登记于 [catalog@1](catalog.json)，它不是实际项目 `.ipd/requirements.yaml` 的替代事实源；本目录也没有伪造 Claim、Gate、状态 revision 或人类审批。

## 按阶段阅读

| 阶段 | 已填写总体文档 | 对应需求表快照 | 本阶段完成的工作 |
| --- | --- | --- | --- |
| TR1 | [原始需求与可行性分析](zh-CN/TR1.md) / [EN](en/TR1.md) | [IR-TR1](zh-CN/IR-TR1.md) / [EN](en/IR-TR1.md) | U1/U2/U3逐条形成3个IR；计算600分钟/40格；此时不预填SR |
| TR2 | [需求场景分析与模块分配](zh-CN/TR2.md) / [EN](en/TR2.md) | [SR-TR2](zh-CN/SR-TR2.md) / [EN](en/SR-TR2.md) | 第3章逐条论证6个SR；第4章整理表；此时AR尚未形成 |
| TR3 | [概要设计与AR分配](zh-CN/TR3.md) / [EN](en/TR3.md) | [AR-TR3](zh-CN/AR-TR3.md) / [EN](en/AR-TR3.md) | 第5章逐条论证12个AR；第6章整理表；实现与验证仍是计划 |
| TR4 | [详细设计、实现与测试](zh-CN/TR4.md) / [EN](en/TR4.md) | [AR-TR4](zh-CN/AR-TR4.md) / [EN](en/AR-TR4.md) | 逐AR详细设计与实现定位、12个AR用例、6个SR用例及3个IR场景实际执行 |

建议先沿着 `ir-02@1 → sr-03@1 → ar-05@1 / ar-06@1` 阅读：从“相邻可用但不能重叠”的用户目标，推导区间公式，分配纯谓词与全量扫描，最后查看相邻和重叠的实际输出。再读 `ir-03@1 → sr-06@1 → ar-11@1 / ar-12@1`，核对统计为何依赖不重叠不变量。

## 可以独立核对的计算

- 容量：`(18−8)×60=600 min`，`600/15=40` 格；正长度且不重叠，所以同时有效预约不超过40条。
- 冲突：两段 `[a,b)`、`[c,d)` 不相交为 `b≤c 或 d≤a`，取反得到 `a<d 且 c<b`。端点相等不会冲突。
- 占用：08:00—09:00 与09:30—10:30之和为120分钟，空闲480分钟，已用8格、空闲32格，利用率20.0%。不能把包含间隙的150分钟跨度当占用。
- 取消第一条后为60分钟、540分钟、4/36格、10.0%；空日与满日分别为0.0%和100.0%。每格2.5%，用整数十分之一百分比无需舍入。

## 实际执行与结果边界

[booking.py](implementation/booking.py) 是标准库实现；[verify_demo.py](implementation/verify_demo.py) 使用独立预期值执行21个用例。[E1 原始结果](evidence/verification.json) 保存每项预期、实际、结果、环境、执行时间和源码SHA-256。当前结果为 **21/21 软件用例通过**；IR层是自动化场景演示，真实人类验收与治理批准仍未发生。

从仓库根目录复现，不改写保存的证据：

```console
python docs/worked-projects/room-booking/implementation/verify_demo.py
python scripts/verify_room_booking_walkthrough.py --execute
```

第二个命令同时检查16份模板实例、中英文需求关系、逐条论证链接、阶段信息边界、源代码摘要及新运行与保存结果的一致性。模板结构通过不代表论证内容已获人类认可。模板锁定见 [document-instances.json](document-instances.json)。
