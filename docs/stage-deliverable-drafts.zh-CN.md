# TR1—TR4 阶段总体文档与需求表草稿

更新：2026-10-20。以下为供共同补充的 **0.2.1 讨论稿**，采用本项目提出的阶段口径，不是华为内部 QA 模板，也不表示已修改现有六 Phase 或 TR/DCP 门禁。新增类型可通过 `ipdctl templates` 查看和实例化；“每阶段至少两份”的建议尚未作为自动门禁启用。

完整填写与实际执行示例见[离线会议室预约器](worked-projects/room-booking/index.zh-CN.md)：3IR→6SR→12AR、16份中英文文档、逐条论证与21项软件用例。[首次填写走查](worked-projects/room-booking/walkthrough.zh-CN.md)记录了唯一论证编号、渐进填写元数据和阶段快照这三项补充指引。

## 先看四份总体文档

| 阶段 | 总体组织文档 | 配套需求管理表 | 总体文档重点 |
| --- | --- | --- | --- |
| TR1 | [原始需求与可行性分析](../ipdctl/document_templates/zh-CN/tr1_requirements_feasibility.md) / [EN](../ipdctl/document_templates/en/tr1_requirements_feasibility.md) | [IR 表](../ipdctl/document_templates/zh-CN/ir_spec.md) / [EN](../ipdctl/document_templates/en/ir_spec.md) | 原始来源、共享背景、用户场景、范围、方案比较、可行性与本轮目标，形成 IR |
| TR2 | [需求场景分析与模块分配](../ipdctl/document_templates/zh-CN/tr2_scenarios_allocation.md) / [EN](../ipdctl/document_templates/en/tr2_scenarios_allocation.md) | [SR 表](../ipdctl/document_templates/zh-CN/sr_spec.md) / [EN](../ipdctl/document_templates/en/sr_spec.md) | 基于 IR 分析正常 / 异常场景、系统边界、模块职责与分配，形成 SR |
| TR3 | [概要设计与 AR 分配](../ipdctl/document_templates/zh-CN/tr3_high_level_design.md) / [EN](../ipdctl/document_templates/en/tr3_high_level_design.md) | [AR 表](../ipdctl/document_templates/zh-CN/ar_spec.md) / [EN](../ipdctl/document_templates/en/ar_spec.md) | 基于 TR2 形成总体架构、交互、接口、资源预算与 AR 分配，策划下一阶段 |
| TR4 | [详细设计、实现与测试验收](../ipdctl/document_templates/zh-CN/tr4_detail_implementation_test.md) / [EN](../ipdctl/document_templates/en/tr4_detail_implementation_test.md) | 更新同一份 [AR 表](../ipdctl/document_templates/zh-CN/ar_spec.md)，补充实现与验证追踪 | 详细设计索引、实现 / 构建 / 集成、AR 模块验证、SR 系统验证、IR 用户验收、缺陷与回归 |

“总体组织文档”解释分析过程、方案取舍、跨需求关系和阶段结论；“需求表”逐条管理规格与追踪。二者通过路径和精确版本关联，不在每条需求文件中重复共同背景。IR/SR/AR 是三个需求层次，TR4 不再创造第四层需求。

总体文档均有交付件清单，记录文档 ID / 路径、精确版本或摘要、覆盖范围、责任人和缺口。建议最小组合为该阶段总体文档和对应需求表；真实设计、实现和验证证据仍须按适用范围提供，不能用两份文档替代。硬件选型、接口设计、原型实验等按项目需要附加。体量较大时可按模块拆分分析或设计文件，由总体文档统一索引；本轮需求覆盖不能因此丢失。

## 首次编写时的工作顺序

每份草稿开头说明从哪里开始，每章明确目的、输入、编写步骤和产出。后续的需求表不必在写作开始时已经存在：先开展分析形成候选需求，再按项目流程登记和整理管理表。

| 阶段 | 分析和形成需求的位置 | 管理表整理的位置 |
| --- | --- | --- |
| TR1 | 第 2—3 章分析问题与场景；第 4 章逐条从来源形成候选 IR；第 5 章检验可行性并修订 | 第 6 章汇总 IR 并核对原始来源覆盖 |
| TR2 | 第 2 章提供场景与边界依据；**第 3 章逐条完成 IR→SR 分解论证** | 第 4 章整理 SR 表，逐行回指论证并核对 IR 覆盖 |
| TR3 | 第 2—4 章形成架构、运行机制与预算依据；**第 5 章逐条完成 SR→AR 分解 / 分配论证** | 第 6 章整理 AR 表，逐行回指论证并核对 SR 组合覆盖 |
| TR4 | 第 2 章逐项写 AR 对应的详细设计；第 3 章实际实现 / 构建；第 4—5 章分别执行各层验证 | 第 4 章更新同一 AR 表的设计、实现和实际证据追踪 |

TR2 / TR3 的逐条说明块须按实际下层需求数量复制。每条记录包含上层版本及目标、场景或设计前提、推导步骤、计算 / 图例 / 逻辑论证、指标与方案取舍、所得需求陈述、验证判据及待决项。量化论证写明假设、变量、单位和来源；规则、接口或异常处置可使用状态 / 时序 / 反例等合适的论证，不要求补无意义公式。共享图或计算可以只写一次，但每条下层需求仍需解释如何由其推出。

