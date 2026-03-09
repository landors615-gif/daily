#!/usr/bin/env python3
import datetime as dt
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "daily"


def sh(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='ignore')
    return p.stdout.strip()


def stooq(symbol: str):
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    out = sh(f"curl -s '{url}' | tail -n 1")
    parts = out.split(',')
    if len(parts) < 7 or parts[1] == 'N/D':
        return None
    return {
        'symbol': parts[0],
        'date': parts[1],
        'open': parts[3],
        'high': parts[4],
        'low': parts[5],
        'close': parts[6],
    }


def tencent_cn_indices():
    out = sh("curl -s 'https://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006'")
    # 兼容乱码，仅提取数字段
    rows = out.splitlines()
    vals = {}
    keys = ['sse','sz','cyb']
    for k, r in zip(keys, rows):
        nums = re.findall(r"-?\d+\.\d+|-?\d+", r)
        # 格式一般含代码、现价、涨跌、涨跌幅
        # 这里用靠后的稳定段：现价, 涨跌, 涨跌幅
        if len(nums) >= 5:
            vals[k] = {
                'close': nums[1],
                'chg': nums[2],
                'pct': nums[3],
            }
    return vals


def macro_headlines():
    queries = [
        "Fed policy latest 24 hours",
        "PBOC latest policy today",
        "OPEC+ oil output latest"
    ]
    items = []
    for q in queries:
        out = sh(f"python3 - <<'EOF'\nprint('')\nEOF")
        # 占位：在无稳定新闻API下，保留观察项
        items.append(q)
    return items


def pct(open_, close_):
    try:
        o = float(open_)
        c = float(close_)
        return (c - o) / o * 100
    except Exception:
        return None


def fmt_line(name, d):
    if not d:
        return f"- {name}: N/A"
    p = pct(d['open'], d['close'])
    ptxt = f"{p:+.2f}%" if p is not None else "N/A"
    return f"- {name}: {d['close']} ({ptxt})"


def build_report(now):
    dji = stooq('^dji')
    spx = stooq('^spx')
    ndq = stooq('^ndq')
    wti = stooq('cl.f')
    brent = stooq('cb.f')
    xau = stooq('xauusd')
    xag = stooq('xagusd')
    cn = tencent_cn_indices()

    mood = "震荡偏谨慎"
    if dji and spx:
        pd = pct(dji['open'], dji['close']) or 0
        ps = pct(spx['open'], spx['close']) or 0
        if pd > 0.4 and ps > 0.4:
            mood = "风险偏好回升"
        elif pd < -0.4 and ps < -0.4:
            mood = "避险情绪升温"

    report = f"""# 全球金融投资日报（{now.strftime('%Y-%m-%d')}）

> 目标受众：专业投资者及高净值个人  
> 覆盖范围：美股、A股、能源、贵金属  
> 生成时间：{now.strftime('%Y-%m-%d %H:%M')} (Asia/Shanghai)

## 🌍 宏观风向标 (Macro Overview)
过去24小时市场主线仍围绕“美联储路径预期、主要经济体政策信号、能源供需预期”展开。风险资产与避险资产呈现跷跷板效应，整体情绪为 **{mood}**。当前阶段交易更偏向数据驱动，市场对增量宏观信息的敏感度提升。

## 🇺🇸 美股聚焦 (US Markets)
### 三大指数（日内近似）
{fmt_line('道指 (DJI)', dji)}
{fmt_line('标普500 (SPX)', spx)}
{fmt_line('纳斯达克100 (NDQ)', ndq)}

### 热门板块/个股
科技成长与AI链条仍是弹性来源；若利率预期回落，成长风格通常受益更明显。中概资产表现仍受中美政策预期与美元流动性边际变化影响。

### 深度解读
美股短线节奏仍由“利率-估值”主导：收益率若上行，估值扩张受限；若回落，成长风格更易获得估值修复。

## 🇨🇳 A股透视 (China A-Shares)
### 大盘收盘（快照）
- 上证指数: {cn.get('sse',{}).get('close','N/A')} ({cn.get('sse',{}).get('pct','N/A')}%)
- 深证成指: {cn.get('sz',{}).get('close','N/A')} ({cn.get('sz',{}).get('pct','N/A')}%)
- 创业板指: {cn.get('cyb',{}).get('close','N/A')} ({cn.get('cyb',{}).get('pct','N/A')}%)

### 资金与政策观察
北向与主力资金在高景气方向与防御方向间切换。政策端若出现对特定产业（如先进制造/自主可控/消费修复）边际催化，板块轮动速度可能加快。

## ⛽️💰 大宗商品 (Commodities)
### 能源
{fmt_line('WTI 原油', wti)}
{fmt_line('布伦特原油', brent)}

### 贵金属
{fmt_line('黄金 (XAUUSD)', xau)}
{fmt_line('白银 (XAGUSD)', xag)}

联动上，油价影响通胀预期与风险偏好；美元与实际利率变化仍是金银定价核心变量。

## 💡 策略综述与明日展望 (Strategy & Outlook)
### 市场情绪一句话
**{mood}，以数据验证替代预判。**

### 明日3个关键观察点
1. 美债收益率与美元指数方向是否同向强化；
2. 能源价格是否突破关键区间并影响通胀交易；
3. A股权重与成长风格的资金切换是否持续。

### 风险提示
地缘事件、政策措辞变化与流动性冲击可能引发跨资产波动放大；请控制仓位与节奏，避免追涨杀跌。

---
*说明：本日报为信息整合与逻辑推演，不构成任何投资建议。*
"""
    return report


