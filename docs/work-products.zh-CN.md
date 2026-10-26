# 支撑成果与统一 Dashboard

[English](work-products.md) | [简体中文](work-products.zh-CN.md)

v0.5.5 将需求、交付件、文档实例和支撑文件投影到一个只读实体索引。主依赖图下方紧接“需求与阶段成果”图；两图与统一矩阵共用节点身份、详情和选择。矩阵保留所有流程交付件，包括尚未关联需求的交付件。

机器 ID 只使用小写英文字母、数字、点、下划线和连字符，并以字母或数字开头；标题和人名可使用中英文。


## 先决定材料的治理方式

| `usage` | 何时选择 | 节点及状态 |
| --- | --- | --- |
| `deliverable` | 选型、论证、架构等专业工作需要单独 Claim、评审和接受 | 创建或引用真实流程 Deliverable；阶段图显示该交付件，具体文件仍可从详情和矩阵查看 |
| `attachment` | 同一成果内的图、计算、代码或测试文件，不需单独审批 | 材料节点指向唯一 Owner；显示文件可用性，不复制 Owner 的接受状态 |
| `reference` | 外部规范、本地参考副本、可选资料 | 参考节点；声明是否必需、Owner 和理由。文件存在不等于已批准 |

每个文件仍只有一个 Owner。共享文件只登记一次，通过多个阶段单元引用；同一增量中的角色必须一致。文件缺失、变化或历史快照与交付件审批状态分别展示。`required` 决定就绪检查，`execution_dependency` 是单独的执行前置决定；支撑边和归属边不会自动改变 Claim 顺序。

## 现有项目只更新展示

用新版本运行 `ipdctl render-dashboard PROJECT`，无需采纳新契约，也不会拆分旧 Owner、重编号或改变状态、Runtime、审批和历史。统一视图使用旧项目已经登记的关联；它无法从任意 Markdown 文字推断专业交付件。未登记的文件须先规划绑定，才能作为可靠的材料节点。

`render-dashboard` 仅重画；在安全流程边界可用 `refresh`，随后运行 `verify`。验证检查渲染源码指纹、产物及统一投影是否新鲜。不要修改生成的 HTML/JSON 来修复事实。

## 新项目或新增量显式采纳角色

先按[阶段组织](stage-organization.zh-CN.md)启用需求并采纳组织契约 1.1，再在接受任何成果之前，预览并授权应用以下请求：

```json
{"request_id":"adopt-work-v055","operation":"adopt_work_products","reason":"明确专业成果与附件的边界","roles":[]}
```

```bash
ipdctl requirements PROJECT --request adoption.json --json > adoption-plan.json
ipdctl requirements PROJECT --apply adoption-plan.json --actor MAINTAINER --authorized
```

已有当前支撑项时，`roles` 必须逐项列出 `unit`、`kind`、`target`、`usage`，不能遗漏或猜测；空数组只适用于尚无支撑项的情况。成功后登记为 Schema 1.2 / 契约 0.5.5，并保留带哈希的旧快照。旧客户端拒绝写入新契约。已接受成果的增量应保持旧事实，在新增量的安全边界采纳。

## 先规划独立支撑交付件

以下请求给 `plan.integrated_plan` 增加一个独立选型交付件，明确要求它先完成。路径必须是项目相对路径。

```json
{
  "request_id":"sensor-selection", "reason":"两条 IR 共用传感器时延论证",
  "stage":"TR2", "consumer":"plan.integrated_plan",
  "materials":[{
    "id":"plan.sensor_selection", "title":"传感器选型与时延预算",
    "path":"docs/analysis/sensor-selection.md", "usage":"deliverable",
    "required":true, "rationale":"支撑采样与报警的系统需求分解",
    "execution_dependency":true
  }]
}
```

```bash
ipdctl work-plan PROJECT --request work-request.json --json > work-plan.json
ipdctl work-plan PROJECT --check-plan work-plan.json --json
```

这两条命令零写入。阅读 `issues`、`tailor_diff`、`candidate_process_extensions`、`candidate_artifact_bindings`、`candidate_stage_units`，以及就绪标志。计划包含状态 revision 和输入指纹；输入或材料变化后重新预览。活动 Claim/评审、已有历史、Owner 冲突、缺失前置与闭合阶段会阻止直接使用候选。

候选不是已接受事实，也不是新的自动应用协议。维护者在核对候选后把扩展和绑定内容写入现有 `.ipd/process_extensions.yaml` 与 `.ipd/artifact_bindings.yaml`，再运行 `tailor --preview --json`，按原有迁移/授权规则应用 `tailor`，并在需要时 `adopt-baseline`。不要覆盖已有历史或绕过迁移。最后将候选单元放入现有 `stage_unit` 请求，预览和授权应用。所有支撑项在契约 1.2 下都须明确 `usage`。

专业交付件按原有 `context → claim → work → close → review → human approve/reject → refresh → verify` 完成。消费者引用已接受的精确支撑内容，再逐条分解 IR→SR 或 SR→AR，形成结论与需求表。TR4 汇总设计、实现和实际执行结果。阶段结论不会代替专业成果的独立评审。

## 阅读视图

- 主依赖图显示当前流程，包含真实交付件及已登记的材料/文档。图例中的前置依赖、支撑、归属含义不同；筛选只改变显示。
- 阶段图按 IR 与 TR 单元折叠，依次展示上层需求、支撑成果、分解结论/需求表及下层需求；TR4 最后一列显示分层验证。展开后可缩放、选节点查看详情并跳转使用位置。
- 唯一矩阵按需求树或交付件组织，可按阶段、增量、类型、责任人、状态或文本筛选。历史节点带上下文和基线链接，不能被当前 Owner 接受状态冒充。
- 详情区保留原始记录供审计。材料的可用性、需求定义/分解、实现、验证与人工接受是不同维度；未知或跳过不能视为通过。

模板包仍为 1.3.0，23 类中英文 Markdown；本版未增加 DOCX/XLSX、自动历史迁移、身份认证映射或并发治理。公开合成验证不能代替真实项目及私有 Golden。
