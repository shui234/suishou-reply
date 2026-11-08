# 随手回 | SuishouReply

**少花时间组织评论，更轻松地参与 X（Twitter）讨论。**

随手回是一款 Windows 桌面中文回复助手，面向 **X 账号冷启动、日常互动和评论效率提升**。看到想参与的热门话题，主动复制推文正文，即可通过 DeepSeek 得到一条简短回复；选择自然、犀利或幽默的语气，检查内容后自行复制、粘贴和发布。

提示词着重减少 AI 模板腔、空洞附和和营销式表达，帮助你更快写出适合当前讨论的评论。生成内容仍需由你审核和修改。应用不承诺涨粉效果，也不提供批量营销功能。

[下载 Windows 版](https://github.com/shui234/suishou-reply/releases/tag/v1.0.0) · [更新记录](CHANGELOG.md) · [测试报告](docs/TEST_REPORT.md) · [维护与发版](docs/UPDATING.md)

## 界面预览

![随手回深色浮窗：监听状态、三种语气、回复正文与复制按钮](docs/preview-dark.png)

*真实应用界面截图，来自原生 EXE 自检的离线模拟流程。原文、回复和 token 数为合成数据，不是付费 DeepSeek 调用结果。*

## 核心功能

| 功能 | 使用方式 |
| --- | --- |
| 复制后生成 | 手动开启监听，再复制一段推文正文，得到一条中文回复 |
| 三种语气 | **自然**：平实参与；**犀利**：补充不同角度、指出漏洞；**幽默**：轻松表达、不硬玩梗 |
| 轻量浮窗 | 可拖动、不抢输入焦点；系统托盘随时找回，支持深色与浅色主题 |
| 手动换一条 | 针对当前原文再次生成，提示模型换一个角度 |
| 复制回复 | 只复制回复正文，由你检查、修改并发布 |
| 默认暂停 | 每次启动和进入设置时暂停；关闭设置后需要手动开启 |
| 安全保存密钥 | API Key 交给当前 Windows 用户的凭据管理器，本地配置不保存明文密钥 |

提示词要求最多两句话、通常 30～80 字，并避免编造亲历、无依据判断真假。实际措辞、事实准确性与长度仍取决于模型。

## 适合哪些场景

- **X 账号冷启动**：找到与你关注领域相关的讨论，减少从空白开始写评论的时间。
- **日常互动**：浏览关注列表时，快速整理认可、补充或质疑的表达。
- **参与热门话题**：你自己选择话题和推文，随手回帮助组织一条贴合原文的回复。
- **调整表达方式**：在自然、犀利和幽默之间切换，找到更符合自己语气的说法。

应用通过系统剪贴板接收文字，不登录 X、不读取网页、不打开评论框，也不自动操作账号或发帖。每条回复是否使用、如何修改、何时发布，都由你决定。

## 安装 Windows 版

运行版无需安装 Python，也无需管理员权限。当前构建为 Windows x64，在 Windows 11 x64 上完成验证。

1. 打开 [v1.0.0 Releases 页面](https://github.com/shui234/suishou-reply/releases/tag/v1.0.0)，在 Assets 中下载 `SuishouReply-1.0.0-Windows.zip`。源码与发布包公开提供，无需 GitHub 登录即可下载。
2. 将 ZIP **完整解压**到一个目录，保留构建信息与许可文件。
3. 双击解压后的 `SuishouReply\dist\SuishouReply.exe`，首次启动会打开设置。

发布包以 Releases 页面实际提供的资产为准；GitHub 自动生成的 Source code 压缩包是源码，不包含可直接运行的 EXE。

发布包包含源码和 `dist/` 运行目录。当前 EXE 未做代码签名。若 Windows SmartScreen 提示未知发布者，请先核对下载来源及 `dist\SHA256SUMS.txt` 中的校验值，无需关闭系统安全防护。可在解压后的 `SuishouReply\dist` 目录运行：

```powershell
Get-FileHash -LiteralPath .\SuishouReply.exe -Algorithm SHA256
Get-Content -LiteralPath .\SHA256SUMS.txt
```

单文件 EXE 首次启动会将运行库解压到系统临时目录，可能略慢。关闭浮窗只会隐藏窗口；可在系统托盘找回，或从托盘菜单退出。

## 配置 DeepSeek 并开始使用

1. 在 [DeepSeek 官方平台](https://platform.deepseek.com) 创建自己的 API Key，粘贴到应用设置的密钥输入框。不要将密钥写入源码、截图、Issue 或聊天记录。
2. 检查模型名，点击 **「测试连接」**。它使用输入框中的密钥发送固定测试文本，不发送当前剪贴板；会产生一次正常 API 调用。应用不赠送 API 额度。
3. 测试成功后点击 **「保存设置」**。密钥存入 Windows 凭据管理器，监听仍保持暂停。
4. 回到浮窗，点击 **「已暂停」** 开启监听。
5. 在浏览器中主动复制一段 **12～3000 字**的推文正文。开启监听不会处理此前已经存在的剪贴板内容。
6. 阅读生成的回复，核对事实、语气及上下文。需要不同角度时点 **「换一条」**。
7. 点击 **「复制回复」**，自行粘贴到 X 评论框，按需修改，再手动发布。

默认模型名为 `deepseek-flash`；可在设置中填写自己账户可用的模型名。当前实现固定请求 `https://api.deepseek.com/chat/completions`，关闭思考模式、非流式返回，30 秒超时。账户支持的模型、余额和服务状态以 DeepSeek 平台为准。

接口参考：[官方接入文档](https://api-docs.deepseek.com/)、[思考模式参数](https://api-docs.deepseek.com/guides/thinking_mode/)、[错误码说明](https://api-docs.deepseek.com/quick_start/error_codes/)。

## 不用密钥，先试离线演示

在解压后的 `SuishouReply\dist` 目录打开 PowerShell，运行：

```powershell
& .\SuishouReply.exe --demo
```

也可双击解压后的 `SuishouReply\demo.bat`。演示窗口有「离线演示」标记，使用固定模拟回复和模拟 token 数，不访问 DeepSeek、不读取或写入真实密钥，也不保存设置。先开启监听，再复制一段示例文字：

> 现在的 AI 工具越来越多，但真正难的似乎不是找到工具，而是想清楚自己究竟要解决什么问题。

演示可检查复制、浮窗、换一条及复制回复的操作流程，模拟回复不代表模型对当前文字的判断。

## 剪贴板、隐私与请求行为

**开启监听后，符合条件的新剪贴板文本会发送给 DeepSeek；应用无法判断文字是否来自 X。复制私人内容前请暂停监听。**

- **输入过滤**：只处理 12～3000 字文本，跳过图片、文件、纯链接、路径、纯数字、邮箱、明显代码及部分疑似密钥、密码和验证码。规则可能漏掉敏感内容，也可能误拦普通文字，并非完整的敏感信息识别系统。
- **发送范围**：发送所复制的文本、回复指令，以及点击「换一条」时的上一条回复。生产服务地址固定为 DeepSeek 官方 HTTPS 接口，不支持自定义 API 地址，不跟随重定向。
- **本地存储**：API Key 保存在 Windows 凭据管理器的 `SuishouReply/DeepSeekAPI` 中，保存失败不会降级为明文，可在设置中删除。`%LOCALAPPDATA%\SuishouReply\settings.json` 仅保存模型名、风格和主题。
- **内容留存**：不保存推文或回复历史，不写入原文、回复或密钥日志。当前原文与回复暂存于运行内存，用于显示和换一条；暂停或退出会清空应用内当前内容。Windows 剪贴板历史、同步及 DeepSeek 的数据处理受各自设置和政策影响。
- **请求调度**：350 毫秒防抖，连续复制优先处理最新内容；新内容或暂停会取消旧任务，过期结果不会覆盖当前内容。会话内通过摘要去重，复制回复不会循环触发生成。
- **调用与计费**：网络错误不会自动重试。需要重新生成时手动操作；取消本地请求不能保证服务端尚未处理或计费。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| 复制后没有回复 | 确认监听已开启，再重新复制；检查长度及过滤规则。开启监听不会发送旧剪贴板 |
| 提示内容已处理 | 相同内容在本次运行内不会自动重复调用，需要时点击「换一条」 |
| API Key 无效 | 在设置中输入正确密钥，测试成功后保存 |
| 余额不足 | 到 DeepSeek 官方平台检查自己的账户余额 |
| 请求过于频繁 | 稍后主动重试；应用不会自动重复请求 |
| 超时或网络错误 | 检查本机网络，在设置中重新测试连接 |
| 保存设置失败 | 检查当前用户的 Windows 凭据管理器及本地配置目录是否可用 |
| 找不到浮窗 | 展开 Windows 系统托盘隐藏图标，点击随手回 |
| Releases 页面显示 404 | 检查仓库地址与版本号，或从仓库首页进入 Releases |

错误界面不会直接显示服务端原始返回正文或密钥。

## 从源码运行

实际开发与验证环境为 **Windows 11 x64、Python 3.14.4**。启动脚本接受 64 位 Python 3.11～3.15，此范围依据固定 Qt wheel 的版本元数据，未逐一验证所有版本。

1. 从 [Python 官方网站](https://www.python.org/downloads/windows/) 安装 64 位 Python，保留 Python Launcher 或将 Python 加入 PATH。
2. 克隆或下载完整源码，双击 `start.bat`。
3. 首次运行会创建项目内 `.venv`，联网安装固定依赖，成功后保存安装标记；后续启动检查环境后直接运行。

路径可包含空格和中文。移动源码目录后若虚拟环境失效，可重命名项目内 `.venv` 并重新启动；Windows 凭据管理器中的密钥不会随项目目录移动而删除。

| 技术 | 用途 |
| --- | --- |
| Python 3.14.4 | 已验证的运行与构建环境 |
| PySide6-Essentials / Shiboken 6.12.0 | 原生 Qt 窗口、托盘与剪贴板，无需 Qt Addons |
| QtNetwork | 异步请求、取消与 30 秒超时 |
| Windows Credential Manager + `ctypes` | 调用 Windows 系统接口保存密钥 |
| PyInstaller 6.22.3 | Windows 单文件 EXE 打包 |
| pytest | 离线单元与集成测试 |

## 测试与构建

安装开发依赖并运行源码测试：

```powershell
.\start.bat --prepare-only
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest -q
```

双击 `build.bat` 可安装固定构建依赖并生成 EXE。已有完整开发环境时，也可运行：

```powershell
& .\.venv\Scripts\python.exe scripts\build.py
```

默认输出位于 `dist/`：

```text
SuishouReply.exe          # 单文件、无控制台窗口
BUILD_INFO.json           # 版本、构建环境、大小及 SHA-256
SHA256SUMS.txt            # EXE 校验值
THIRD_PARTY_NOTICES.md    # 第三方组件说明
licenses/                # 许可文本
```

检查或替换 Qt 动态库时可用 `scripts\build.py --onedir` 构建目录版，保留完整 `dist\SuishouReply\` 目录运行。两种格式使用相同应用源码。

v1.0.0 已记录 **85 项自动化测试通过、退出码 0**，以及最终原生 **EXE 19 项自检通过、退出码 0**。EXE 自检覆盖本地 HTTP 模拟服务、原生剪贴板、复制回复、不抢焦点及 TLS 后端；不等同于真实 DeepSeek 服务验证。详细结果、复现命令与边界见 [测试报告](docs/TEST_REPORT.md)。

**未使用真实 DeepSeek API Key，尚未验证真实账户链路、余额或模型回复质量；也未在另一台全新 Windows 电脑逐项验证。** 自检会短暂使用系统剪贴板，运行前请避开正在复制重要内容的操作。

## 后续方向

以下为计划评估的改进方向，不代表已实现功能或发布时间承诺：

- 改善敏感文本过滤与误拦提示。
- 提供由用户主动启用的快捷键。
- 改善回复长度及异常输出的提示。
- 完善无障碍体验和多显示器表现。
- 评估 Windows 代码签名。

## 第三方组件与维护

随手回的项目代码以 [MIT 许可证](LICENSE) 开源，欢迎使用、修改和贡献。第三方组件不因项目采用 MIT 而改变许可。

本项目使用 Python、PySide6 / Qt、Shiboken 和 PyInstaller，各组件适用各自许可。Qt / PySide6 的 LGPL 说明、来源及替换构建方式见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；分发构建结果时请一并保留对应源码、构建说明和许可文件。

维护者可参考 [更新与发布流程](docs/UPDATING.md) 完成验证、版本更新和 GitHub Release 发布，分发前检查见 [发布安全审查](docs/SECURITY_REVIEW.md)。
