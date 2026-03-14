#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import subprocess
import random
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "daily"
CONTENT_DIR = ROOT / "content"


def sh(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="ignore")
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
    rows = out.splitlines()
    vals = {}
    keys = ['sse', 'sz', 'cyb']
    for k, r in zip(keys, rows):
        # 腾讯返回类似：v_s_sh000001="1~上证指数~000001~4096.60~-27.59~-0.67~...";
        m = re.search(r'="([^"]+)"', r)
        if not m:
            continue
        parts = m.group(1).split('~')
        # 索引位：3=现价, 4=涨跌, 5=涨跌幅(%)
        if len(parts) >= 6:
            close = parts[3]
            chg = parts[4]
            pct = parts[5]
            vals[k] = {'close': close, 'chg': chg, 'pct': pct}
    return vals


def fetch_rss_titles(url: str, limit: int = 5):
    xml = sh(f"curl -L -s --max-time 12 '{url}'")
    if not xml:
        return []
    titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', xml, flags=re.I | re.S)
    out = []
    for a, b in titles:
        t = (a or b or '').strip()
        t = re.sub(r'\s+', ' ', t)
        if not t:
            continue
        tl = t.lower()
        if tl in {'rss', 'reuters', 'cnbc', 'google news'}:
            continue
        if ' - google news' in tl:
            continue
        if t.startswith('"') and '" - ' in t:
            continue
        out.append(t)
    dedup = []
    seen = set()
    for t in out:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(t)
    return dedup[:limit]


def detect_event_tags(headlines):
    text = ' '.join(headlines).lower()
    tags = []
    rules = [
        ('fed', ['fed', 'federal reserve', 'powell', 'rate cut', 'rate hike']),
        ('inflation', ['inflation', 'cpi', 'ppi']),
        ('yields', ['treasury', 'bond yield', '10-year yield']),
        ('ai_tech', ['ai', 'nvidia', 'microsoft', 'apple', 'tesla', 'semiconductor', 'chip']),
        ('geopolitics', ['ukraine', 'middle east', 'geopolitical', 'tariff', 'sanction']),
        ('china_policy', ['china', 'beijing', 'pboc', 'stimulus', 'property', 'policy']),
        ('oil_supply', ['opec', 'oil supply', 'crude', 'brent', 'wti']),
        ('gold_safe_haven', ['gold', 'safe haven', 'dollar']),
    ]
    for name, kws in rules:
        if any(k in text for k in kws):
            tags.append(name)
    return tags


def pct(open_, close_):
    try:
        o = float(open_)
        c = float(close_)
        return (c - o) / o * 100
    except Exception:
        return None


def fmt_line(name, d):
    if not d:
        return f"{name}: N/A"
    p = pct(d['open'], d['close'])
    ptxt = f"{p:+.2f}%" if p is not None else "N/A"
    return f"{name}: {d['close']} ({ptxt})"


def parse_pct_from_line(line: str):
    m = re.search(r"\(([+-]?\d+(?:\.\d+)?)%\)", line)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def colorize_line(line: str):
    p = parse_pct_from_line(line)
    if p is None:
        return line
    if p > 0:
        arrow = '▲'
        cls = 'up'   # 中国市场习惯：上涨红色
        ptxt = f"+{abs(p):.2f}%"
    elif p < 0:
        arrow = '▼'
        cls = 'down' # 下跌绿色
        ptxt = f"-{abs(p):.2f}%"
    else:
        arrow = '•'
        cls = 'flat'
        ptxt = '0.00%'
    return re.sub(r"\(([+-]?\d+(?:\.\d+)?)%\)", f"(<span class='{cls}'>{arrow} {ptxt}</span>)", line)


def strength_word(v):
    if v is None:
        return "偏平"
    a = abs(v)
    if a >= 1.2:
        return "显著"
    if a >= 0.5:
        return "温和"
    return "窄幅"


