# Edge 版的平台边界与本地通信

核查日期：2026-11-11。以下依据当日可访问的官方资料；这是功能边界说明，不是平台授权或法律合规认证。

## X 页面操作

[X 自动化规则](https://help.x.com/en/rules-and-policies/x-automation)明确列出：

> Use non-API-based forms of automation, such as scripting the X website.

该句位于禁止事项中。规则还对 AI 自动回复机器人的部署要求事先书面批准。[X 服务条款](https://x.com/en/tos)当日页面标明自 2026-10-09 生效，限制未经书面许可的抓取和非公开接口访问。

本工具仅生成待用户审阅的草稿，不执行自动发帖；这与自动回复机器人有区别。但官方资料没有明确批准“用户点一下扩展便由脚本写入 X 回复框”这一例外，也没有给本工具平台授权。

因此，本次 V1.2 采用用户要求的人工替代方式：**生成草稿 → 用户编辑或审阅 → 复制／手动填充 → 用户亲自粘贴至 X 回复框并发送**。扩展不会写入、点击或合成输入事件操作 X 回复框，不会自动点赞、关注或发布。界面中的手动填充须解释为复制草稿及粘贴指引，不应宣传为已实现自动写入。

详情识别仅检查用户当前前台帖子已渲染的最少文本，不遍历时间线、不请求私有接口、不访问 Cookies、不后台批量抓取；无法确定原帖时采用用户主动粘贴文字的方式。这些技术限制不能当作 X 已授权 DOM 读取的证明。自动读取的许可边界仍需平台确认，用户也可使用原有剪贴板工作流。

## 为什么选择 Native Messaging

[Microsoft Edge 官方 Native Messaging 文档](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging)提供浏览器扩展与已安装 Win32 程序之间的标准输入输出通道。相比 localhost HTTP 服务，本版本无需常驻监听端口，不需要把本地认证令牌或 API Key 放入浏览器。

- 扩展 ID 固定为 `pibjjmjbipbifeddoahjagcinihkcgnf`；manifest 中的公钥是公开身份材料，不是 API 密钥。
- 主机名为 `com.suishou.reply`，安装 manifest 仅允许 `chrome-extension://pibjjmjbipbifeddoahjagcinihkcgnf/`。
- 安装器仅写当前用户 HKCU 的 Microsoft Edge NativeMessagingHosts 注册项，安装前保存原值；卸载仅在注册项仍属于本包时恢复，不覆盖别的安装新写入的值。
- 主机校验调用 origin、动作、字段类型、长度、帖子 URL／ID／作者关系；协议不接受浏览器提供的密钥、任意接口地址、系统提示词或文件路径。
- 内容脚本通过扩展 service worker 转发消息，不能直接调用本地主机。原网页不能获得主机 API 或 DeepSeek 密钥。
- API Key 继续由本机 Windows Credential Manager 保存；模型名从既有非秘密设置读取。

Native Messaging 的 origin 约束由浏览器实施，并由主机复核；它不是抵御同一 Windows 用户下恶意本地进程的密码学身份认证。安装目录应由用户妥善保管，不要随意替换其中的程序和扩展文件。

## 生命周期与请求成本

[Chromium service worker 生命周期说明](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)提示 worker 可能随时终止，运行中的 Native Messaging 连接可维持它。实现仍须处理断开、取消、超时和过期结果，不因自动重连而重复付费请求。

开启自动生成会把当前帖子正文发送到 DeepSeek，可能产生费用；默认关闭，不自动恢复已失败的请求。同一内容和风格优先使用会话缓存，用户主动重新生成才强制请求。关闭开关、离开当前帖子或结束连接会取消本地等待；已经由 DeepSeek 接受的请求仍可能计费。

真实 X 网站适配、平台授权和模型内容质量，均不能由离线 DOM 测试或模拟 API 测试证明。交付报告应分别列明已执行的模拟测试、浏览器本地样例测试和仍待人工完成的真实站点检查。
