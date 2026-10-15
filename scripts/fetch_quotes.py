"""抓所有持股的每日開高低收，寫入 data/quotes.json 與 data/fx.json。

資料來源（都不用 API key）：
- 美股、台股：Yahoo Finance chart API（台股上市 .TW、上櫃 .TWO，自動判斷）
- 台股備援：證交所 STOCK_DAY_ALL、櫃買中心 mainboard quotes（Yahoo 抓不到時才用）
- 匯率：Yahoo USDTWD=X

用法：python scripts/fetch_quotes.py
持股清單讀 data/symbols.json：[{"mkt": "TW", "sym": "2330"}, {"mkt": "US", "sym": "NVDA"}, ...]
"""
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPE = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (stock-ledger quote updater)"}


def get_json(url, tries=2):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - 網路錯誤一律重試一次
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def yahoo(symbol):
    """回傳最後一個交易日的 {date, open, high, low, close, prevClose, volume}，抓不到回傳 None。"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10d&interval=1d"
    try:
        res = get_json(url)["chart"]["result"][0]
    except Exception:  # noqa: BLE001
        return None
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    tz = timezone(timedelta(seconds=res.get("meta", {}).get("gmtoffset", 0)))
    rows = []
    for i, t in enumerate(ts):
        c = (q.get("close") or [None])[i]
        if c is None:
            continue
        rows.append({
            "date": datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"),
            "open": q["open"][i], "high": q["high"][i], "low": q["low"][i],
            "close": c, "volume": q["volume"][i],
        })
    if not rows:
        return None
    last = rows[-1]
    prev = rows[-2]["close"] if len(rows) > 1 else res.get("meta", {}).get("chartPreviousClose")
    out = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in last.items()}
    out["prevClose"] = round(prev, 4) if prev is not None else None
    return out


def twse_all():
    """證交所上市個股當日行情（備援用）。"""
    try:
        rows = get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for r in rows:
        c = num(r.get("ClosingPrice"))
        if c is None:
            continue
        chg = num(r.get("Change")) or 0
        out[r["Code"]] = {"open": num(r.get("OpeningPrice")), "high": num(r.get("HighestPrice")),
                          "low": num(r.get("LowestPrice")), "close": c, "prevClose": round(c - chg, 4),
                          "volume": num(r.get("TradeVolume"))}
    return out


def tpex_all():
    """櫃買中心上櫃個股當日行情（備援用）。"""
    try:
        rows = get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes")
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for r in rows:
        c = num(r.get("Close"))
        if c is None:
            continue
        chg = num(r.get("Change")) or 0
        out[r.get("SecuritiesCompanyCode")] = {"open": num(r.get("Open")), "high": num(r.get("High")),
                                               "low": num(r.get("Low")), "close": c, "prevClose": round(c - chg, 4),
                                               "volume": num(r.get("TradingShares"))}
    return out


def main():
    symbols = json.loads((DATA / "symbols.json").read_text(encoding="utf-8"))
    old_path = DATA / "quotes.json"
    quotes = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    now = datetime.now(TPE)
    fallback = None
    ok, miss = 0, []
    for s in symbols:
        key = f"{s['mkt']}-{s['sym']}"
        got, src = None, None
        if s["mkt"] == "US":
            got, src = yahoo(s["sym"]), "Yahoo"
        else:
            for suffix in (".TW", ".TWO"):
                got = yahoo(s["sym"] + suffix)
                if got:
                    src = f"Yahoo {suffix}"
                    break
            if not got:
                if fallback is None:
                    fallback = {**tpex_all(), **twse_all()}
                if s["sym"] in fallback:
                    got = {"date": now.strftime("%Y-%m-%d"), **fallback[s["sym"]]}
                    src = "TWSE/TPEx"
        if got:
            quotes[key] = {**quotes.get(key, {}), **got, "mkt": s["mkt"], "sym": s["sym"], "src": src,
                           "updatedAt": now.isoformat(timespec="seconds")}
            ok += 1
        else:
            miss.append(key)
        time.sleep(0.3)

    fx = yahoo("USDTWD=X")
    if fx:
        (DATA / "fx.json").write_text(json.dumps({"USDTWD": round(fx["close"], 4), "date": fx["date"], "src": "Yahoo USDTWD=X"},
                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    old_path.write_text(json.dumps(quotes, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"更新 {ok} 檔，失敗 {len(miss)} 檔{'：' + ', '.join(miss) if miss else ''}；匯率 {fx['close'] if fx else '未更新'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
