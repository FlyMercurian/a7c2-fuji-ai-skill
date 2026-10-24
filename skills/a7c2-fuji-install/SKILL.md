---
name: a7c2-fuji-install
description: 带用户逐步为 Sony A7C II（ILCE-7CM2，固件 2.01）安装富士风格外观。使用默认六款配置，检查版本、驱动、历史事务和连接，执行本地工具，在用户完成相机操作后继续并核验；支持替换外观、部分槽位及可选附加功能。
---

# A7C II 富士外观安装向导

使用本技能目录的 `scripts/guide.py` 调用项目本地向导。该脚本的 `settings.private.json` 保存已安装项目和 Python 环境的位置；项目内的副本可自动定位项目。工具输出单个 JSON 文档，`phase`、`allowed_operations` 和 `prompt` 决定下一步。完整 USB 引擎由现有 Windows `A7C2Tools.exe --worker` 执行。

## 交互方式

- 默认安装：自订 1 经典负片、2 经典正片、3 怀旧负片、4 Astia、5 Provia、6 Velvia。默认不启用 FL2/FL3、快门声、竖屏或 Lightroom 插件。外观为拟合的富士风格，不宣称等同富士官方色彩。
- 不要求用户逐款选滤镜，不要求用户自己读完文档。展示默认清单并说明会替换自订 1–6；用一两句说明也能换其他富士／理光风格、只装部分槽位、加装附加功能。用户说“按默认安装”即接受这个明确的方案，不再反复询问选项。
- 每轮只提出当前需要完成的一项相机操作或一组紧密相关的操作，解释如何判断完成，等待真实反馈。不得编造版本、电量、断电或试拍结果。已获得的信息和授权继续有效；每次实际写入需有当前电量反馈。
- 普通用户只看到当前状态、当前操作和结果。JSON、路径、事务、USB ID 等细节留给 AI；排障确有需要时再说明。
- 用户改变配置时展示变更影响；已开始的安装沿用保存的计划，不偷偷切换为默认方案。

## 调用

以下 `<helper>` 是本技能 `scripts/guide.py` 的绝对路径。启动脚本仅需 Python 标准库；脚本会选择已配置的项目运行环境。

```text
python "<helper>" init
python "<helper>" --session "<session>" status
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
3. **CONNECT_CAMERA**：让用户关闭原软件，保留一台相机，设海量存储、数据线直连。用户完成后，提交 `{"confirmed":true}` 到 `answer --kind connected`。
4. **EXISTING_TRANSACTION**：读取列出的历史阶段。不能删除、搬走或改写状态来解除阻塞。已在等待重开的旧一键安装可用 `adopt --workspace "<old workspace>"` 续接；先向用户说明这是原计划。其他旧事务需读原软件日志、导出诊断并在原软件审查，结果未知不能重放。不能把所有历史失败都解释为驱动问题。
5. **READY_DRIVERS**：`start --operation drivers`。这会执行现有两阶段驱动准备；Windows UAC 由用户在本机处理，密码不交给 AI。相机提示“请检查所连接的设备”和盘符消失可能是正常现象；以程序结果为准。
6. **READY_STABILITY**：`start --operation stability` 运行至少两分钟的只读测试。后台异步执行，持续提供简短进度。失败后根据日志处理线材／接口／驱动，不自动循环测试。
7. **HISTORY_QUESTION**：询问是否改装，用 `answer --kind history` 提交 `{"modified":"yes"}` 或 `no`。
8. **READY_RESTORE**：旧安装需先恢复原厂功能。解释自订 1–6 将被设为 ST，旧配方不找回，保留需要的参数。取得对此影响的明确确认及当前电量，执行 `start --operation restore --confirmed --battery <实际百分比> --replace-slots`。不能把“装富士滤镜”的一般意图当成用户已经知道恢复会清空旧配方。
9. **READY_INSTALL**：展示默认清单、覆盖的槽位及可选调整，取得用户接受方案和当前电量后，执行 `start --operation install --confirmed --battery <实际百分比> --replace-slots`。如果已有接受同一清单的授权，只补问仍缺的信息。不得代替用户填 100%。
10. **RUNNING**：不要再启动其他相机操作，不要杀进程／设置写入超时后重试。用 `status` 查看进度，用 `poll` 消费已结束任务的结果。后台日志路径会返回，可读日志解释进展。用户应保持供电、线缆不动；不要在运行中要求断电。轮询间继续沟通，避免忙循环。
11. **WAIT_RELOAD／WAIT_RESOURCE_RELOAD**：只有这里的后台结束凭据允许提示物理操作。按返回的 `cold_reload_steps`：断 USB 和外部供电，等存取灯停，关机等屏幕／灯全灭，取电池至少一分钟，再装回开机。等待用户确认正常取景并重新接线后，用 `answer --kind reboot` 提交 `{"confirmed":true}`。资源阶段可能需要额外一次重开，按实际状态引导。
12. **READY_CONTINUE**：用 `start --operation continue`。安装续接可能包含剩余写入，需同一方案授权和当前电量，带 `--confirmed --battery <实际百分比>`；原厂恢复的核验只读，不需要新的写入确认。程序会核验冷启动证据，用户说“重启了”不能替代核验。
13. **PHYSICAL_CHECKS**：后台读写已结束，可让用户拔下 USB 并保持相机开机。分别取得所有已装槽位的名称／预览、拍摄／回放、原有外观的反馈。若启用附加功能，也核对其实际效果。用 `answer --kind checks` 提交 `{"preview":true,"capture_playback":true,"original_looks":true}`；启用的附加功能再加对应 `fl23`／`sound`／`vertical`／`plugin` 布尔结果。失败必须记录 false。
14. **COMPLETE** 才能宣布本次安装完成。**NEEDS_REVIEW** 停止自动执行，保留失败事务、读日志和导出诊断；不能自动重复写入、清空状态或用恢复原厂作为通用重试手段。完成离线测试不等于实机安装或试拍通过。

## 用户主动调整时

从返回的 `alternatives.profiles` 选择实际存在的库名称。用户可直接说“第五个换成 Eterna”“只装前三个”“加上快门声”；AI 将意图转为配置，无需教用户 JSON。以下只是调用示例：

```json
{"looks":[{"slot":1,"profile":"Classic Neg."},{"slot":2,"profile":"Eterna"}],"extras":{"sound":true}}
```

保存后调用 `configure --file "<config.json>"`。`looks` 是完整的目标槽位列表，未列出的槽位保留。`extras` 可包含 `fl23`、`sound`、`vertical`、`plugin` 的布尔值。工具会校验文件、更新方案；安装后不能修改原计划。

## 诊断与隐私

`diagnostics --output "<new zip path>"` 只导出公开摘要，不含固件、机身校准、序列号、照片或原始私有日志，也不会上传。完整原软件日志保留本机，必要时读取。工具不下载／分发完整固件，不把用户相机数据加入项目或技能包。