def build_data(now):
    dji = stooq('^dji')
    spx = stooq('^spx')
    ndq = stooq('^ndq')
    wti = stooq('cl.f')
    brent = stooq('cb.f')
    xau = stooq('xauusd')
    xag = stooq('xagusd')
    cn = tencent_cn_indices()

    us_p = {
        'dji': pct(dji['open'], dji['close']) if dji else None,
        'spx': pct(spx['open'], spx['close']) if spx else None,
        'ndq': pct(ndq['open'], ndq['close']) if ndq else None,
    }
    cn_p = {
        'sse': float(cn.get('sse', {}).get('pct', 'nan')) if cn.get('sse', {}).get('pct') not in [None, 'N/A', ''] else None,
        'sz': float(cn.get('sz', {}).get('pct', 'nan')) if cn.get('sz', {}).get('pct') not in [None, 'N/A', ''] else None,
        'cyb': float(cn.get('cyb', {}).get('pct', 'nan')) if cn.get('cyb', {}).get('pct') not in [None, 'N/A', ''] else None,
    }
    com_p = {
        'wti': pct(wti['open'], wti['close']) if wti else None,
        'brent': pct(brent['open'], brent['close']) if brent else None,
        'gold': pct(xau['open'], xau['close']) if xau else None,
        'silver': pct(xag['open'], xag['close']) if xag else None,
    }

    mood = "震荡偏谨慎"
    mood_emoji = "⚖️"
    pd = us_p['dji'] or 0
    ps = us_p['spx'] or 0
    if pd > 0.4 and ps > 0.4:
        mood = "风险偏好回升"
        mood_emoji = "🚀"
    elif pd < -0.4 and ps < -0.4:
        mood = "避险情绪升温"
        mood_emoji = "🛡️"

    us_avg = sum([x for x in us_p.values() if x is not None]) / max(1, len([x for x in us_p.values() if x is not None]))
    cn_avg = sum([x for x in cn_p.values() if x is not None]) / max(1, len([x for x in cn_p.values() if x is not None]))
    oil_avg = sum([x for x in [com_p['wti'], com_p['brent']] if x is not None]) / max(1, len([x for x in [com_p['wti'], com_p['brent']] if x is not None]))

    world_news = fetch_rss_titles('https://news.google.com/rss/search?q=global+markets+when:1d&hl=en-US&gl=US&ceid=US:en', limit=4)
    business_news = fetch_rss_titles('https://news.google.com/rss/search?q=federal+reserve+inflation+when:1d&hl=en-US&gl=US&ceid=US:en', limit=4)
    market_news = fetch_rss_titles('https://news.google.com/rss/search?q=china+market+oil+gold+when:1d&hl=en-US&gl=US&ceid=US:en', limit=4)
    headlines = (world_news + business_news + market_news)[:8]
    event_tags = detect_event_tags(headlines)

    day_seed = int(hashlib.md5(now.strftime('%Y-%m-%d').encode()).hexdigest()[:8], 16)
    rng = random.Random(day_seed)

    macro_templates = [
        "美股整体{us_trend}，A股表现{cn_trend}，跨市场风险偏好{mood}。",
        "跨资产盘面显示：美股{us_trend}、A股{cn_trend}，整体情绪仍处于{mood}区间。",
        "从当日收盘结构看，美股{us_trend}且A股{cn_trend}，风险偏好维持{mood}。",
    ]
    us_templates = [
        "美股三大指数呈现{us_vol}波动，当前交易主线围绕{driver}展开。",
        "纳指与标普的节奏分化仍在，短线由{driver}主导估值锚。",
        "美股日内定价核心在于{driver}，指数表现为{us_vol}波动。",
    ]
    cn_templates = [
        "A股三大指数今日{cn_move}，盘面关注点集中在{driver}。",
        "A股延续{cn_move}，资金在权重与成长之间切换，主要受{driver}影响。",
        "A股日内呈现{cn_move}，后续需要观察{driver}能否持续。",
    ]
    com_templates = [
        "原油表现{oil_trend}，贵金属波动受{driver}影响更明显。",
        "大宗商品中油价{oil_trend}，金银价格继续围绕{driver}交易。",
        "商品端今日焦点是油价{oil_trend}，贵金属则受{driver}扰动。",
    ]

    us_trend = f"{strength_word(us_avg)}{'走强' if us_avg > 0 else ('回落' if us_avg < 0 else '震荡')}"
    cn_trend = f"{strength_word(cn_avg)}{'偏强' if cn_avg > 0 else ('偏弱' if cn_avg < 0 else '中性')}"
    us_vol = f"{strength_word(us_avg)}"
    cn_move = f"{strength_word(cn_avg)}{'上行' if cn_avg > 0 else ('回调' if cn_avg < 0 else '震荡')}"
    oil_trend = f"{strength_word(oil_avg)}{'偏强' if oil_avg > 0 else ('偏弱' if oil_avg < 0 else '震荡')}"

    us_driver = '利率预期与科技龙头财报预期'
    if 'fed' in event_tags or 'yields' in event_tags:
        us_driver = '美联储路径与美债收益率变化'
    elif 'ai_tech' in event_tags:
        us_driver = 'AI/半导体链条估值再定价'

    cn_driver = '政策预期与内需修复节奏'
    if 'china_policy' in event_tags:
        cn_driver = '政策端信号与稳增长预期'

    com_driver = '美元与实际利率预期'
    if 'oil_supply' in event_tags:
        com_driver = '供给扰动与地缘溢价'
    elif 'gold_safe_haven' in event_tags or 'geopolitics' in event_tags:
        com_driver = '避险需求与美元波动'

    macro_note = rng.choice(macro_templates).format(us_trend=us_trend, cn_trend=cn_trend, mood=mood)
    us_note = rng.choice(us_templates).format(us_vol=us_vol, driver=us_driver)
    cn_note = rng.choice(cn_templates).format(cn_move=cn_move, driver=cn_driver)
    com_note = rng.choice(com_templates).format(oil_trend=oil_trend, driver=com_driver)
    strategy_note = f"{mood_emoji} {mood}：基线情景以数据验证为先，若{('收益率继续上行' if 'yields' in event_tags else '地缘风险再升温' if 'geopolitics' in event_tags else '政策预期落空')}，需控制仓位并避免情绪化追涨杀跌。"

    return {
        "date": now.strftime('%Y-%m-%d'),
        "time": now.strftime('%Y-%m-%d %H:%M:%S'),
        "mood": mood,
        "mood_emoji": mood_emoji,
        "macro_note": macro_note,
        "us_note": us_note,
        "cn_note": cn_note,
        "com_note": com_note,
        "strategy_note": strategy_note,
        "headlines": headlines,
        "us": {
            "dji": colorize_line(fmt_line('道指 (DJI)', dji)),
            "spx": colorize_line(fmt_line('标普500 (SPX)', spx)),
            "ndq": colorize_line(fmt_line('纳斯达克100 (NDQ)', ndq)),
        },
        "cn": {
            "sse": colorize_line(f"上证指数: {cn.get('sse', {}).get('close', 'N/A')} ({cn.get('sse', {}).get('pct', 'N/A')}%)"),
            "sz": colorize_line(f"深证成指: {cn.get('sz', {}).get('close', 'N/A')} ({cn.get('sz', {}).get('pct', 'N/A')}%)"),
            "cyb": colorize_line(f"创业板指: {cn.get('cyb', {}).get('close', 'N/A')} ({cn.get('cyb', {}).get('pct', 'N/A')}%)"),
        },
        "commodities": {
            "wti": colorize_line(fmt_line('WTI 原油', wti)),
            "brent": colorize_line(fmt_line('布伦特原油', brent)),
            "gold": colorize_line(fmt_line('黄金 (XAUUSD)', xau)),
            "silver": colorize_line(fmt_line('白银 (XAGUSD)', xag)),
        }
    }


