---
name: a7c2-fuji-install
description: 带用户逐步为 Sony A7C II（ILCE-7CM2，固件 2.01）安装富士／理光风格外观。未指定滤镜时使用默认六款，支持从富士 11 款、理光彩色 4 款中自定义最多六个槽位；检查版本、驱动、历史事务和连接，调用本地向导并等待真实相机反馈后继续核验。
---

# A7C II 富士／理光外观安装向导

使用本技能目录的 `scripts/guide.py` 调用项目本地向导。该脚本的 `settings.private.json` 保存已安装项目和 Python 环境的位置；项目内的副本可自动定位项目。工具输出单个 JSON 文档，`phase`、`allowed_operations` 和 `prompt` 决定下一步。完整 USB 引擎由现有 Windows `A7C2Tools.exe --worker` 执行。

## 首次说明与默认方案

用户首次调用本技能时，必须先用易懂的中文说明容量、默认顺序、完整可选清单、自定义方法和安装约定，再提出当前阶段需要的问题。以下内容可直接使用；同一会话续接无需反复展示：

> 这套工具最多同时安装 6 个滤镜，占用自订 1–6。你没有指定滤镜时，默认安装：1. Classic Neg（经典负片）；2. Classic Chrome（经典正片）；3. Nostalgic Negative（怀旧负片）；4. Velvia；5. GR 正片；6. GR 负片。安装会替换所选槽位现有内容。
>
> 目前有富士 11 款、理光彩色 4 款，可混搭，也可只装部分槽位。富士：Astia、Bleach Bypass、Classic Chrome、Classic Neg.、Eterna、Nostalgic Neg.、Pro Neg Hi、Pro Neg Std、Provia、Reala Ace、Velvia。理光：GR 正片、GR 负片、GR 标准、GR 鲜艳。
>
> 自定义时直接按槽位发来，例如“1. Classic Neg 2. Eterna 3. Nostalgic Negative 4. Velvia 5. GR 正片 6. GR 负片”；不需要自己修改文件或填写 JSON。也可以说“第五个换成 Eterna”或“只装前三个”。没有特殊要求就沿用默认组合。
>
> 请严格按向导约定顺序操作，看到当前步骤后再操作并如实反馈，尤其不要在写入中拔线、关机或取电池。为减少误读和漏步骤，建议使用具备较强推理能力、支持本地工具调用的模型，例如 GPT、Claude、DeepSeek Pro、GLM、Kimi 等，并选用所在平台可用的较强版本。模型选择有助于执行流程，但没有跨模型成功率数据，也不能保证安装成功。

以上清单以本地已核对的配对库为基础。首次 `init`／`status` 后必须用 `alternatives.profiles` 核对可用项；库不一致时先说明实际差异，禁止把缺失滤镜说成可安装，禁止静默替换。外观为拟合风格，不宣称等同富士／理光官方色彩。模型名称只是选用建议，不是执行依赖，不要求用户为使用本技能购买或切换平台。

默认槽位与工具名称必须严格对应，用户可见写法不能直接当作工具参数：

| 自订槽位 | 用户可见名称 | `profile` 精确名称 |
| --- | --- | --- |
| 1 | Classic Neg／经典负片 | `Classic Neg.` |
| 2 | Classic Chrome／经典正片 | `Classic Chrome` |
| 3 | Nostalgic Negative／怀旧负片 | `Nostalgic Neg.` |
| 4 | Velvia | `Velvia` |
| 5 | GR 正片 | `GR Positive Film` |
| 6 | GR 负片 | `GR Negative Film` |

`GR 标准` 对应 `GR Standard`，`GR 鲜艳` 对应 `GR Vivid`。其他富士名称使用可选清单中的精确拼写。支持大小写、常见空格与句点差异，以及 Classic Negative／经典负片、Nostalgic Negative／怀旧负片等明确同义词；“正片”“负片”未说明富士或理光时先澄清，不凭感觉猜测。不提供未列入可用库的黑白或其他滤镜。

