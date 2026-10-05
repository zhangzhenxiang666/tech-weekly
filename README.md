# 技术周刊 · TakeHan

一个轻量、可扩展的中文技术周刊站点，发布在 [GitHub Pages](https://zhangzhenxiang666.github.io/tech-weekly/)。

目前栏目：Rust、GitHub 热门项目、AI。首页和栏目共享设计系统，每期有日期固定链接，归档可以按栏目筛选或搜索。全文阅读页保留站点首页、栏目、本期导览及 GitHub 仓库导航，显示实际期刊日期。原始 HTML 周报按字节完整保留，可单独下载，图表与交互仍可使用。

## 本地运行

需要 Python 3.11+，无第三方运行依赖。

```sh
python scripts/build.py --validate
python -m unittest discover -s tests -v
python scripts/build.py --base ''
python -m http.server 8000 --directory dist
```

也可用 `uv run python …`。正式构建不传 `--base`，自动读取 `/tech-weekly`，适用于 GitHub 项目 Pages。

## 目录

- `config/site.json`：站点名称、公开 URL、子路径
- `config/columns.json`：栏目注册表；导航、首页卡片、栏目页自动生成
- `content/issues/YYYY-MM-DD/<column>.json`：每期结构化入口
- `content/originals/`：原始 HTML 周报；SHA-256 防止无意修改
- `schemas/issue-v1.schema.json`：机器可读的接入格式
- `templates/base.html`：共享页面外壳
- `templates/reader.html`：完整周报的共享导航外壳，隔离原文样式与脚本
- `static/`：共享样式与渐进增强脚本
- `scripts/columns.py`：栏目专属展示扩展点
- `scripts/build.py`：校验、渲染、索引生成
- `scripts/ingest.py`：原子预校验的数据接入入口，不自动发布
- `tests/`：边界校验、输出链接和原始文件保真测试

## 添加一期

详见 [接入协议](docs/ingestion.md)。生成器可以直接输出 JSON 到接入脚本，不依赖手工从聊天界面复制文件：

```sh
python scripts/ingest.py issue.json --original original.html
# 或结构化正文直接通过标准输入
producer-command | python scripts/ingest.py -
python -m unittest discover -s tests -v
python scripts/build.py
```

检查生成结果后，将数据与源文件提交到 `main`。Actions 会校验、构建并部署；失败不会替换线上版本。重复日期+栏目的接入会拒绝覆盖，请明确审核后直接编辑原 JSON。

## 增加栏目

在 `config/columns.json` 添加一条配置即可得到导航、首页卡片、栏目归档和通用渲染。`module` 未注册时使用通用说明；需要专属功能时，在 `scripts/columns.py` 注册说明与字段标签，在同一共享模板中渲染。通用字段不随栏目复制。更多说明见 [扩展设计](docs/architecture.md)。

## 发布

仓库 Settings → Pages → Source 使用 **GitHub Actions**。工作流为 `.github/workflows/pages.yml`，PR 只校验，`main` push 或手动 dispatch 才部署。工作流仅使用临时 `GITHUB_TOKEN`，无需配置个人 token 或密钥。

**定期采集、生成、定时发布尚未启用。** 仓库没有 cron，没有外部模型密钥，也没有自动读取聊天内容。未来生成器应输出同一接入协议；具体来源、时区、频率和公开发布范围确认后再接通。

## 内容与核验

已收录的原始周报保留自身来源和核验边界。站点导览只帮助定位内容，不把原报告的每个结论宣称为新核验事实。历史价格、热度、版本和可用性请以来源的当时口径及最新官方资料为准。缺失的期刊显示为空，不以旧内容或虚构新闻代替。

原始 HTML 含可执行 JavaScript，应只接入已人工审查的可信产物。校验器验证格式、路径、引用关系和文件校验和，不是 HTML 安全审计器。公共仓库中不要加入私人数据、访问令牌或内部链接。