def build_content_payload(d):
    # 内容层：结构化文本主稿（作为渲染唯一来源）
    def plain(x: str):
        return re.sub(r'<[^>]+>', '', x)

    return {
        "date": d["date"],
        "time": d["time"],
        "mood": f"{d['mood_emoji']} {d['mood']}",
        "sections": {
            "macro": {
                "title": "🌍 宏观风向标",
                "summary": d["macro_note"]
            },
            "events": {
                "title": "📰 当日关键事件",
                "items": d.get('headlines', [])[:5]
            },
            "us": {
                "title": "🇺🇸 美股聚焦",
                "items": [plain(d['us']['dji']), plain(d['us']['spx']), plain(d['us']['ndq'])],
                "summary": d["us_note"]
            },
            "cn": {
                "title": "🇨🇳 A股透视",
                "items": [plain(d['cn']['sse']), plain(d['cn']['sz']), plain(d['cn']['cyb'])],
                "summary": d["cn_note"]
            },
            "commodities": {
                "title": "⛽️💰 大宗商品",
                "items": [plain(d['commodities']['wti']), plain(d['commodities']['brent']), plain(d['commodities']['gold']), plain(d['commodities']['silver'])],
                "summary": d["com_note"]
            },
            "strategy": {
                "title": "💡 策略综述与明日展望",
                "summary": d["strategy_note"]
            }
        }
    }