## 交互方式

- 用户说“使用 $a7c2-fuji-install 安装”“帮我安装滤镜”且没有指定滤镜：自动选择上述默认六款，不逐款询问、不要求先选套餐。默认不启用 FL2/FL3、快门声、竖屏或 Lightroom 插件。
- 默认选择不等于已完成写入授权。展示实际清单及覆盖影响后，用户说“按默认安装”即接受此方案，不再反复询问配置；仍须完成状态检查、取得当前电量及其他必要的真实反馈。
- 每轮只提出当前需要完成的一项相机操作或一组紧密相关的操作，解释如何判断完成，等待真实反馈。不得编造版本、电量、断电或试拍结果。已获得的信息和授权继续有效；每次实际写入需有当前电量反馈。
- 普通用户只看到当前状态、当前操作和结果。JSON、路径、事务、USB ID 等细节留给 AI；排障确有需要时再说明。
- 提示 USB 连接方式时，必须写明相机界面上的“影像传输（MSC）”，并说明这就是海量存储模式；首次连接及断电重开后重新连接都使用此称呼，不只说“选择海量存储”。
- 用户改变配置时展示变更影响；已开始的安装沿用保存的计划，不偷偷切换为默认方案。

## 所有模型必须遵守的执行约束

1. **先读状态，再执行一个合法步骤。** 以当前 `session` 的 `phase`、`allowed_operations`、`prompt` 和 `plan` 为依据，完成一次调用后检查返回 JSON 与退出码。禁止把从机型确认到安装续接的命令串成无人检查的一键执行；等待用户操作时必须停下。
2. **真实反馈不能由模型代填。** 用户未报告的机身版本、改装历史、电量、断电完成、取景或试拍结果均为未知；未知不等于通过。只有实际取得对应确认才传 `--confirmed`、`--replace-slots` 或 `true`。本工具写入要求当前电量至少 50%，官方固件更新的要求另按官方说明核对。
3. **配置先离线校验并回读。** 将用户意图转换为 1–6 的不重复槽位及库中精确名称，提交 `configure` 后核对返回的全部槽位、名称、附加功能和 `plan.id`。不一致就停止，不进入写入。超过六个、重复槽位、未知或歧义名称须先让用户修正，不自动截断或换款。
4. **保存的计划优先于新默认值。** 续接先读取原计划，不能因技能升级或用户未重新指定滤镜而重置；开始写入后禁止 `configure`。用户此时要换组合，说明当前阶段限制，保留原事务，不另开安装规避。
5. **仅通过公开向导入口执行。** 不直接调用 USB、`A7C2Tools.exe --worker`、内部 `_worker` 或旧版刷写命令来绕过状态检查；不手改私有状态、请求、校验结果或电量门槛。其他相机软件必须关闭，同一时间只允许一个相机操作。
6. **拒绝、异常或结果未知就检查证据。** 退出码 2、缺失／无法解析 JSON、超时、断连或 `NEEDS_REVIEW` 时读取现有状态及日志；不能假定未写入并重放，不能杀后台进程。没有后台结束凭据不得提示拔线、取电池或重开。
7. **工具不可用就停在缺失条件。** 无本地命令执行能力、脚本／环境缺失或命令不受支持时，说明具体阻碍并保留进度，不模拟调用、伪造成功或自行拼凑替代刷写流程。Windows UAC 由用户本人处理。
8. **完成必须有两类证据。** 程序验证和用户机身检查均通过、状态为 `COMPLETE` 才能宣布完成；离线测试、进程退出或模型判断不能替代实机验收。不同模型使用相同状态与证据规则，不降低门槛。

## 调用

以下 `<helper>` 是本技能 `scripts/guide.py` 的绝对路径。启动脚本仅需 Python 标准库；脚本会选择已配置的项目运行环境。

```text
python "<helper>" init
python "<helper>" --session "<session>" status
python "<helper>" --session "<session>" configure --file "<config.json>"
python "<helper>" --session "<session>" answer --kind camera --file "<feedback.json>"
python "<helper>" --session "<session>" start --operation drivers
python "<helper>" --session "<session>" poll
```

