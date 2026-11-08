# 随手回实现计划

**目标**：原生 Windows 托盘应用，监听用户主动复制的推文，异步生成一条中文回复并展示在不抢焦点的浮窗。

**架构**：Python + PySide6 Widgets / QtNetwork。Windows Credential Manager 使用系统 API；本地 JSON 仅保存模型、风格、主题。不保存推文历史，不启动自动监听，不自动重试。HTTP 目的地固定为 DeepSeek 官方域名。

## 模块与接口

- `suishou/api.py`：`DeepSeekClient(QObject)`，`succeeded(int,str,dict)` / `failed(int,str)`，`generate(request_id,text,key,model,style,previous='')`、`cancel()`；非阻塞网络、超时、错误、token。
- `suishou/config.py`：`Settings(model='deepseek-flash',style='自然',theme='dark')`、`SettingsStore.load()/save(settings)`，允许字段白名单。
- `suishou/credentials.py`：`CredentialStore.get()/set(key)/delete()`，无明文降级。
- `suishou/ui.py`：`ReplyWindow` / `SettingsDialog`，轻量原生界面、拖动、深色/浅色、不抢焦点。
- `suishou/clipboard.py`：文本资格与敏感检测，单独可测试。
- `suishou/controller.py`：监听状态、350ms 防抖、取消旧请求、请求代号、内存哈希去重、自写剪贴板抑制、托盘。
- `suishou/main.py` / `main.py`：启动、单实例、首次配置、无密钥离线演示。
- `scripts/build.py` / `start.bat` / `build.bat`：安装隔离依赖、双击启动、Windows EXE 打包。

## 实施与验证

1. 编写并运行敏感输入、去重、最新结果优先、暂停、复制循环等失败测试，然后实现控制流程。
2. 并行实现 API/凭据、独立 UI、交付脚本与 README；各模块拥有独立文件。
3. 用模拟服务端完成请求协议与错误测试；不使用用户密钥或真实推文。
4. 运行 Qt 集成测试，通过真实 QClipboard 模拟复制→请求→显示→复制，检查原文不被改写。
5. 实际运行 UI 并截图检查，构建单文件 EXE，再执行 EXE 自检和启动检查。

## 必须覆盖的边界

- 新复制内容为敏感信息/文件时，取消之前尚未完成的任务。
- A→B→A 和延迟返回不能覆盖当前结果；相同内容只有手动换一条可再请求。
- 设置界面输入或粘贴密钥期间暂停监听；测试连接有独立网络客户端。
- 网络错误、超时、无余额、无效响应不泄露服务端原始内容，不自动重试。
- 退出时取消活动网络请求；关闭浮窗仅隐藏。

## 完成依据

测试报告记录实际执行结果。没有真实 API Key 时，仅声明模拟流程及官方协议验证通过，不声称真实账号调用成功。

## 实现记录

- 核心模块、原生 UI、启动/打包脚本均已实现；采用 QtNetwork 异步请求，不使用额外 HTTP SDK。
- 2026-11-08：85 项单元与集成测试通过；原生 Qt + 本地 HTTP 的 19 项完整流程检查通过。
- 去重只保存本次运行内的 SHA-256 摘要；当前原文/回复仅保留在内存，用于显示与换一条。
- 设置打开时暂停，关闭后保持暂停，避免密钥仍在剪贴板时立即恢复上传。
- 独立代码审查提出的剪贴板历史恢复与演示启动问题已修复；回归测试覆盖前者。
- 打包采用受控 PATH，排除开发机其他软件的同名 DLL 污染；最终产物另运行 EXE 自检。
