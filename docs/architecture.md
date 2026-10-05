# 共享外壳 + 栏目模块

## 分层

`content`（数据） → `validate_issue`（契约） → `Builder`（页面） → `templates/base.html`（外壳） → `static`（设计与交互）。

所有页面使用同一导航、页脚、可访问跳转、SEO 摘要和响应式设计。栏目只贡献配置与专属元数据；日期路由由生成器决定。内容不会成为模板代码；所有文本和属性均 HTML 转义。JSON 原始索引在 `/api/index.json`，版本与内容协议一致，可供未来客户端读取。

## 增加栏目

1. 复制 `config/columns.json` 中一条配置，设置唯一安全 `id`、中文名称、描述、短符号、标签和空状态
2. 设置 `module`；未知模块使用通用渲染。`accent` 可复用 rust/github/ai 或在 CSS 加新颜色规则
3. 使用相同 v1 信封写入 `content/issues/YYYY-MM-DD/<id>.json`
4. 专属字段在 `scripts/columns.py` 的 `FIELDS` 加标签映射，不复制整页模板
5. 更复杂组件在该模块实现并由共享渲染器调用，同时增加测试；避免把采集请求或秘密写入前端

现有字段：Rust 的 version/compatibility；GitHub 的 language/license/stars_delta/metric_window；AI 的 availability/pricing/verification。没有数据时不造数，未知元数据保存在 JSON 索引但不自动显示。

## URL 与部署

站点路径前缀集中在 `config/site.json`。首页 `/`，栏目 `/columns/<id>/`，期刊 `/issues/<date>/<id>/`，历史 `/archive/`，全文阅读 `/originals/<filename>.html`，原始下载 `/downloads/originals/<filename>.html`。每期稳定链接不依赖最新排序。默认部署到项目 Pages 的 `/tech-weekly`，本地 `--base ''` 预览。

## 完整周报的导航钩子

`Builder.original(issue)` 是所有 HTML 周报共用的构建钩子。原有 `/originals/` 公开链接直接生成 `templates/reader.html`，头部从站点、栏目和本期 JSON 读取首页、栏目、本期导览、GitHub 仓库及真实期刊日期；新增一期自动使用，无须逐篇改 HTML。

外壳将字节不变的原文放在带标题、可聚焦的 iframe 内，原文独立滚动，保留各自的 sticky 导航、进度条、筛选、主题、打印按钮和下载功能。站点样式及脚本不会进入原文 DOM。顶部下载链接明确指向原始 HTML；源文件及下载文件都使用相同期刊 SHA-256。iframe 是样式与 DOM 隔离，不是安全沙箱，仍只接受审查过的可信 HTML。

`static/reader.js` 只渐进增强片段链接与键盘跳转：已有全文 `#片段` 会传给原文，原文片段变化反映到可分享的阅读 URL，不额外添加一条历史记录。无 JavaScript 时导航、下载及 iframe 正文仍可用。原文打印按钮在其自己的文档中工作。原文应为自包含 HTML，或使用绝对资源 URL，避免依赖原来的文件夹位置。

构建是确定性的，不把构建时钟写入输出。已发布期刊和原始文件进入版本控制，构建产物 `dist/` 不入库。所有内容与模板都可本地重建，无框架、第三方字体、分析追踪或外部运行时依赖（原始周报可能有自己的外部资源）。

## 发布与隐私边界

PR 工作流只能读仓库并校验。部署 job 仅赋予 Pages 写入及短期 OIDC 身份权限，不创建或存储个人凭证。不包含 cron；未来采集/生成应有单独授权与失败处理。原始周报仅保留公开技术内容，导入前应做人工内容及脚本审查。
