# 更新与发布流程

适用于公开仓库 `shui234/suishou-reply`，项目代码采用 MIT 许可证。以下命令是维护模板，在源码根目录的 PowerShell 中执行；它们不会由阅读文档自动运行。将版本号改为本次计划发布的版本；如果仓库所属用户或组织变更，再调整 `$repoOwner`。需要已安装并登录 GitHub CLI；尚未登录时使用 `gh auth login --web` 完成浏览器授权，不在文档或命令中粘贴 Token。

## Edge 扩展发版

[v1.2.1 Release](https://github.com/shui234/suishou-reply/releases/tag/v1.2.1) 的运行包为 [SuishouReply-1.2.1-Edge-Windows.zip](https://github.com/shui234/suishou-reply/releases/download/v1.2.1/SuishouReply-1.2.1-Edge-Windows.zip)，包含 MV3 扩展、独立桥接 EXE、安装器、文档与对应源码子集。它不替换仍可下载的 [v1.0.0 桌面 Release](https://github.com/shui234/suishou-reply/releases/tag/v1.0.0)，也不表示 v1.1.1 完整桌面 EXE 已公开发布。

Edge 与完整桌面程序独立构建、分别命名。更新 Edge 时同步 `extension/manifest.json`、`extension/package.json`、面板版本标记、`suishou/edge_protocol.py` 的应用版本、`scripts/build_edge.py` 的版本与 Windows 版本资源，以及相关测试、文档和发布说明。Native 消息中的协议字段 `v` 不随补丁版本自动升级。

发布构建应来自选定的、已提交的完整源码。若日常工作区还有其他未提交功能，使用独立工作树从目标提交构建；不要复制脏工作区中的复用模块，也不要重置、清理或覆盖那些未提交文件。发行 ZIP 内 `source` 中的复用模块须与发布标签一致。

在干净发布工作树中，安装开发依赖后执行：

```powershell
python -m pytest -q
node --test extension/tests/*.test.js
python scripts/build_edge.py
node extension/tests/browser-smoke.cjs
python scripts/package_edge.py
```

`build_edge.py` 为 v1.2.1 写入独立的 `dist-edge-v1.2.1`，不覆盖桌面产物；`package_edge.py` 在项目上一级生成 Edge ZIP 和 SHA-256 文件。升级其他版本时应同步脚本及测试中的输出目录。检查运行文件与当前源码哈希一致、ZIP CRC 正常，并排除密钥、用户配置、原创历史、注册文件、注册备份、日志和缓存。依赖来源及许可文件保留在包内，EXE/ZIP 不提交进 Git。

Node 测试和 Edge 合成页面检查不产生付费 API 调用。合成网页、模拟模型、仿真焦点及捕获的剪贴板调用必须如实标注；不能将其写成真实 X 登录或系统剪贴板已经验收。发布说明记录实际发布提交的测试数量，不沿用包含未提交桌面功能的工作区测试总数。

源代码按仓库现有流程提交并推送后，检查标签不存在或已指向预期提交，再创建草稿 Release。下例版本仅用于展示本次命名；发布后不得移动或覆盖已有标签与同名附件：

```powershell
$repoName = 'shui234/suishou-reply'
$edgeVersion = '1.2.1'
$edgeTag = "v$edgeVersion"
$edgeAsset = "..\SuishouReply-$edgeVersion-Edge-Windows.zip"
$edgeChecksum = "..\SuishouReply-$edgeVersion-Edge-SHA256.txt"
gh auth status
gh repo view $repoName --json nameWithOwner,visibility
git tag -a $edgeTag -m "SuishouReply Edge $edgeTag"
git push origin $edgeTag
gh release create $edgeTag $edgeAsset $edgeChecksum --repo $repoName --verify-tag --draft --title "随手回 Edge $edgeTag" --notes-file .\work\release-notes.md
```

先核对草稿说明与附件，下载并比对 SHA-256，再使用 `gh release edit $edgeTag --repo $repoName --draft=false` 发布。发布后匿名下载附件再次校验，并检查 README、Release 和直接下载链接。原有 v1.0.0 Release 及安装包继续保留，不为本次发版删除旧版本。

用户端升级已加载的扩展时，可在原稳定安装路径替换 `extension` 运行文件，再在 Edge 扩展页重新加载并刷新 X；同时升级桥接 EXE 时按 [安装与升级说明](EDGE_EXTENSION.md#从已有-v120-升级) 完成旧组件卸载与新目录注册。新开关默认关闭，发布文档应明确要求用户主动启用，以及先暂停桌面剪贴板监听。

## 完整桌面版维护模板（v1.1.1）

以下沿用完整 PySide6 桌面程序的构建与发布流程；文件名不带 `Edge`，不能用这些命令替代上方扩展构建。v1.1.1 源码已包含在仓库中，完整桌面二进制公开下载仍以 v1.0.0 Release 为准。

```powershell
$repoOwner = 'shui234'
$repoName = "$repoOwner/suishou-reply"
$releaseVersion = '1.1.1'
$releaseTag = "v$releaseVersion"
```

## 1. 同步源码并修改

先确认当前分支、工作区和远程地址，再更新源码。存在未提交修改时，先妥善处理，不要覆盖它们。

```powershell
git status --short --branch
git remote -v
git pull --ff-only
git switch -c "release/$releaseTag"
```

同步更新以下版本信息：

- `suishou/__init__.py` 的 `__version__`。
- `scripts/build.py` 的 `VERSION`，以及 `write_version_info()` 中的文件和产品版本，包括数字元组。
- `CHANGELOG.md`、相关 README 下载链接和本次验证记录。

只记录已经实现的变化。新的截图使用真实运行界面，并说明是否采用模拟数据；不要将离线测试写成真实账户调用成功。

## 2. 运行测试并构建

```powershell
.\start.bat --prepare-only
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest -q
.\build.bat
```

每一步退出码为 0 后再继续。构建后运行最终 EXE 自检，确认新产物而非旧源码通过：

```powershell
$check = Start-Process -FilePath .\dist\SuishouReply.exe -ArgumentList '--self-test --report build/exe-self-test.json' -Wait -PassThru -WindowStyle Hidden
$check.ExitCode
Get-Content -LiteralPath .\build\exe-self-test.json -Encoding UTF8
Get-Content -LiteralPath .\dist\BUILD_INFO.json -Encoding UTF8
Get-FileHash -LiteralPath .\dist\SuishouReply.exe -Algorithm SHA256
```

自检使用合成文本和本地模拟服务，会短暂使用并恢复系统剪贴板，请避开其他复制操作。它不验证真实 DeepSeek 账户。仅在你主动使用自己的密钥完成真实调用后，才在报告中记录对应验证；不要把密钥写入测试、日志或仓库。

## 3. 准备发布文件

执行 `python scripts/package_release.py --dist-dir dist` 可生成 ZIP 与 SHA-256；旧版运行时可先 `python scripts/build.py --dist-dir dist-v1.1.1`，再使用相同目录打包。脚本不会自动推送或发布。发布包沿用 v1.0.0 的结构：ZIP 最外层为 `SuishouReply/`，其中包含完整应用源码、启动与构建脚本、README、文档和许可文件；`dist/` 内包含 EXE、`BUILD_INFO.json`、`SHA256SUMS.txt`、`THIRD_PARTY_NOTICES.md` 和 `licenses/`。

EXE 在压缩包内的路径应为 `SuishouReply/dist/SuishouReply.exe`，与 README 的运行说明一致。ZIP 命名为 `SuishouReply-<版本>-Windows.zip`，例如 `SuishouReply-1.1.1-Windows.zip`。检查 ZIP 中没有 `.git`、`.venv`、工作缓存、个人配置、真实密钥、令牌或私人文本。

在工作区内保存本次 `release-notes.md`，写明变化、运行方法、验证结果、未验证事项和代码签名状态。发布说明使用普通文本文件传给 `gh`，保留正常换行，不将密钥放入命令参数。

## 4. 提交、审核并合并

先检查将要提交的文件与差异，再明确添加需要的源码和文档。不要提交 EXE、开发环境或私人配置。

```powershell
git status --short
git diff --check
git diff
# 按实际修改替换此列表，并加入已核对的源码文件。
$changedFiles = @('README.md', 'CHANGELOG.md', 'docs/TEST_REPORT.md')
git add -- $changedFiles
git diff --cached --check
git diff --cached --stat
git commit -m "Prepare $releaseTag"
git push -u origin "release/$releaseTag"
```

使用仓库现有的审核流程创建并合并 Pull Request。示例：

```powershell
gh pr create --repo $repoName --title "Prepare $releaseTag" --body-file .\work\release-notes.md
```

不要强制推送，也不要在常规发版时修改仓库的可见性。合并后切回主分支并拉取已审核的提交；以下示例假设主分支名为 `main`：

```powershell
git switch main
git pull --ff-only
git status --short --branch
```

## 5. 创建草稿 Release，再发布

确认登录的是预期 GitHub 账号、仓库为预期的公开状态，再给已验证且已合并的提交打标签。公开内容必须先检查密钥与隐私信息。若标签已经存在，检查其指向，不要覆盖或移动已发布标签。

```powershell
gh auth status
gh repo view $repoName --json nameWithOwner,visibility
git tag -a $releaseTag -m "SuishouReply $releaseTag"
git push origin $releaseTag
$releaseAsset = ".\work\releases\SuishouReply-$releaseVersion-Windows.zip"
gh release create $releaseTag $releaseAsset --repo $repoName --verify-tag --draft --title "随手回 $releaseTag" --notes-file .\work\release-notes.md
```

检查草稿中的标题、说明、标签提交和附件。下载附件并比对 ZIP 内 EXE 的 SHA-256 与 `BUILD_INFO.json`、`SHA256SUMS.txt`，确认无误后发布：

```powershell
gh release edit $releaseTag --repo $repoName --draft=false
gh release view $releaseTag --repo $repoName
```

公开仓库的 Release 附件应能在未登录时下载。发布完成后匿名下载附件并验证 SHA-256，检查 README 的版本链接和附件名称，记录最终 Release 地址。不要在仓库、Release、Issue 或命令输出中公开 GitHub 令牌或 DeepSeek API Key。
