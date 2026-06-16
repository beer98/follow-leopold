# 跟着 Leopold 赚大钱 · Situational Awareness 实盘罗盘

把 Leopold Aschenbrenner 的世界模型(《Situational Awareness》)、他基金的 SEC 13F 实盘、
每日框架推演、和 Serenity 式凸性筛选,压成一页可一眼扫完的纸面作战室。

## 两页结构

**首页 index.html(收敛层,每天看)**:大头像+战绩(费后收益/13F增长/金主/实盘代表作收据)→ 当日判断(红黄绿章+一句话+三条证据)→ 今日荐股(质量栏卡片:他持有/延伸/回避,链·未定价·风险)→ 数据室入口。

**次页 deep.html(数据室,深挖用)**:

| 层 | 内容 | 性质 | 更新节奏 |
|---|---|---|---|
| 壹 世界模型 | 论文因果链 + 投资转译 + 两年体检 | 稳定 | 他出新文章才动 |
| 贰 实盘 13F | 6 季持仓演化、多头书、PUT 墙、季度变动(**过去式,校准用,非抄作业**) | **事实**(EDGAR 一手) | 每季 13F 截止后 1~3 天 |
| 叁 推演档案 | 事实层(带来源)→框架透镜→三层推演→Review | 事实/推演分离标注 | 有料才更,无料停更 |
| 肆 凸性雷达 | 他书里的尾部小票 = 他的凸性下注;延伸候选过质量栏才入池 | 事实+标注推演 | 随每日推演喂入 |

每日卡 schema(`data/daily.json` 数组首条):`judgment{tone,light,line,drivers}` 喂首页当日判断,`picks[{ticker,tag,tone:buy|watch|avoid,action,chain,unpriced,risk}]` 喂首页荐股,其余字段(facts/lens/orders/review/stance)喂数据室档案。

## 维护

```bash
python3 scripts/refresh.py          # 重拉行情 + 重建 data/data.js(日常)
python3 scripts/refresh.py --edgar  # 新 13F 出来后:重抓 EDGAR 全部申报
```

- 13F 节奏:Q2'26 截止 **2026-08-14**(之后顺延每季 45 天)。
- 每日推演:编辑 `data/daily.json`(新条目插到数组最前),再跑 refresh.py。
- 凸性池:编辑 `data/convexity.json`,入池必须过页面底部的质量栏。
- 网络注意(本机):**SEC 必须绕过系统代理直连**(脚本已处理);CNBC 必须走代理 + 浏览器 UA。

## 数据源

- SEC EDGAR,CIK [0002045724](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002045724&type=13F)(Situational Awareness LP 全部 13F-HR)
- [situational-awareness.ai](https://situational-awareness.ai/)(原典)
- CNBC restQuote(行情快照)

## 部署

```bash
cd ~/follow-leopold
export npm_config_cache=/private/tmp/follow-leopold-npm-cache
npx --yes vercel@latest deploy --prod --yes --token "$(cat ~/.vercel_token)"
```

## 诚实边界(读数前必看)

1. 13F 滞后 45 天,只含美股多头与持有期权,不含空头现货/海外/现金;
2. 期权按底层名义市值申报,无行权价与到期日;
3. 13F 市值增长含申购,**不是**基金收益;
4. 本页不构成投资建议;所有「推演」可能完全错误。