`init` 在首次使用时创建本地进度，后续调用默认返回同一进度。记录返回的 `session`；所有后续操作显式带上它。`status`、`plan`、`answer`、`configure`、`diagnostics` 不打开 USB。只有 `start` 会启动后台操作。退出码 2 表示本次命令被拒绝／失败，阅读错误，不用猜测的参数绕过。

将用户的真实反馈写入本地 JSON，再用 `answer` 提交。例如：

```json
{"model":"ILCE-7CM2","firmware":"2.01","modified":"no"}
```

`modified` 是以前是否安装过本项目（`yes`／`no`／`unknown`），不是是否更新过 Sony 官方固件。可将用户说的“A7C2”规范为机型代码，机身版本必须来自用户查看菜单的结果。

## 按状态继续

1. **CAMERA_INFO**：先问机型、机身菜单里的版本、以前是否用过本项目。工具里的固定 `2.01` 选项不能证明实际版本。用 `answer --kind camera` 记录。
2. **FIRMWARE_UPDATE**：先核对对应地区的 Sony 官方 2.01 更新说明和用户当前版本所需路径，提供官方链接并逐步引导。工具不会刷官方固件。官方更新需电量至少 51%，建议充满；更新过程中不能取电池或存储卡。涉及格式化，先处理用户数据并取得相应授权；不要为安装滤镜自动格式化卡。更新后重新取得机身版本，用 `camera` 再提交。**UNSUPPORTED_FIRMWARE／UNSUPPORTED_MODEL** 停止，不盲目升最新版或尝试降级。项目“恢复原厂功能”不是固件升级／降级。
3. **CONNECT_CAMERA**：让用户关闭原软件，保留一台相机，用数据线直连电脑；相机出现 USB 连接方式选项时，选择界面上的“影像传输（MSC）”（即海量存储模式）。用户完成后，提交 `{"confirmed":true}` 到 `answer --kind connected`。
4. **EXISTING_TRANSACTION**：读取列出的历史阶段。不能删除、搬走或改写状态来解除阻塞。已在等待重开的旧一键安装可用 `adopt --workspace "<old workspace>"` 续接；先向用户说明这是原计划。其他旧事务需读原软件日志、导出诊断并在原软件审查，结果未知不能重放。不能把所有历史失败都解释为驱动问题。
5. **READY_DRIVERS**：`start --operation drivers`。这会执行现有两阶段驱动准备；Windows UAC 由用户在本机处理，密码不交给 AI。相机提示“请检查所连接的设备”和盘符消失可能是正常现象；以程序结果为准。
6. **READY_STABILITY**：`start --operation stability` 运行至少两分钟的只读测试。后台异步执行，持续提供简短进度。失败后根据日志处理线材／接口／驱动，不自动循环测试。
7. **HISTORY_QUESTION**：询问是否改装，用 `answer --kind history` 提交 `{"modified":"yes"}` 或 `no`。
8. **READY_RESTORE**：旧安装需先恢复原厂功能。解释自订 1–6 将被设为 ST，旧配方不找回，保留需要的参数。取得对此影响的明确确认及当前电量，执行 `start --operation restore --confirmed --battery <实际百分比> --replace-slots`。不能把“装富士滤镜”的一般意图当成用户已经知道恢复会清空旧配方。
9. **READY_INSTALL**：展示 `plan` 中的实际清单（新会话未指定滤镜时应为上表默认六款；自定义及旧会话以已保存计划为准）、覆盖的槽位及可选调整。若新会话默认方案与上表不符，先在允许配置的阶段通过 `configure` 校正并回读；缺失默认滤镜则停止说明，不能照旧安装。取得用户接受方案和当前电量后，执行 `start --operation install --confirmed --battery <实际百分比> --replace-slots`。如果已有接受同一清单的授权，只补问仍缺的信息。不得代替用户填 100%。
10. **RUNNING**：不要再启动其他相机操作，不要杀进程／设置写入超时后重试。用 `status` 查看进度，用 `poll` 消费已结束任务的结果。后台日志路径会返回，可读日志解释进展。用户应保持供电、线缆不动；不要在运行中要求断电。轮询间继续沟通，避免忙循环。
11. **WAIT_RELOAD／WAIT_RESOURCE_RELOAD**：只有这里的后台结束凭据允许提示物理操作。按返回的 `cold_reload_steps`：断 USB 和外部供电，等存取灯停，关机等屏幕／灯全灭，取电池至少一分钟，再装回开机。等待用户确认正常取景，重新接线并选择“影像传输（MSC）”（即海量存储模式）后，用 `answer --kind reboot` 提交 `{"confirmed":true}`。资源阶段可能需要额外一次重开，按实际状态引导。
12. **READY_CONTINUE**：用 `start --operation continue`。安装续接可能包含剩余写入，需同一方案授权和当前电量，带 `--confirmed --battery <实际百分比>`；原厂恢复的核验只读，不需要新的写入确认。程序会核验冷启动证据，用户说“重启了”不能替代核验。
13. **PHYSICAL_CHECKS**：后台读写已结束，可让用户拔下 USB 并保持相机开机。分别取得所有已装槽位的名称／预览、拍摄／回放、原有外观的反馈。若启用附加功能，也核对其实际效果。用 `answer --kind checks` 提交 `{"preview":true,"capture_playback":true,"original_looks":true}`；启用的附加功能再加对应 `fl23`／`sound`／`vertical`／`plugin` 布尔结果。失败必须记录 false。
14. **COMPLETE** 才能宣布本次安装完成。**NEEDS_REVIEW** 停止自动执行，保留失败事务、读日志和导出诊断；不能自动重复写入、清空状态或用恢复原厂作为通用重试手段。完成离线测试不等于实机安装或试拍通过。