def build_index():
    files = sorted(DAILY_DIR.glob('*.md'), reverse=True)
    latest = files[0].stem if files else 'N/A'
    items = "\n".join([
        f"<li><a href='daily/{f.name}'><span>{f.stem}</span><small>查看</small></a></li>" for f in files[:60]
    ])
    html = f"""<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>Kora Path · Global Finance Daily</title>
  <style>
    :root {{
      --bg:#0b0f17; --panel:#121827; --card:#0f172a; --line:#25324a;
      --text:#e6edf7; --muted:#93a4bd; --gold:#c8a15a; --ok:#23c483;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin:0; color:var(--text);
      background: radial-gradient(1200px 500px at 10% -10%, #1b2a45 0%, transparent 60%), var(--bg);
      font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
      line-height:1.6;
    }}
    .wrap {{ max-width: 980px; margin: 36px auto; padding: 0 16px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(200,161,90,.12), rgba(35,196,131,.08));
      border:1px solid var(--line); border-radius: 18px; padding: 26px 22px;
      box-shadow: 0 12px 32px rgba(0,0,0,.28);
    }}
    h1 {{ margin:0; font-size: 34px; letter-spacing:.2px; }}
    .sub {{ margin-top:8px; color:var(--muted); }}
    .meta {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }}
    .chip {{
      border:1px solid var(--line); background: rgba(18,24,39,.75); color:var(--muted);
      border-radius:999px; padding:6px 10px; font-size:13px;
    }}
    .chip b {{ color: var(--gold); font-weight:600; }}

    .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:18px; }}
    .card {{
      background: var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px;
    }}
    .card h2 {{ margin:0 0 10px 0; font-size:18px; color:var(--gold); }}
    .kpi {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .kpi .box {{
      background:var(--card); border:1px solid var(--line); border-radius:12px; padding:10px 12px;
    }}
    .kpi .label {{ color:var(--muted); font-size:12px; }}
    .kpi .val {{ font-size:20px; font-weight:700; margin-top:2px; }}

    ul.list {{ list-style:none; margin:0; padding:0; max-height: 560px; overflow:auto; }}
    ul.list li + li {{ margin-top:10px; }}
    ul.list a {{
      display:flex; justify-content:space-between; align-items:center;
      text-decoration:none; color:var(--text);
      background:var(--card); border:1px solid var(--line); border-radius:12px;
      padding:12px 14px;
      transition: transform .15s ease, border-color .15s ease;
    }}
    ul.list a:hover {{ transform: translateY(-1px); border-color: #3c4f72; }}
    ul.list small {{ color: var(--muted); }}

    footer {{ color:var(--muted); text-align:center; margin:20px 0 6px; font-size:13px; }}

    @media (max-width: 820px) {{
      .grid {{ grid-template-columns:1fr; }}
      h1 {{ font-size:28px; }}
    }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>全球金融投资日报</h1>
      <p class='sub'>Kora Path · AI 驱动宏观观察面板</p>
      <div class='meta'>
        <span class='chip'>更新频率：<b>每日 09:00</b>（Asia/Shanghai）</span>
        <span class='chip'>仓库：<b>landors615-gif/daily</b></span>
        <span class='chip'>最新一期：<b>{latest}</b></span>
      </div>
    </section>

    <section class='grid'>
      <article class='card'>
        <h2>日报概览</h2>
        <div class='kpi'>
          <div class='box'><div class='label'>总期数</div><div class='val'>{len(files)}</div></div>
          <div class='box'><div class='label'>状态</div><div class='val' style='color:var(--ok)'>RUNNING</div></div>
        </div>
        <p class='sub' style='margin-top:12px;'>本页面由 GitHub Pages 托管，内容由自动化任务生成与更新。</p>
      </article>

      <article class='card'>
        <h2>历史日报</h2>
        <ul class='list'>{items}</ul>
      </article>
    </section>

    <footer>© Kora Path · Built with OpenClaw · Not Investment Advice</footer>
  </div>
</body>
</html>"""
    (ROOT / 'index.html').write_text(html, encoding='utf-8')


def main():
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    md = build_report(now)
    out = DAILY_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    out.write_text(md, encoding='utf-8')
    build_index()
    print(f"generated {out}")


if __name__ == '__main__':
    main()
