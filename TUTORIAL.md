# 如何用这个仓库搭建你自己的每日论文推送 Bot

全程约 15 分钟，不需要写代码。

---

## 1. Fork 这个仓库

点右上角 Fork → 创建你自己的副本。

---

## 2. 修改研究方向和兴趣

### 2.1 编辑 `prompts/relevance_judge.txt`

这是最核心的一步。修改 prompt 中的研究兴趣描述，让 DeepSeek 按你的需求筛选论文。

当前内容是为 AI4Bio / 生物基础模型设计的。你需要改写：

- 第 1-19 行：描述你关心的研究方向
- 第 19 行：排除你不关心的方向

### 2.2 编辑 `prompts/summary_generator.txt`

修改摘要生成 prompt。可以：
- 保持 2 问题格式，仅改领域描述
- 或改成 N 问题格式（你的自定义结构）

### 2.3 编辑 `config.yaml`

```yaml
arxiv:
  categories:  # ArXiv 分类，改成你关心的
    - cs.LG
    - cs.AI
    # ... 加减分类

prefilter:
  keywords:  # 关键词预筛选，broad is better
    - your keyword
    - another keyword

selection:
  max_papers: 5  # 每日最多推送篇数

schedule:
  timezone: "Asia/Shanghai"  # 你的时区
  send_hour_local: 20  # 几点推送（24h）
  send_minute_local: 0
```

---

## 3. 修改 GitHub Actions 调度时间

编辑 `.github/workflows/daily.yml`：

```yaml
schedule:
  - cron: '0 12 * * *'  # 这里是 UTC 时间！
```

**时间换算：**
- `北京时间 = UTC + 8`
- 北京 20:00 = UTC 12:00 → `0 12 * * *`
- 纽约 08:00 = UTC 12:00（夏令时）→ `0 12 * * *`

[Cron 表达式网站](https://crontab.guru)

---

## 4. 配置 Secrets

去仓库 Settings → Secrets and variables → Actions → New repository secret：

| Secret | 说明 | 示例 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-xxx` |
| `SMTP_HOST` | SMTP 服务器 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口 | `587` |
| `SMTP_USERNAME` | 发件邮箱地址 | `you@gmail.com` |
| `SMTP_PASSWORD` | Gmail App Password | 16 位字符 |
| `EMAIL_FROM` | 发件人地址 | `you@gmail.com` |
| `EMAIL_TO` | 收件人（多人用逗号分隔） | `you@gmail.com,friend@qq.com` |

### Gmail App Password 获取

1. 开启 [两步验证](https://myaccount.google.com/security)
2. 前往 [App Passwords](https://myaccount.google.com/apppasswords) 生成
3. 选 Mail + Other，复制 16 位密码

---

## 5. 调整评分阈值（可选）

编辑 `config.yaml`：

```yaml
selection:
  min_topic_relevance: 4   # 降低 = 更多论文
  min_learning_value: 4    # 降低 = 更多论文
  min_evaluation_quality: 3  # 降低 = 更多论文

scoring:
  topic_relevance: 2.0   # 调整各维度权重
  learning_value: 2.0
  # ...
```

规则在 `ranker.py` 里，想看就改。

---

## 6. 启用 GitHub Actions

1. 去仓库 Actions tab
2. 点 "I understand my workflows, go ahead and enable them"
3. 手动触发一次：Actions → AI4Bio Daily Paper Digest → Run workflow

---

## 7. 调试

每次运行后查看：
- **Actions 日志**：GitHub Actions → 最近的 run → run-bot job
- **每日日志**：`logs/YYYY-MM-DD.json`（自动提交到仓库）
- **已发送记录**：`data/seen_papers.json`

---

## 常见问题

**Q: 收不到邮件？**
A: 检查 Gmail App Password 是否正确、两步验证是否开启。

**Q: 每天只推送 0-1 篇？**
A: 阈值可能太严。降低 `config.yaml` 里的 `min_*` 值。

**Q: 论文不相关？**
A: 修改 `prompts/relevance_judge.txt` 中的研究方向描述。

**Q: 推送太多不相关论文？**
A: 提高阈值或收紧 prompt。

**Q: 能用 QQ 邮箱 / 163 邮箱吗？**
A: 可以。改 `SMTP_HOST`、`SMTP_PORT` 为对应配置，`SMTP_PASSWORD` 填授权码。

**Q: 能用其他 LLM 吗（OpenAI / 通义千问）？**
A: 可以。修改 `config.yaml` 中的 `llm.api_base` 和 `llm.model`，DeepSeek API 兼容 OpenAI SDK。