def build_daily_html(d):
    return f"""<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>全球金融投资日报 · {d['date']}</title>
  <style>
    :root {{
      --bg:#f5f5f7; --card:#ffffff; --line:#e7e7ea; --text:#1d1d1f;
      --muted:#6e6e73; --accent:#0071e3; --ok:#2fb344;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif; }}
    .wrap {{ max-width:1100px; margin:40px auto; padding:0 16px; }}
    .hero {{ background:linear-gradient(180deg,#fff,#f8f8fa); border:1px solid var(--line); border-radius:24px; padding:32px 28px; box-shadow:0 14px 40px rgba(0,0,0,.06); }}
    h1 {{ margin:0; font-size:42px; letter-spacing:-.02em; font-weight:700; }}
    .sub {{ margin-top:8px; color:var(--muted); }}
    .chips {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
    .chip {{ border:1px solid var(--line); border-radius:999px; padding:7px 12px; font-size:13px; color:var(--muted); background:#fff; }}
    .chip b {{ color:var(--text); }}

    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:18px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:20px; padding:20px; box-shadow:0 8px 20px rgba(0,0,0,.04); }}
    .card h2 {{ margin:0 0 12px 0; font-size:22px; letter-spacing:-.01em; }}
    .card p {{ margin:8px 0; color:#303035; }}
    .up {{ color:#d70015; font-weight:600; }}
    .down {{ color:#0f9d58; font-weight:600; }}
    .flat {{ color:#6e6e73; font-weight:600; }}
    .list {{ margin:0; padding-left:18px; }}
    .list li {{ margin:7px 0; }}
    .focus {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-top:8px; }}
    .focus .box {{ border:1px solid var(--line); border-radius:14px; padding:12px; background:#fafafa; font-size:14px; }}

    .footer {{ text-align:center; color:var(--muted); margin:18px 0 8px; font-size:13px; }}
    a.back {{ color:var(--accent); text-decoration:none; }}

    @media (max-width:900px) {{
      .grid {{ grid-template-columns:1fr; }}
      .focus {{ grid-template-columns:1fr; }}
      h1 {{ font-size:32px; }}
    }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>全球金融投资日报</h1>
      <div class='sub'>Global Finance Daily · 专业投资者版</div>
      <div class='chips'>
        <span class='chip'>日期：<b>{d['date']}</b></span>
        <span class='chip'>生成时间：<b>{d['time']}</b></span>
        <span class='chip'>市场情绪：<b>{d['mood_emoji']} {d['mood']}</b></span>
      </div>
    </section>

    <section class='grid'>
      <article class='card'>
        <h2>🌍 宏观风向标</h2>
        <p>{d['macro_note']}</p>
      </article>

      <article class='card'>
        <h2>📰 当日关键事件</h2>
        <ul class='list'>
          {''.join([f"<li>{h}</li>" for h in d.get('headlines', [])[:5]])}
        </ul>
      </article>

      <article class='card'>
        <h2>🇺🇸 美股聚焦</h2>
        <ul class='list'>
          <li>{d['us']['dji']}</li>
          <li>{d['us']['spx']}</li>
          <li>{d['us']['ndq']}</li>
        </ul>
        <p>{d['us_note']}</p>
      </article>

      <article class='card'>
        <h2>🇨🇳 A股透视</h2>
        <ul class='list'>
          <li>{d['cn']['sse']}</li>
          <li>{d['cn']['sz']}</li>
          <li>{d['cn']['cyb']}</li>
        </ul>
        <p>{d['cn_note']}</p>
      </article>

      <article class='card'>
        <h2>⛽️💰 大宗商品</h2>
        <ul class='list'>
          <li>{d['commodities']['wti']}</li>
          <li>{d['commodities']['brent']}</li>
          <li>{d['commodities']['gold']}</li>
          <li>{d['commodities']['silver']}</li>
        </ul>
        <p>{d['com_note']}</p>
      </article>

      <article class='card' style='grid-column:1/-1'>
        <h2>💡 策略综述与明日展望</h2>
        <p><strong>市场情绪一句话：</strong>{d['strategy_note']}</p>
        <div class='focus'>
          <div class='box'><strong>观察点 1</strong><br>美债收益率与美元指数是否同向强化</div>
          <div class='box'><strong>观察点 2</strong><br>能源价格是否突破关键区间并影响通胀交易</div>
          <div class='box'><strong>观察点 3</strong><br>A股权重与成长风格的资金切换是否持续</div>
        </div>
        <p style='margin-top:12px;color:var(--muted)'>风险提示：地缘事件、政策措辞变化与流动性冲击可能放大跨资产波动。本页面为信息整合，不构成投资建议。</p>
      </article>
    </section>

    <div class='footer'>
      <a class='back' href='../index.html'>← 返回日报首页</a><br>
      © Kora Path · Apple-like clean interface
    </div>
  </div>
</body>
</html>"""


