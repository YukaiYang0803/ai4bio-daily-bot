# AI4Bio / BioFM Daily Paper Bot

每日自动抓取 arXiv 论文，用 DeepSeek 筛选并生成中文摘要，发送到指定邮箱。

## 工作流程

1. 抓取 arXiv 最新论文（8 个分类，近 2 天，最多 300 篇）
2. 关键词预筛选（8 个 broad keywords）
3. DeepSeek 逐篇评分（relevance + quality judge）
4. 全球排名，选取 top 3-5 篇
5. DeepSeek 生成中文 2 问题摘要
6. 邮件推送至指定收件人

## 部署（GitHub Actions，完全自动化）

### 1. 推送到 GitHub

```bash
cd ai4bio_daily_bot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
git push -u origin main
```

### 2. 设置 GitHub Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions，添加：

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `SMTP_HOST` | smtp.gmail.com |
| `SMTP_PORT` | 587 |
| `SMTP_USERNAME` | 你的 Gmail 地址 |
| `SMTP_PASSWORD` | Gmail App Password（不是邮箱密码） |
| `EMAIL_FROM` | 发件人地址（同 Gmail） |
| `EMAIL_TO` | 收件人（可逗号分隔多个） |

### 3. Gmail App Password 获取

1. 开启 Gmail 两步验证
2. 访问 https://myaccount.google.com/apppasswords
3. 生成一个 App Password（选 Mail + Other）

### 4. 调度时间

默认每天北京时间 20:00（UTC 12:00）。修改 `.github/workflows/daily.yml` 中的 cron：

```yaml
- cron: '0 12 * * *'  # 北京时间 20:00
```

### 5. 手动测试

GitHub Actions → AI4Bio Daily Paper Digest → Run workflow

## 本地测试

```bash
export DEEPSEEK_API_KEY="sk-xxx"
export SMTP_USERNAME="your@gmail.com"
export SMTP_PASSWORD="your-app-password"
export EMAIL_FROM="your@gmail.com"
export EMAIL_TO="receiver@gmail.com"

pip install -r requirements.txt
python main.py
```

## 修改配置

编辑 `config.yaml`：
- `selection.max_papers`: 每日最多推送篇数（默认 5）
- `email.receivers`: 收件人列表
- `prefilter.keywords`: 筛选关键词
- `arxiv.categories`: ArXiv 分类

## 项目结构

```
ai4bio_daily_bot/
├── .github/workflows/daily.yml   # GitHub Actions 调度
├── main.py                        # Pipeline 编排
├── config.yaml                    # 所有配置
├── arxiv_fetcher.py               # ArXiv API
├── llm_judge.py                   # DeepSeek 相关性判断
├── ranker.py                      # 评分排序
├── summarizer.py                  # 中文摘要生成
├── email_sender.py                # SMTP 发送
├── state_store.py                 # 去重 + 日志
├── prompts/
│   ├── relevance_judge.txt        # Judge prompt
│   └── summary_generator.txt      # Summary prompt
├── data/seen_papers.json          # 已发送论文（自动维护）
└── logs/                          # 每日运行日志
```
