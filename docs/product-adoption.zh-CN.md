# 子产品版本与主产品采用

Recorder 和 Replay 分别登记稳定的产品 ID、版本及批准历史。工具版本记录精确的发布范围，主产品采用记录该版本组合适用的用途、协议、数据与环境。受控数据集另行记录其采集来源和质量。

## 显式启用契约

使用既有需求命令，或等价的 `products . --request request.json` 预览，再用 `products . --apply plan.json --actor 姓名 --authorized` 应用。每个请求包含唯一 `request_id`、`reason` 和 `operation`。预览不写项目事实，应用会在项目互斥锁内重验指纹，并使用既有回滚日志。精确重试保留同一请求 ID。

需求登记启用后，应用 `adopt_product_governance`。已有阶段组织的项目须先采纳支撑材料角色契约。本次显式升级产生注册表 1.3 / 契约 0.5.7，保留带摘要的升级前快照。现有项目可以直接重画视图，旧客户端会拒绝写入新契约。

## 分别登记和发布工具

`product_register` 的 `product` 包含 `id`、`title`、`scope`。Recorder 和 Replay 各自登记。

版本记录包含 `id`、`product`、`version`、`scope`、`source`、`protocol`、`environments`、`capabilities`、`requirements`、`artifacts`。每份产物用项目相对 `path` 与 `sha256` 固定。来源包含 `backend`、`repository`、`revision`、`path`。Git 使用完整提交，SVN 使用数字版本，内容后端使用产物清单摘要。仓库出处属于声明的来源信息，本版验证本地内容摘要。

已有旧版批准时，使用 `product_import`，其中 `import` 包含 `release`、`approver`、批准证据的路径与摘要，以及 `identity_source: historical-local-declaration`。旧批准保留原适用范围，主产品采用还要完成本地适用性评审。

新版工具先领取对应规范交付件 Owner 的 Claim，写出产物后，用 `product_work` 登记 `kind: release`、`owner` 和版本 `record`。新增证据路径须属于该 Owner。随后按正常 CLI 关闭、评审并取得明确的人类批准，再以工作 ID 应用 `product_accept`。接受操作会核对当前工作是否属于该次精确评审。主产品同一增量内可串行接受多次工具发版。

## 数据与兼容性分别验证

`kind: dataset` 沿用同一工作、评审和接受路径。记录精确 `recorder` 版本、`protocol`、`environment`、`configuration`、`calibration`、`time_basis`、数据 `files` 和 `quality`。质量对象包含用例及证据路径与摘要，工具批准和生成数据的质量分别留证。

`kind: compatibility` 记录精确 `releases`、`datasets`、`protocol`、`environment`、`cases`、`evidence`。每个用例包含 `id`、`criterion`、`expected`、`observed`、`result`。失败、未知和跳过结果可以保留在草稿中，并阻止接受。按实际用途制定格式、时间基准、通道、完整性和目标环境判据，使用代表性数据执行录制与回放验证。

采用需要覆盖其精确版本组合、协议、环境及所需数据集的已接受验证。开发 PC 的证据适用于对应环境，测试 PC 使用须有该环境证据。

## 按用途采用与受控升级

在已有适用性评估 Owner 下登记 `kind: adoption`，包含 `id`、稳定用途 `key`、`purpose`、精确 `releases`、`datasets`、`checks`、`protocol`、`environment`、`consumers`、`evidence`、`prior`、`assessments`。登记前，先为每个消费交付件配置到采用 Owner 的显式执行依赖。

相同适用条件下，一份采用可以服务多个交付件。采集判据允许时可以单独采用 Recorder；回放或评估按需要采用经过组合验证的 Recorder/Replay。首次采用使用 `prior: null` 和空评估列表。替换采用固定原采用 ID，并逐项评估新旧消费交付件，字段为 `target`、`action: reverify|unaffected`、`rationale`。已经接受的消费交付件在新增量中调整采用。

`products . --impact 旧版本ID --replacement 新版本ID` 只读显示来源、产物、协议、环境和范围差异，以及受影响的数据集、兼容性验证、消费交付件和需求引用。需求及范围预览也会列出下游成果和验证影响。接受新采用后切换选定版本，新工具发版本身保留现有采用的精确引用。

内容漂移、版本组合不兼容、目标环境证据缺失或 `product_withdraw` 会暂停受影响用途。历史接受记录继续可查。需求验证绑定采用输入，升级或证据变化后须完成适用的重新验证。

## 旧成果交接与回填

`products . --handoff-plan request.json` 只读预览显式文件映射。请求包含 `request_id`、`reason`、`source_owner`、`target_owner` 和 `files: [{"source":"old.md","target":"docs/new.md"}]`。结果提供内容摘要、原评审摘要、目标 Owner 冲突及候选绑定规则。审查并采纳目标绑定后，再领取目标 Owner 的 Claim。

在该 Claim 下，用 `handoff_instance` 提交 `source`、`source_owner`、`sha256`、`editor` 和正常的新 `instance`。操作生成锁定模板下的新草稿，附上来源正文和出处记录。关闭前完成模板填写。原文件和原 Owner 评审继续保留，路径搬迁与删除使用后续版本的迁移机制。

## Dashboard 与验证边界

统一矩阵及依赖图展示选定工具版本、数据、验证、主产品采用及消费交付件。详情说明批准来自历史导入还是当前 Owner 治理，并列出精确上下文与诊断。项目继续执行单 Claim 和单评审对象。

本版验证声明的用例结果、证据身份和治理受理条件。独立内容就绪评审与平台认证审批映射沿用其各自版本规划。大型产物和数据留在受控仓库路径中，子产品历史记录清单及摘要。完整增量基线中的普通评审证据仍适用既有快照大小限制。

公开场景位于 `tests/test_product_governance.py`。它通过正常 CLI 接受新版 Recorder，实际执行录制和回放子进程，评审数据集与兼容性报告，再采用精确版本并领取主产品消费交付件。可用 `python -B -m unittest tests.test_product_governance -v` 执行。