逐条说明之后，还要按每条上层需求检查其全部下层需求组合后能否覆盖目标。例如模块时延预算需要核对总和或关键路径与余量；多个 AR 各自通过不能自动证明 SR 成立。模板中的简短示例只演示推导写法，不是项目事实、预算或通过结果。结构检查只检查章节、表头与填写完整性，不判断论证是否正确或充分。

## 需求规格以多行表格维护

`ir_spec/sr_spec/ar_spec` 现在是 **1.1.1 管理表模板**。默认两行演示，实际数量不限于两条，也不要求每条需求单独建立说明文件。每条需求保留一个精确 `id@version`；实例元数据的 `requirements` 列出该表覆盖的所有需求版本。

- IR 列包括来源与共享背景、用户场景与范围、需求陈述、价值、验收意图、优先级、责任人、增量与 SR 分解。
- SR 列包括上层 IR、场景、系统行为、指标与边界、接口约束、模块分配、系统验证、责任与 AR 分配。
- AR 列包括上层 SR、分配模块、责任、行为与约束、接口预算、概要 / 详细设计及实现、验证判据、实际结果与证据、回归范围。

普通 Markdown 的管线表格不支持合并单元格，因此 `.md` 中使用原生 HTML 表格。共享背景、场景或上层引用可用 `rowspan` 跨行合并；新增、删除或拆分行时调整跨度。示意：

```html
<tr>
  <td>ir-a@1</td>
  <td rowspan="2">共同来源与背景，只写一次</td>
  <!-- 本行其余列 -->
</tr>
<tr>
  <td>ir-b@1</td>
  <!-- 共享背景列由上一行覆盖；继续本行其余列 -->
</tr>
```

每条需求的 ID / 版本单元格不得合并；不同的验收判据、结果、责任和增量承诺也不能被合并掩盖。只有实际相同的内容才共享。可视呈现取决于 Markdown 查看器是否允许 HTML；不支持 HTML 的查看器需查看源文件或用支持 HTML 的预览。当前检查器按展开后的单元格验证列、跨度和需求引用，不会因合并而将第二条需求漏掉。

单元格内使用 `<br>` 换行，文本中的 `<`、`>`、`&` 分别写成 `&lt;`、`&gt;`、`&amp;`；不要依赖 HTML 单元格内的 Markdown 语法自动渲染。

`.ipd/requirements.yaml` 仍保存规范需求事实。管理表是受版本控制的分析与交付文件，修改其中描述不会自动写入需求登记、执行验证或记录批准。表格填写、结构检查和阶段批准分别处理；待决、未执行、失败、跳过和失效状态均不能写成通过。

## 版本与使用

活动模板包为 `ipd-starter@1.2.1`，包含 18 类、36 份中英文文件：3 类需求管理表、4 类阶段总体文档讨论稿及 11 类原有专用模板。`1.0.0`、`1.1.0`、`1.2.0` 包保留原内容供既有锁定使用。阶段稿自身为 `0.2.1`，需求管理表为 `1.1.1`，其他未修改类型仍为 `1.0.0`。单增量创建实例后不自动换包；采用新模板应遵守现有包锁定和增量边界。

```console
ipdctl templates --type ir_spec --locale zh-CN
ipdctl templates --type tr1_requirements_feasibility --locale zh-CN
ipdctl templates --type tr3_high_level_design --locale en
```

完整操作见[需求与模板说明](requirements-and-templates.zh-CN.md)。下一轮可重点补充各章的具体填写尺度、硬件项目差异和评审检查项，再决定是否把阶段组合配置成正式义务。

## 公开参考与采用边界

本次参考的是可公开访问的大纲和文档要求，正文为本项目原创草稿：

- [NASA ConOps 注释大纲](https://www.nasa.gov/reference/appendix-s-concept-of-operations-annotated-outline/)：用于 TR1 的背景、参与者、使用场景、边界、替代方案与影响分析组织。
- [ECSS 技术需求规格标准及 Annex A 文档要求](https://ecss.nl/standard/ecss-e-st-10-06c-technical-requirements-specification/)：用于需求规格的目的、输入引用和结构安排。
- [NASA 软件设计说明公开大纲](https://swehb.nasa.gov/spaces/SWEHBVC/pages/50888776/5.13%2B-%2BSwDD%2B-%2BSoftware%2BDesign%2BDescription)：用于 TR3 / TR4 的架构、模块、接口、设计理由、详细设计与追踪。未获取或复刻其中提到的内部受限模板。
- [NASA 需求验证矩阵](https://www.nasa.gov/reference/appendix-d-requirements-verification-matrix/)：用于精确需求标识与分层验证追踪。
- [华为云 CodeArts Req 术语](https://support.huaweicloud.com/intl/zh-cn/productdesc-projectman/codeartsreq_07_2008.html)：用于 IR/SR/AR 需求分层。

这些来源不证明本项目 TR1—TR4 编号映射为通用规则，也不构成对本 Skill 的认证。具体阶段口径来自本项目用户的培训经验，模板正待共同细化。
