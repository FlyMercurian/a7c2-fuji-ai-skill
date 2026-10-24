# A7C II Tools 3.0 · AI Skill

**English** · [简体中文](README.zh-CN.md)

An AI-guided installer for the **Sony A7C II (ILCE-7CM2), firmware 2.01**, adapted from [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research). This version focuses on the `a7c2-fuji-install` skill: describe what you want, and an AI agent guides you through the camera operations one step at a time.

The upstream A7C II Tools 3.0 desktop app provides custom Creative Looks, FL2/FL3, electronic shutter sound, Vertical Display and factory-function restoration. This project uses its Windows package as the installation backend.

## Quick start: let AI guide you

1. On **Windows 10/11 x64**, [download this project](https://github.com/FlyMercurian/a7c2-fuji-ai-skill/archive/refs/heads/main.zip) and extract it.
2. Download the **complete Windows package** (`A7C2Tools-Windows-x64.zip`) from the [upstream Releases](https://github.com/QAQLeonard/a7c2-fl23-research/releases) and extract the whole archive. Keep `A7C2Tools.exe`, `_internal` and `Profiles` together.
3. Open this project's folder in an AI client that can read local files and run commands, such as Codex. Use the prompt below to have it prepare the Python environment and install the skill. Keep both extracted folders available locally.

**For your first use, send this prompt to the AI:**

```text
Read skills/a7c2-fuji-install/SKILL.md in this project, prepare the required environment and install the skill, then guide me through installing the default Fujifilm-style looks on my A7C II. Tell me only what I need to do at the current step, and wait for my feedback before continuing.
```

**If the skill is already installed, just say:**

```text
Use $a7c2-fuji-install to guide me through installing the default Fujifilm-style looks on my A7C II.
```

The default installs **Classic Negative, Classic Chrome, Nostalgic Negative, Astia, Provia and Velvia** into custom slots 1–6, replacing their current contents. You do not need to pick each look. The AI first confirms your camera model and firmware, then guides connection, driver preparation, installation, cold reload and physical checks.

To change the plan, simply say "Replace the fifth look with Eterna," "Install only the first three and keep the other slots," or "Also enable shutter sound." Other Fujifilm/Ricoh looks, Vertical Display, FL2/FL3 and the Lightroom plugin are optional and are not enabled by default. The looks are fitted approximations, not a promise of identical Fujifilm color.

The AI guide is a **Windows preview** and still needs physical acceptance. Follow its prompts for camera actions; if something goes wrong, describe it to the AI instead of repeatedly retrying writes.

## Example conversation

The screenshot illustrates the step-by-step interaction, from camera and firmware confirmation to driver checks and confirmation before restoration. It does not establish that a complete installation or physical acceptance passed.

![Example of AI-guided A7C II installation](docs/images/ai/gpt.png)

## Supported camera and precautions

> [!IMPORTANT]
> **Only Sony A7C II (ILCE-7CM2), firmware 2.01 is supported.** Other models, including the original A7C, A7 IV, A7CR, A7R V, A6700 and A7 V, and other firmware versions are not supported. Do not try them.

> [!IMPORTANT]
> This tool modifies programs and settings in the camera firmware. Follow the AI's current instructions and provide actual camera feedback and battery level before writes. If the app reports an error, **export a diagnostic bundle first. Do not keep retrying the write.** For manual operation, read the [upstream step-by-step guide](https://github.com/QAQLeonard/a7c2-fl23-research/blob/main/README.md#step-by-step-guide).

If the camera has a previous installation, the guide may require restoration first. **Restoration resets custom slots 1–6 to ST and does not recover old recipes**; save any settings you need and confirm that impact before continuing.

## More documentation

- [Upstream manual, feature descriptions and troubleshooting](https://github.com/QAQLeonard/a7c2-fl23-research/blob/main/README.md)
- [Windows package and other upstream downloads](https://github.com/QAQLeonard/a7c2-fl23-research/releases)
- [Skill instructions](skills/a7c2-fuji-install/SKILL.md) and [local development / environment setup](docs/en/development.md)
- [Third-party sources and licenses](docs/en/notices.md)

## Source, acknowledgements and license

This project is modified from **[QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)**. Thank you to **[QAQLeonard](https://github.com/QAQLeonard)** and the upstream contributors for the camera research, desktop tools and installation capabilities that make this AI-guided version possible. This repository focuses on the conversational skill and installation workflow; the underlying camera tools originate from the upstream project.

The code is distributed under the [MIT License](LICENSE). The upstream copyright and permission notices, and third-party license notices, are retained. Firmware, trademarks and third-party components retain their respective rights; see [sources and licenses](docs/en/notices.md).
