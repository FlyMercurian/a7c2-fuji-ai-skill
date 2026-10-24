# A7C II Tools 3.0 · AI Skill

[English](README.md) · **简体中文**

给 **Sony A7C II（ILCE-7CM2）固件 2.01** 使用的 AI 技能版安装向导，基于 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) 修改。本项目围绕 `a7c2-fuji-install` 技能整理安装流程：告诉 AI 你的需求，由它一步一步带你完成相机操作。

底层使用上游 A7C II Tools 3.0 桌面工具，支持自定义创意外观、FL2／FL3、电子快门声音、竖屏显示和恢复原厂功能。本项目调用其完整 Windows 安装包执行安装。

## 快速开始：让 AI 带你安装

1. 在 **Windows 10／11 x64** 电脑上[下载本项目](https://github.com/FlyMercurian/a7c2-fuji-ai-skill/archive/refs/heads/main.zip)并解压。
2. 从[上游 Releases](https://github.com/QAQLeonard/a7c2-fl23-research/releases) 下载**完整 Windows 安装包**（`A7C2Tools-Windows-x64.zip`）并整包解压。保留 `A7C2Tools.exe`、`_internal` 和 `Profiles` 在同一目录，不要只拷出 EXE。
3. 用能读取本地文件、执行命令的 AI（例如 Codex）打开本项目文件夹。把下面的提示词发给它，让它准备 Python 环境并安装技能；本项目和 Windows 安装包的解压目录都需要保留在本机。

**第一次使用，把这段话发给 AI：**

```text
请读取当前项目的 skills/a7c2-fuji-install/SKILL.md，帮我准备所需环境并安装这个技能，然后按默认配置带我给 A7C2 安装富士风格外观。每次只告诉我当前需要做什么，等我反馈后再继续。
```

**已经安装过技能，直接说：**

```text
使用 $a7c2-fuji-install，按默认配置带我安装 A7C2 富士风格外观。
```

默认将**经典负片、经典正片、怀旧负片、Astia、Provia、Velvia** 安装到自订 1–6，替换这些槽位原有内容。无需逐款选择；AI 会先确认机型、固件版本，再带你连接、准备驱动、安装、断电重开和检查效果。

想调整时直接告诉 AI，例如“第五个换成 Eterna”“只装前三个，保留其他槽位”或“加装快门声”。其他富士／理光风格、竖屏、FL2／FL3 和 Lightroom 插件也可选，默认不启用附加功能。外观为拟合的富士风格，不代表与富士官方色彩完全一致。

当前 AI 向导为 **Windows 预览**，仍需实机验收。相机上的操作由你按提示完成；遇到异常，先把现象告诉 AI，不要反复重试写入。

## AI 安装对话示例

下面展示了从确认机型和固件，到检查驱动、在恢复前确认影响的分步对话。截图用于说明交互方式，不代表完整安装或实机验收已经通过。

![AI 引导安装 A7C II 富士风格外观的对话示例](docs/images/ai/gpt.png)

## 支持的机型与注意事项

> [!IMPORTANT]
> **本工具只支持 Sony A7C II（ILCE-7CM2），固件 2.01。**其他机型（包括初代 A7C、A7 IV、A7CR、A7R V、A6700、A7 V 等）及其他固件版本均不支持，请不要尝试。

> [!IMPORTANT]
> 本工具会修改相机固件中的程序和设置。使用 AI 向导时，按它当前给出的步骤操作，并在写入前提供真实的相机反馈和当前电量。遇到软件报错时，**先导出诊断包，不要反复重试写入**。手动使用软件前，请先阅读[上游操作指南](https://github.com/QAQLeonard/a7c2-fl23-research/blob/main/README.zh-CN.md#操作指南)。

如果相机以前安装过本项目，向导可能要求先恢复原厂功能。**恢复会将自订 1–6 设为 ST，不会找回旧配方**；请先保存需要的参数，确认影响后再继续。

## 更多说明

- [上游完整说明、功能介绍与常见问题](https://github.com/QAQLeonard/a7c2-fl23-research/blob/main/README.zh-CN.md)
- [Windows 安装包与其他上游下载](https://github.com/QAQLeonard/a7c2-fl23-research/releases)
- [技能说明](skills/a7c2-fuji-install/SKILL.md)与[本地开发／环境准备](docs/zh-CN/development.md)
- [第三方来源与许可](docs/zh-CN/notices.md)

## 项目来源、致谢与许可

本项目基于 **[QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)** 修改而来。感谢原作者 **[QAQLeonard](https://github.com/QAQLeonard)** 及上游贡献者提供相机研究、桌面工具和安装能力，使 AI 引导安装成为可能。本仓库侧重对话式技能与安装流程，底层相机工具来自上游项目。

代码沿用 [MIT 开源协议](LICENSE)，保留上游版权声明、许可文本及第三方许可说明。固件、商标和第三方组件仍归各自权利人所有，详见[来源与许可](docs/zh-CN/notices.md)。