## 用户主动调整时

从返回的 `alternatives.profiles` 选择实际存在的库名称。支持富士与理光混搭，目标为 1–6 个槽位，每个槽位一个滤镜；不能安装七个或使用槽位 7。用户的“1.xxx 2.xxx … 6.xxx”中的数字就是目标自订槽位，不是库列表序号。用户明确给出完整清单或说“只装”时，仅安装列出的槽位，不用默认值补齐；清单缺号且意图不清时先澄清。

“第五个换成 Eterna”属于局部修改：读取当前 `plan.looks`，修改槽位 5，保留本次其余目标和附加功能，再提交完整目标列表。“只装前三个”则从当前计划筛选槽位 1–3，不重新挑选默认滤镜。“加上快门声”只更新 `extras.sound`，保留当前滤镜配置。已有自定义方案时，只有用户明确要求恢复默认组合才重建上述六款列表。

以下是“只装槽位 1 的 Classic Neg 与槽位 2 的 Eterna，并加快门声”的完整配置示例，不能把它误作其他局部修改的通用参数：

```json
{"looks":[{"slot":1,"profile":"Classic Neg."},{"slot":2,"profile":"Eterna"}],"extras":{"sound":true}}
```

保存为 UTF-8 JSON 后调用 `python "<helper>" --session "<session>" configure --file "<config.json>"`，检查返回方案再展示给用户。`looks` 是完整的目标槽位列表，未列出的槽位不再属于本次安装目标，机身现有内容保留；但此前若执行原厂恢复，六槽已按恢复规则设为 ST，不能承诺找回旧配方。`extras` 可包含 `fl23`、`sound`、`vertical`、`plugin` 的布尔值，省略的项保持原配置。工具会校验文件、更新方案；开始安装后不能修改原计划。

## 诊断与隐私

`diagnostics --output "<new zip path>"` 只导出公开摘要，不含固件、机身校准、序列号、照片或原始私有日志，也不会上传。完整原软件日志保留本机，必要时读取。工具不下载／分发完整固件，不把用户相机数据加入项目或技能包。
