# 周报接入协议 v1

目标：生成器直接产出可校验的数据，不必每周复制聊天附件。采集和生成独立于站点；站点负责验证、归档、渲染和部署。当前没有启用任何定时任务。

## 信封格式

```json
{
  "schema_version": 1,
  "column": "rust",
  "date": "2026-10-05",
  "title": "本期经过编辑的标题",
  "summary": "本期摘要，不能把未核验的陈述写成事实。",
  "coverage": "本期实际覆盖的时间范围及所在时区",
  "provenance": "生成器或编辑来源与核验说明",
  "highlights": ["可选导览"],
  "sources": [{"id":"rust-blog","title":"Rust 官方博客","url":"https://blog.rust-lang.org/","accessed_at":"2026-10-05"}],
  "items": [{"id":"release-note","title":"条目标题","summary":"基于来源的概述","source_ids":["rust-blog"],"tags":["发布"],"metadata":{"version":"以核验版本为准"}}]
}
```

以上是协议示例，不是已发布的真实新闻。日期使用 `YYYY-MM-DD`，日期含义由生成器的已确认时区决定；禁止从执行机时区猜测用户时区。`column` 必须注册。`source_ids` 必须引用同一期存在的来源，所有来源只接受无凭证 HTTPS URL。

每一期至少含 `items` 或 `original` 之一。字段详细结构见 `schemas/issue-v1.schema.json`。`scripts/build.py --validate` 是发布时的权威校验，还会检查跨字段引用、真实日历日期、重复期刊、路径和文件哈希。

## 接入原始 HTML

在信封里增加：

```json
"original": {
  "path": "rust-weekly-2026-10-05.html",
  "sha256": "替换为原始字节的64位小写SHA256"
}
```

文件名必须是小写 ASCII 安全文件名，不含路径。运行 `python scripts/ingest.py issue.json --original /path/to/report.html`。内容先在临时目录完整校验，校验通过才写入。已有一期和同名不同内容的原文件不会被静默覆盖。`original` 只有元数据时，脚本会验证仓库内已经存在的文件。

归档原文不改写、不注入脚本，下载版本按字节保留。站点阅读导览链接到 `/originals/<filename>.html` 共享阅读外壳：顶部提供站点来源、返回首页、栏目、本期导览、仓库及实际期刊日期，下方隔离嵌入原始 HTML，保留各栏目的图表与筛选。新增一期自动套用同一导航钩子。原文件放在 `/downloads/originals/<filename>.html`，供阅读器加载及明确下载。

原始 HTML 应自包含，或使用绝对资源 URL；以 `#id` 表达文内跳转。它仍可执行脚本，iframe 不是安全边界，因此接入前应检查来源、脚本、外链与敏感信息；不要自动接入任意远端 HTML。

## 推荐的未来链路

1. 已授权采集器从明确的公开来源获取材料，记下发生时间、获取时间、时区与 URL
2. 生成器输出 v1 JSON，以及可选的完整 HTML；保留每条来源、统计口径和不确定性
3. 调用 `ingest.py`，再跑测试和构建；失败停止，不能带病发布
4. 人工审核或明确的长期公开发布授权生效后，才提交到 GitHub
5. GitHub Actions 构建和部署，验证对应提交的部署结果与线上页面

不要把“成功接入”误认为“允许公开发布”。当前仅部署已明确批准的站点与内容，无计划任务、抓取任务或模型调用。

## 版本演进

当前只接受 `schema_version: 1`，未知字段报错，防止生成器拼错字段导致静默丢失。兼容新增字段应更新 schema、验证器、渲染器和测试；破坏性修改新增 v2 并提供迁移，保留已有档案的可重建性。未来生成器提交的数据不允许直接提供 HTML 页面路径、模板名称或执行代码。