def build_index(generated_time: str):
    html_files = sorted(DAILY_DIR.glob('*.html'), reverse=True)
    latest = html_files[0].stem if html_files else 'N/A'
    latest_disp = latest.replace('-', '/') if latest != 'N/A' else latest
    items = "\n".join([
        f"<li><a class='item' href='daily/{f.name}'><span>{f.stem}</span><span class='btn'>阅读日报</span></a></li>" for f in html_files[:60]
    ])
    html = f"""<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>Kora Path · Global Finance Daily</title>
  <style>
    :root {{ --bg:#f5f5f7; --card:#fff; --line:#e7e7ea; --text:#1d1d1f; --muted:#6e6e73; --accent:#0071e3; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif; }}
    .wrap {{ max-width:980px; margin:42px auto; padding:0 16px; }}
    .hero {{ background:linear-gradient(180deg,#fff,#f8f8fa); border:1px solid var(--line); border-radius:24px; padding:30px 26px; box-shadow:0 12px 32px rgba(0,0,0,.06); }}
    h1 {{ margin:0; font-size:40px; letter-spacing:-.02em; }}
    .sub {{ color:var(--muted); margin-top:8px; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    .chip {{ border:1px solid var(--line); border-radius:999px; padding:7px 12px; font-size:13px; color:var(--muted); background:#fff; }}
    .chip b {{ color:var(--text); }}
    .card {{ margin-top:16px; background:var(--card); border:1px solid var(--line); border-radius:20px; padding:18px; box-shadow:0 8px 20px rgba(0,0,0,.04); }}
    ul {{ list-style:none; margin:0; padding:0; }}
    li + li {{ margin-top:10px; }}
    a.item {{
      display:flex; justify-content:space-between; align-items:center;
      text-decoration:none; color:var(--text);
      border:1px solid var(--line); border-radius:14px;
      padding:12px 14px; background:#fafafa;
      transition: all .18s ease;
    }}
    a.item:hover {{ border-color:#cfd3da; transform: translateY(-1px); }}
    .btn {{
      background: linear-gradient(180deg, #2997ff, #0071e3);
      color: #fff;
      border-radius: 999px;
      padding: 7px 14px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: .2px;
      box-shadow: 0 4px 12px rgba(0,113,227,.28);
      border: 1px solid rgba(255,255,255,.35);
      white-space: nowrap;
    }}
    .footer {{ text-align:center; color:var(--muted); margin:18px 0 6px; font-size:13px; }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>全球金融投资日报</h1>
      <div class='chips'>
        <span class='chip'>最新一期：<b>{latest_disp}</b></span>
        <span class='chip'>最近生成：<b>{generated_time}</b></span>
      </div>
    </section>

    <section class='card'>
      <ul>{items}</ul>
    </section>

    <div class='footer'>© Kora Path · Built with OpenClaw</div>
  </div>
</body>
</html>"""
    (ROOT / 'index.html').write_text(html, encoding='utf-8')


def build_daily_md(d):
    def plain(x: str):
        return re.sub(r'<[^>]+>', '', x)

    event_lines = '\n'.join([f"- {h}" for h in d.get('headlines', [])[:5]]) or '- 暂无可用事件标题'

    return f"""# 全球金融投资日报（{d['date']}）

## 🌍 宏观风向标
{d['macro_note']}

## 📰 当日关键事件
{event_lines}

## 🇺🇸 美股聚焦
- {plain(d['us']['dji'])}
- {plain(d['us']['spx'])}
- {plain(d['us']['ndq'])}

{d['us_note']}

## 🇨🇳 A股透视
- {plain(d['cn']['sse'])}
- {plain(d['cn']['sz'])}
- {plain(d['cn']['cyb'])}

{d['cn_note']}

## ⛽️💰 大宗商品
- {plain(d['commodities']['wti'])}
- {plain(d['commodities']['brent'])}
- {plain(d['commodities']['gold'])}
- {plain(d['commodities']['silver'])}

{d['com_note']}

## 💡 策略综述与明日展望
**{d['strategy_note']}**

> 本报告仅作信息参考，不构成投资建议。
"""


def main():
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_data(now)

    # 1) 内容层：先生成主稿（JSON + MD）
    content_json = CONTENT_DIR / f"{data['date']}.json"
    content_json.write_text(json.dumps(build_content_payload(data), ensure_ascii=False, indent=2), encoding='utf-8')

    daily_md = DAILY_DIR / f"{data['date']}.md"
    daily_md.write_text(build_daily_md(data), encoding='utf-8')

    # 2) 渲染层：再根据内容生成 HTML 与首页入口
    daily_html = DAILY_DIR / f"{data['date']}.html"
    daily_html.write_text(build_daily_html(data), encoding='utf-8')

    build_index(data['time'])
    print(f"generated {daily_html} from content/{data['date']}.json")


if __name__ == '__main__':
    main()
