# 官方热点来源与验证记录

验证日期：2026-11-09（Windows / Python 3 / PySide6 QtNetwork）。这是当次环境的实际观察，不保证每次运行、每个地区或每个时段都可访问。

## 固定公开来源

| 来源 | 固定请求地址 | 内容与日期字段 |
| --- | --- | --- |
| OpenAI | <https://openai.com/news/rss.xml> | RSS `title`、`pubDate`、`link`、`description` |
| Google DeepMind | <https://deepmind.google/blog/rss.xml> | RSS `title`、`pubDate`、`link`、`description` |
| OpenAI Agents SDK | <https://api.github.com/repos/openai/openai-agents-python/releases?per_page=20> | Releases `name` / `tag_name`、`published_at`、`html_url`、`body` |
| Anthropic Claude Code | <https://api.github.com/repos/anthropics/claude-code/releases?per_page=20> | Releases `name` / `tag_name`、`published_at`、`html_url`、`body` |

这些请求不使用 API key、Authorization、Cookie、登录状态或用户输入。Qt 自动 Cookie 加载、保存和认证复用均设为 Manual；重定向不跟随。不会抓取搜索结果、第三方搬运、社交帖子或任意用户提供的 URL。

GitHub 的 [List releases 官方说明](https://docs.github.com/en/rest/releases/releases#list-releases)确认公开发布信息可公开读取，并列出 `published_at`、`draft`、`prerelease`、`body` 等字段。匿名请求仍可能限流。

## 实际探测结果

1. 沙箱内 Python 直连四个来源均遇到 Windows `WinError 10013`（网络权限限制），不代表来源宕机。
2. 已授权的沙箱外 Python 公开只读探测：
   - OpenAI RSS：HTTP 200、832,876 字节、1,368 条原始条目，可解析；最新条目日期为 2026-11-06。
   - DeepMind RSS：HTTP 200，`Content-Encoding: gzip`，压缩响应 18,849 字节，解压后 100 条。最近一条的摘要为空；空摘要条目被拒绝，不从标题编造摘要。
   - 两个 GitHub REST Releases 端点：HTTP 403，响应为匿名 rate limit exceeded。
3. 生产 `NewsClient` 的 QtNetwork 集成运行（启用系统代理配置）：四个固定端点均 HTTP 200，3.01 秒返回 30 条合格动态，包含 OpenAI、DeepMind 和 Claude Code。SDK 预发布默认排除；不能据 HTTP 200 推断必有符合主题及日期要求的条目。
4. 不显式修改代理配置的第二次 QtNetwork 运行：`usesSystemConfiguration()` 已为 True；两个 RSS HTTP 200，两个 GitHub API HTTP 403，7.75 秒返回 30 条合格动态。可用性在两次运行间发生变化，不能把差异归因于代理配置。
5. 网页读取工具打开两个 RSS 端点时报告不支持 XML content-type，打开两个 API 端点时报告不可访问；实际生产可用性以直接 QtNetwork 集成结果为准。

另探测了两个官方 GitHub `releases.atom` 地址，均 HTTP 200 且包含完整更新说明，但只有 `updated` 时间、没有精确预发布标志。本版未把它们加入生产来源，避免把更新日期冒充发布日期。Google Research RSS 也 HTTP 200，但示例 description 只有分类名称，未加入来源。

## 返回事实与生成评论的界限

`NewsClient.succeeded(request_id, items)` 中每条记录包含：

```python
{
    'title': '来源原始标题（清理标记后）',
    'published_at': '2026-11-08T08:00:00+00:00',
    'url': 'https://官方域名/原始条目',
    'summary': '官方 feed description 或 release body 的纯文本摘录',
    'provider': '来源名称',
    'topic': '匹配的界面主题',
}
```

- 标题、日期、链接和摘要全部必填。只保留抓取时刻前 14 天以内（含边界）、非未来、含时区的原始发布时间。
- 标题最多 220 字符，官方摘要 / 更新说明摘录最多 1,200 字符；截断标记为 `…`。这里的 summary 是来源摘录，未调用模型生成，不声称已阅读或独立核验全文。
- URL 必须为 HTTPS、精确官方域名；GitHub 还必须位于指定仓库的 `/releases/tag/` 路径下。拒绝用户名密码、非标准端口、目录穿越和不可信来源。
- 删除 HTML 标记、script/style 等隐藏内容和 Markdown 装饰，保留代码标识符；明显指令注入文本会整条拒绝。这是输入清理，不代表任何外部文本可以作为模型指令。后续提示词仍须把字段当作引用材料。
- Releases 始终排除 draft；默认排除 prerelease，只有显式传入 `include_prereleases=True` 才接收预发布。没有发布日期时不会拿 `updated_at` 补齐。
- “已验证”指来源域名、结构、日期和必需信息通过校验，不表示软件独立证实了发布者的每项主张。界面应区分“官方来源 / 摘录”和“AI 生成评论”。

主题筛选使用来源类别与标题、摘要、RSS 分类关键词；不会把同一组新闻无条件返回给每个主题。Agents SDK 支持 AI Agent、GitHub开源和 AI工具；Claude Code 支持 AI编程与 AI工具，未因其在 GitHub 发布就标为开源产品。通用新闻按内容匹配 AI工具、模型更新、AI编程、AI Agent 或行业观察。无匹配内容时明确提示重试或选择“随机”。

## 有界网络与取消

- 每次最多 4 个固定请求、最多 3 个同时进行，无自动重试或分页。
- 每个来源最多 2 MiB 应用层响应数据；总预算 6 MiB。超出时最多额外读取 1 字节用于判定，立即停止相应请求或本次抓取。
- 默认每个请求 10 秒、整体 18 秒。构造参数即使放宽，也被分别限制在 15 秒和 25 秒。
- 一个来源失败、限流、空摘要或只有旧内容不会阻止使用其他来源。
- 整体到期时可返回已取得的合格条目；完全没有材料时只报友好错误，不生成标题、摘要或事实作为替代。
- `cancel()` 立即使当前请求失效并中止未结束请求，不发送成功或失败信号；晚到回调被忽略。新的 fetch 会先取消旧请求。
- 最多返回 30 条、按发布时间降序、按原始 URL 去重。不持久保存新闻，不把旧缓存冒充实时内容。

## 真实返回样本

以下是 2026-11-09 第二次 QtNetwork 运行中实际取得的完整短条目，可用于审核截图或离线演示。它不是运行时兜底数据；以后超过 14 天即不应再显示为近期热点。

```json
{
  "title": "Speeding up planning decisions with AI",
  "published_at": "2026-10-30T14:18:30+00:00",
  "url": "https://deepmind.google/blog/speeding-up-planning-decisions-with-ai/",
  "summary": "Google DeepMind and UK government work together to reduce planning assessment times",
  "provider": "Google DeepMind",
  "topic": "行业观察"
}
```

## 自动化验证

`tests/test_news.py` 使用确定的 UTC 时钟、真实解析器和模拟 Qt 网络回复，覆盖官方来源成功、主题不符、过期/未来/缺日期、非法 URL、空摘要、坏 XML、实体声明、明显注入、草稿与预发布、Markdown 事实保真、极端日期、来源不可用、Cookie/认证/重定向策略、并发请求数、大小限制、总字节预算、取消、晚到回调与整体超时。测试不访问外网，不调用 DeepSeek，不读取真实凭据。
