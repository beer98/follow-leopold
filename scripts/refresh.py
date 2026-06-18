#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跟着Leopold赚大钱 — 数据刷新管线
用法:
  python3 scripts/refresh.py            # 用缓存的13F + 实时行情,重建 data/data.js
  python3 scripts/refresh.py --edgar    # 重新从 SEC EDGAR 抓全部 13F(出新申报后用)
13F 来源: SEC EDGAR, CIK 0002045724 (Situational Awareness LP)。
行情来源: CNBC restQuote(免key,需浏览器UA)。
"""
import json, os, re, sys, time, urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA_SEC = "follow-leopold zmyroy@gmail.com"
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CIK = "2045724"
BASE = f"https://www.sec.gov/Archives/edgar/data/{CIK}/"

# 本机代理对 sec.gov 掐 TLS,SEC 必须直连;CNBC 直连被挡,必须走系统代理。
def opener(proxy: bool):
    handlers = [] if proxy else [urllib.request.ProxyHandler({})]
    return urllib.request.build_opener(*handlers)

def get(url, ua, proxy, timeout=30, retries=3):
    op = opener(proxy)
    op.addheaders = [("User-Agent", ua)]
    last = None
    for _ in range(retries):
        try:
            return op.open(url, timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f"fetch failed {url}: {last}")

# ───────────────────────── ticker / 板块映射 ─────────────────────────
# key = 发行人名大写去多空格
TICKER = {
    "ADVANCED MICRO DEVICES INC": ("AMD", "芯片·设备", "Advanced Micro Devices"),
    "APPLIED DIGITAL CORP": ("APLD", "数据中心·神经云", "Applied Digital"),
    "ASML HLDG NV N Y REGISTRY": ("ASML", "芯片·设备", "ASML"),
    "BABCOCK & WILCOX ENTERPRISES": ("BW", "电力与能源", "Babcock & Wilcox"),
    "BITDEER TECHNOLOGIES GROUP": ("BTDR", "矿工转AI", "Bitdeer"),
    "BITFARMS LTD": ("BITF", "矿工转AI", "Bitfarms"),
    "BLOOM ENERGY CORP": ("BE", "电力与能源", "Bloom Energy 燃料电池"),
    "BROADCOM INC": ("AVGO", "芯片·设备", "Broadcom"),
    "CIPHER MINING INC": ("CIFR", "矿工转AI", "Cipher Mining"),
    "CLEANSPARK INC": ("CLSK", "矿工转AI", "CleanSpark"),
    "COHERENT CORP": ("COHR", "光学", "Coherent"),
    "CONSTELLATION ENERGY CORP": ("CEG", "电力与能源", "Constellation 核电"),
    "CORE SCIENTIFIC INC NEW": ("CORZ", "数据中心·神经云", "Core Scientific"),
    "COREWEAVE INC": ("CRWV", "数据中心·神经云", "CoreWeave 神经云"),
    "CORNING INC": ("GLW", "光学", "Corning 康宁"),
    "EQT CORP": ("EQT", "电力与能源", "EQT 天然气"),
    "GALAXY DIGITAL INC.": ("GLXY", "矿工转AI", "Galaxy Digital"),
    "HIVE DIGITAL TECHNOLOGIES LT": ("HIVE", "矿工转AI", "HIVE Digital"),
    "HUT 8 CORP": ("HUT", "矿工转AI", "Hut 8"),
    "INFOSYS LTD": ("INFY", "云·软件", "Infosys IT服务"),
    "INTEL CORP": ("INTC", "芯片·设备", "Intel"),
    "IREN LIMITED": ("IREN", "矿工转AI", "IREN 矿转AI算力"),
    "KILROY RLTY CORP": ("KRC", "数据中心·神经云", "Kilroy 地产REIT"),
    "LIBERTY ENERGY INC": ("LBRT", "电力与能源", "Liberty Energy 油服"),
    "LUMENTUM HLDGS INC": ("LITE", "光学", "Lumentum 光模块"),
    "MARVELL TECHNOLOGY INC": ("MRVL", "芯片·设备", "Marvell 定制芯片"),
    "MICRON TECHNOLOGY INC": ("MU", "内存·存储", "Micron 美光"),
    "MODINE MFG CO": ("MOD", "散热·设备", "Modine 散热"),
    "NVIDIA CORPORATION": ("NVDA", "芯片·设备", "NVIDIA 英伟达"),
    "ONTO INNOVATION INC": ("ONTO", "芯片·设备", "Onto 半导体检测"),
    "ORACLE CORP": ("ORCL", "云·软件", "Oracle 甲骨文"),
    "POWER SOLUTIONS INTL INC": ("PSIX", "电力与能源", "Power Solutions 燃气发电机"),
    "PROPETRO HLDG CORP": ("PUMP", "电力与能源", "ProPetro 油服"),
    "RIOT PLATFORMS INC": ("RIOT", "矿工转AI", "Riot Platforms"),
    "SANDISK CORP": ("SNDK", "内存·存储", "SanDisk 闪迪 NAND"),
    "SEAGATE TECHNOLOGY HLDNGS PL": ("STX", "内存·存储", "Seagate 希捷 HDD"),
    "SHARONAI HOLDINGS INC": ("SHAZ", "数据中心·神经云", "SharonAI 澳洲神经云"),
    "SOLARIS ENERGY INFRAS INC": ("SEI", "电力与能源", "Solaris 燃气轮机"),
    "T1 ENERGY INC": ("TE", "电力与能源", "T1 Energy 太阳能+储能"),
    "TAIWAN SEMICONDUCTOR MANUFAC": ("TSM", "芯片·设备", "台积电 ADR"),
    "TAIWAN SEMICONDUCTOR MFG LTD": ("TSM", "芯片·设备", "台积电 ADR"),
    "TALEN ENERGY CORP": ("TLN", "电力与能源", "Talen 核电+燃气"),
    "TOWER SEMICONDUCTOR LTD": ("TSEM", "芯片·设备", "Tower 特色代工"),
    "VANECK ETF TRUST": ("SMH", "芯片·设备", "VanEck 半导体ETF"),
    "VERTIV HOLDINGS CO": ("VRT", "散热·设备", "Vertiv 机柜电源散热"),
    "VISTRA CORP": ("VST", "电力与能源", "Vistra 电力"),
    "WESTERN DIGITAL CORP": ("WDC", "内存·存储", "西部数据 HDD"),
    "WHITEFIBER INC": ("WYFI", "数据中心·神经云", "WhiteFiber AI数据中心"),
}

QUARTER_STAGE = {
    "2024-12-31": "起手式:电力三巨头 VST/CEG/TLN + 机柜VRT + 散热MOD + 定制芯片MRVL——把论文IIIa章(万亿集群的瓶颈)直接换成6只票",
    "2025-03-31": "铺开:加矿转AI(CORZ/APLD/IREN)+天然气EQT+CoreWeave IPO首日进场",
    "2025-06-30": "收缩聚焦:9只——电力VST/CEG/EQT + INTC/AVGO/SMH + 矿转AI三杰",
    "2025-09-30": "全面展开28只:内存复合体(SNDK/MU/WDC/STX)+光学(LITE/COHR)+矿工群进场,撤出公用事业",
    "2025-12-31": "聚焦计权:BE登顶 + CRWV/INTC用call加杠杆 + 光学双雄,纯多头基建书",
    "2026-03-31": "大转向:挂出$8.46B名义put墙(SMH/NVDA/ORCL/AVGO/AMD/MU/TSM/ASML),同时保留电力/内存/神经云多头——多瓶颈,空拥挤",
}

QUOTE_SYMBOLS = ["NVDA","SMH","BE","SNDK","CRWV","IREN","CORZ","APLD","RIOT","CLSK","MU","TSM",
                 "ORCL","AMD","AVGO","ASML","INTC","GLW","INFY","TE","SHAZ","WYFI","PSIX","BW",
                 "PUMP","SEI","BTDR","HIVE",".VIX",".SPX",
                 # 前向荐股池(引擎A/B 用,随 daily.json picks 增删)
                 "AROC","ACLS","LEU","KLIC",
                 # 盘面对照用(电力/大盘/利率)
                 "CEG","GEV",".IXIC","US10Y","VRT","AVGO",
                 # 新候选(变压器咽喉/核能下一棒/私募信贷)
                 "CLF","SMR","OKLO","NNE","APO","POWL","NVT"]

ACCS = [  # (filed, period, accession)  ——新申报出来后在此追加,或用 --edgar 自动发现
    ("2026-05-18", "2026-03-31", "000204572426000008"),
    ("2026-02-11", "2025-12-31", "000204572426000002"),
    ("2025-11-14", "2025-09-30", "000204572425000008"),
    ("2025-08-14", "2025-06-30", "000204572425000006"),
    ("2025-05-14", "2025-03-31", "000204572425000002"),
    ("2025-02-12", "2024-12-31", "000093583625000120"),
]

def local(tag): return tag.split("}")[-1]

def fetch_all_13f():
    """从 EDGAR 抓全部 13F infotable,含申报列表自动发现新季度。"""
    atom = get(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=000{CIK}"
               f"&type=13F&output=atom&count=40", UA_SEC, proxy=False).decode("utf-8","replace")
    accs = []
    for e in re.findall(r"<entry>.*?</entry>", atom, re.S):
        ft = re.search(r"<filing-type>(.*?)</filing-type>", e)
        fd = re.search(r"<filing-date>(.*?)</filing-date>", e)
        href = re.search(r"/(\d{18})/", e.replace("-",""))
        acc = re.search(r"Archives/edgar/data/\d+/(\d+)/", e)
        if ft and "13F-HR" in ft.group(1) and acc:
            accs.append((fd.group(1), acc.group(1)))
    known = {a[2] for a in ACCS}
    out = {}
    for filed, acc in accs:
        idx = json.loads(get(BASE + acc + "/index.json", UA_SEC, proxy=False))
        names = [it["name"] for it in idx["directory"]["item"]]
        xmls = [n for n in names if n.lower().endswith(".xml")]
        prim = [n for n in xmls if "primary_doc" in n.lower()][0]
        info = [n for n in xmls if "primary_doc" not in n.lower()][0]
        pr = ET.fromstring(get(BASE + acc + "/" + prim, UA_SEC, proxy=False))
        period = None
        for c in pr.iter():
            if local(c.tag) == "periodOfReport":
                period = c.text.strip()
        # periodOfReport 形如 MM-DD-YYYY 或 YYYY-MM-DD,统一成 YYYY-MM-DD
        if period and re.match(r"\d{2}-\d{2}-\d{4}", period):
            m, d, y = period.split("-"); period = f"{y}-{m}-{d}"
        root = ET.fromstring(get(BASE + acc + "/" + info, UA_SEC, proxy=False))
        rows = []
        for t in root.iter():
            if local(t.tag) != "infoTable":
                continue
            dd = {}
            for c in t.iter():
                dd[local(c.tag)] = (c.text or "").strip()
            rows.append({"issuer": dd.get("nameOfIssuer",""), "class": dd.get("titleOfClass",""),
                         "cusip": dd.get("cusip",""), "value": int(float(dd.get("value") or 0)),
                         "amt": int(float(dd.get("sshPrnamt") or 0)),
                         "amtType": dd.get("sshPrnamtType",""), "putCall": dd.get("putCall","")})
        out[period] = {"filed": filed, "acc": acc, "rows": rows}
        print(f"  EDGAR {period} (filed {filed}): {len(rows)} rows", file=sys.stderr)
        if acc not in known:
            print(f"  ★ 新申报 {acc},记得把它加进 refresh.py 的 ACCS", file=sys.stderr)
    return out

def fetch_quotes():
    syms = urllib.parse.quote("|".join(QUOTE_SYMBOLS), safe="")
    url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
           f"?symbols={syms}&output=json")
    try:
        d = json.loads(get(url, UA_BROWSER, proxy=True, timeout=20))
        qq = d["FormattedQuoteResult"]["FormattedQuote"]
        out, asof = {}, ""
        for q in qq:
            s = q.get("symbol","")
            if not s or q.get("last") in (None, "", "?"):
                continue
            try:
                last = float(str(q.get("last","")).replace(",",""))
            except ValueError:
                continue
            out[s] = {"last": last, "chg": q.get("change_pct",""), "name": q.get("name","")}
            asof = q.get("last_time","") or asof
        return out, asof
    except Exception as e:
        print(f"  行情拉取失败,保留上次快照: {e}", file=sys.stderr)
        return None, None

def norm_issuer(name):
    return re.sub(r"\s+", " ", name.upper()).strip()

def enrich(raw):
    """整理成季度数组(升序), 行聚合到 (ticker,type)。"""
    quarters = []
    for period in sorted(raw.keys()):
        q = raw[period]
        agg = {}
        for r in q["rows"]:
            key_name = norm_issuer(r["issuer"])
            t = TICKER.get(key_name)
            ticker, sector, cname = t if t else ("", "其他", r["issuer"].title())
            typ = (r["putCall"] or "SH").upper()
            k = (ticker or key_name, typ)
            a = agg.setdefault(k, {"ticker": ticker, "name": cname, "sector": sector,
                                   "type": typ, "value": 0, "amt": 0})
            a["value"] += r["value"]; a["amt"] += r["amt"]
        rows = sorted(agg.values(), key=lambda x: -x["value"])
        tot = sum(r["value"] for r in rows)
        quarters.append({
            "period": period,
            "label": f"{period[:4]}Q{(int(period[5:7])+2)//3}",
            "filed": q["filed"], "acc": q["acc"],
            "stage": QUARTER_STAGE.get(period, ""),
            "totals": {
                "all": tot,
                "sh": sum(r["value"] for r in rows if r["type"] == "SH"),
                "put": sum(r["value"] for r in rows if r["type"] == "PUT"),
                "call": sum(r["value"] for r in rows if r["type"] == "CALL"),
            },
            "n": len(rows), "rows": rows,
        })
    return quarters

def diff(latest, prev):
    L = {(r["ticker"] or r["name"], r["type"]): r for r in latest["rows"]}
    P = {(r["ticker"] or r["name"], r["type"]): r for r in prev["rows"]}
    def fmt(r): return {"ticker": r["ticker"], "name": r["name"], "type": r["type"],
                        "value": r["value"], "amt": r["amt"], "sector": r["sector"]}
    adds   = [fmt(r) for k, r in L.items() if k not in P]
    exits  = [fmt(r) for k, r in P.items() if k not in L]
    ups, downs = [], []
    for k in set(L) & set(P):
        a, b = L[k]["amt"], P[k]["amt"]
        if b and a > b * 1.05:
            ups.append({**fmt(L[k]), "pct": round((a/b-1)*100)})
        elif b and a < b * 0.95:
            downs.append({**fmt(L[k]), "pct": round((a/b-1)*100)})
    for arr in (adds, exits): arr.sort(key=lambda r: -r["value"])
    ups.sort(key=lambda r: -r["value"]); downs.sort(key=lambda r: -r["value"])
    return {"adds": adds, "exits": exits, "ups": ups, "downs": downs,
            "vs": prev["label"]}

def main():
    refetch = "--edgar" in sys.argv
    cache_p = os.path.join(DATA, "cache_13f.json")
    if refetch or not os.path.exists(cache_p):
        print("抓取 EDGAR …", file=sys.stderr)
        raw = fetch_all_13f()
        json.dump(raw, open(cache_p, "w"))
    else:
        raw = json.load(open(cache_p))
    quarters = enrich(raw)
    d = diff(quarters[-1], quarters[-2]) if len(quarters) >= 2 else None

    quotes, asof = fetch_quotes()
    prev_js = os.path.join(DATA, "data.js")
    if quotes is None and os.path.exists(prev_js):  # 行情失败时保留上次
        m = re.search(r"window\.SA\s*=\s*(\{.*\});?\s*$", open(prev_js).read(), re.S)
        if m:
            old = json.loads(m.group(1))
            quotes, asof = old.get("quotes", {}), old.get("quotesAsof", "")

    daily = json.load(open(os.path.join(DATA, "daily.json"))) if \
        os.path.exists(os.path.join(DATA, "daily.json")) else []
    convexity = json.load(open(os.path.join(DATA, "convexity.json"))) if \
        os.path.exists(os.path.join(DATA, "convexity.json")) else []

    bj = timezone(timedelta(hours=8))
    payload = {
        "generated": datetime.now(bj).strftime("%Y-%m-%d %H:%M 北京时间"),
        "quotesAsof": asof or "",
        "meta": {
            "fund": "Situational Awareness LP", "manager": "Leopold Aschenbrenner",
            "cik": "0002045724", "nextDue": "2026-08-14",
            "edgar": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002045724&type=13F",
            "essay": "https://situational-awareness.ai/",
        },
        "quotes": quotes or {}, "quarters": quarters, "diff": d,
        "daily": daily, "convexity": convexity,
    }
    with open(prev_js, "w") as f:
        f.write("window.SA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"OK → data/data.js  ({len(quarters)}季 / 行情{len(quotes or {})}只 / "
          f"日卡{len(daily)}张 / 凸性{len(convexity)}只)", file=sys.stderr)

if __name__ == "__main__":
    main()
