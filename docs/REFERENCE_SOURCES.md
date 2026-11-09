# 普通原创的参考来源

核验日期：2026-11-09。覆盖 `suishou/inspirations.json` 的 20 个主题，共 12 个不同的官方资料页面。

这里的资料为普通原创提供可追溯的事实起点，`kind` 固定为 `reference`。它们不是“近 14 天新闻”，不能进入热点新闻时效判断，也不能被写成“今天刚发布”。`verified_at` 是本次人工浏览核验日期，不是文章发布日期。只有页面明确标注了发布日期的文章才记录该日期；其余 `published_at` 为“参考文档 · 未标注发布日期”。帮助中心的相对更新时间没有被换算成首次发布日期。

每个下列最终 URL 均通过浏览工具实际打开，并阅读与主题有关的正文；不是根据域名或标题拼接的地址。摘要采用简短中文转述，不保存网页全文，不保存价格、额度或性能数字。普通原创引用这些资料时，应把资料事实与作者由此产生的判断分开，不把主题角度说成官方结论。

| 官方页面（最终链接） | 对应主题 ID | 核验位置与使用范围 |
| --- | --- | --- |
| [Building effective agents — Anthropic](https://www.anthropic.com/research/building-effective-agents) | `tool-fit`、`automation-exceptions`、`agent-handoff`、`small-workflows` | 阅读简单方案、协调工作模型、执行反馈和停止条件段落。页面明确发布日期为 2024-12-19；也提示部分工具信息已变化，仅采用方法层面的说明。 |
| [Pricing — OpenAI API](https://developers.openai.com/api/docs/pricing) | `tool-pricing` | 阅读计费表头及分类，核实输入、输出与缓存等项目的区别。仅支持“成本需结合使用方式”的讨论，不构成免费额度或订阅套餐的证据。 |
| [Application card: GitHub Copilot inline suggestions — GitHub](https://docs.github.com/en/copilot/responsible-use/inline-suggestions) | `code-quality` | 阅读 Limitations 与 Best practices 中的代码审查、测试和项目适配说明。 |
| [Safety in building agents — OpenAI](https://developers.openai.com/api/docs/guides/agent-builder-safety) | `agent-permissions` | 阅读工具确认、结构化数据流和防护局限。该页针对 Agent Builder 且已有退役提示；只引用权限和确认原则，不推荐其作为新建项目平台。 |
| [Use Compose in production — Docker](https://docs.docker.com/compose/how-tos/production/) | `opensource-deployment` | 阅读生产配置与部署变更段落，核实日志、重启策略、重建等维护环节。不是所有开源项目的统一硬件要求。 |
| [About the repository README file — GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) | `readme-reality`、`learning-cost`、`project-signals` | 阅读 About READMEs 与 Wikis。这里只支持文档应包含哪些入口，不证明任何具体项目维护活跃、运行稳定或可复现。 |
| [Evaluation best practices — OpenAI](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | `benchmark-context`、`human-judgment`、`model-migration` | 阅读 Types of evals、How to read evals 与 Design your eval process。使用通用评测方法；页面含旧 Evals 平台退役提示，不据此推荐该平台。 |
| [Reduce hallucinations — Anthropic](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) | `hallucination-check` | 阅读允许不确定、依据原文和核对引用的建议，不据此声称幻觉已消除或捏造比例。 |
| [Prompting best practices — Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | `homogeneous-content`、`testable-requests` | 阅读 Be clear and direct、Add context、Use examples effectively。用于具体背景、约束与示例多样性，不作为内容同质化程度的统计证据。 |
| [Image generation — OpenAI](https://developers.openai.com/api/docs/guides/image-generation) | `jobs-tasks` | 阅读 Overview、生成与编辑接口、多轮编辑及输出设置。支持讨论创作任务如何拆分，不支持职业消失或效率提升百分比的结论。 |
| [Canceling your ChatGPT subscription — OpenAI](https://help.openai.com/en/articles/7232927-canceling-your-chatgpt-subscription) | `subscription-fatigue` | 阅读 Overview 与取消渠道说明。只陈述订阅管理事实；使用频率、功能重叠和注意力负担属于延伸观点。 |
| [Licensing a repository — GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) | `opensource-license` | 阅读许可证选择与文件位置说明。用于提醒核对使用条件，不判断具体项目法律适用，也不据此定义模型开放权重。 |

## 地址核验记录

浏览时发现的重定向已落实为上表及 JSON 中的最终地址：

- OpenAI 的 `platform.openai.com/docs/guides/...` 文档跳转至 `developers.openai.com/api/docs/guides/...`。
- 原 `openai.com/api/pricing/` 跳转到商业套餐页面，故未将其作为 API 价格来源；改用从官方文档导航打开的 API `pricing` 页。
- GitHub 的 `copilot-code-completion` 页面跳转到 `inline-suggestions`。
- Anthropic 的旧 `docs.anthropic.com` 文档跳转至 `platform.claude.com`；旧 `be-clear-and-direct` 页归入 `claude-prompting-best-practices`。
- ChatGPT 取消订阅帮助页的旧标题路径跳转为 `7232927-canceling-your-chatgpt-subscription`。

## 维护约定

参考资料随应用打包，生成时可直接使用本地摘要及真实链接。它不代表每次生成都重新抓取网页。后续更新资料时应重新打开页面、核对主题匹配与重定向，再更新 `verified_at`。若要写产品价格、版本新发布、性能数字或时效性判断，应另行获取相应证据，不能仅凭这份静态资料推断。
