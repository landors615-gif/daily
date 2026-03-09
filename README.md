# daily

全球金融投资日报（GitHub Pages）

## 内容结构
- `daily/YYYY-MM-DD.md`：每日报告正文
- `index.html`：网页版入口（自动列出最新日报）
- `scripts/generate_daily.py`：日报生成脚本
- `.github/workflows/finance-daily.yml`：每天 09:00（Asia/Shanghai）自动生成并推送

## 运行方式（本地）
```bash
python3 scripts/generate_daily.py
```

## 自动化
GitHub Actions 定时任务：
- `cron: 0 1 * * *`（UTC）= 北京时间 09:00

## 部署
在仓库 `Settings -> Pages` 中选择：
- Source: Deploy from a branch
- Branch: `main` / `(root)`

完成后页面入口：
`https://<your-username>.github.io/daily/`
