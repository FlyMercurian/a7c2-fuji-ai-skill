# A7C2 富士／理光 预制滤镜精简技能包

这是 Windows 10/11 x64 独立分享包，只支持 Sony A7C II（ILCE-7CM2）机身固件 2.01。ZIP 只保留 15 款预制滤镜的选择、驱动准备、安装、续接和核验，共用一个后台程序。不包含桌面界面、RAW/DCP 转换、音频、竖屏、插件或原厂恢复功能；无需克隆源码、安装 Python 或下载原项目。

1. 解压整个 ZIP，保留 `a7c2-fuji-install` 文件夹内的全部内容，尤其是 `assets/runtime`。不要在压缩包内直接运行。
2. 将整个 `a7c2-fuji-install` 文件夹放入支持技能的 AI 工具的技能目录；也可将其中的 `SKILL.md` 交给能读取本地文件、执行本地命令的 AI。普通网页聊天仅上传说明文件无法执行本机安装。
3. 对 AI 说：“使用 a7c2-fuji-install 安装滤镜”。未指定时默认自订 1 Classic Neg、2 Classic Chrome、3 Nostalgic Negative、4 Velvia、5 GR 正片、6 GR 负片。可从富士 11 款、理光彩色 4 款自定义最多 6 个。
4. 按 AI 当前步骤操作；USB 方式选择相机界面的“影像传输（MSC）”，即海量存储模式。不要在写入时拔线或取电池。

包内仍有 EXE/DLL：它们负责实际相机通信与安装，不需要用户打开软件窗口。首次调用自动定位随包程序，进度保存在接收者自己的 `%LOCALAPPDATA%\A7C2Tools`，不写进分享包。开始相机安装后不要移动技能文件夹；下次调用会续接原计划，不会重置进度。请解压到新目录，不覆盖旧完整版。精简版使用独立配置，仅续接自身事务；已有未完成写入时保留其原运行包和全部记录；若提示缺失原路径，先恢复原路径，不另建会话重放写入。

可在 PowerShell 中运行以下离线自检（将路径替换为实际解压位置）：

```powershell
& 'D:\Skills\a7c2-fuji-install\scripts\guide.cmd' doctor
```

此命令不打开 USB、不写相机。离线检查通过不代表实机安装通过。相机写入仅由 AI 按技能状态步骤显式启动；管理员弹窗由使用者本人处理。

安装及异常复核都通过脚本进行，不要求打开桌面程序。遇到待复核记录时，AI 先运行 `review` 离线核对，只有返回 `can_apply=true` 才能运行 `review --apply` 返回原步骤。此命令保留原请求和日志，不重试相机操作；涉及写入且结果未知时仍停止并导出诊断。缺日志或当前 MTP 身份不能证明未接触相机，也不存在必须手动去 GUI “结案”的步骤。

分享这个 ZIP 即可。不要把自己的 `settings.private.json`、日志、诊断、相机会话或备份加进去。源码与后续更新：[FlyMercurian/a7c2-fuji-ai-skill](https://github.com/FlyMercurian/a7c2-fuji-ai-skill)。许可及来源见 `LICENSE`、`assets/notices.md`、`assets/notices.zh-CN.md` 和 `assets/licenses`。滤镜是拟合风格，不保证等同原厂色彩。

## English

This preset-only, single-runtime Windows 10/11 x64 ZIP supports Sony ILCE-7CM2 firmware 2.01 only. Extract the entire folder, including `assets/runtime`, and load `SKILL.md` in an AI tool able to read local files and execute local commands. No source checkout or Python installation is required. Invoke the skill and follow one camera step at a time. Select “Image Transfer (MSC)” for USB. `scripts/guide.cmd doctor` validates the bundled library offline without opening USB. Per-user progress lives in `%LOCALAPPDATA%\A7C2Tools`; do not move an installation with an active transaction or share its state. Offline validation does not establish physical camera acceptance. Default slots are Classic Neg., Classic Chrome, Nostalgic Neg., Velvia, GR Positive Film and GR Negative Film; up to six choices can be customized from the 15-profile library. See the bundled notices and licenses for attribution.

This edition retains driver preparation, preset installation, cold reload, readback verification and offline review. It omits the desktop GUI, RAW/DCP conversion, audio, portrait overlays, plugins and factory reset. Extract to a new directory and retain any old package required by an unfinished transaction; it does not migrate old write jobs. The bundled EXE/DLLs run headlessly and require no manual GUI operation.
