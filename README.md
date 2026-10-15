# 每日收盤價

用 GitHub Actions 每天抓台股、美股收盤價和美元匯率，存成 JSON。做法和「2330 衝動轉換器」一樣：

- `scripts/fetch_quotes.py`：讀 `data/symbols.json` 的代號清單，抓開高低收、昨收、成交量
  - 美股、台股：Yahoo Finance（台股上市 `.TW`、上櫃 `.TWO` 自動判斷）
  - 台股備援：證交所、櫃買中心 OpenAPI
  - 匯率：Yahoo `USDTWD=X`
- `.github/workflows/update-quotes.yml`：台北時間週一到週五 14:20、16:20（台股）和 06:20（美股）各跑一次，有變動才 commit
- 輸出：`data/quotes.json`、`data/fx.json`、`data/dividends.json`（近一年除息日與每股金額）

這個 repo 只放價格，不放持股股數和成本（那些在私人的 stock-ledger repo）。

## 讀取網址

```
https://raw.githubusercontent.com/nekogugoru/stock-quotes-web/main/data/quotes.json
https://raw.githubusercontent.com/nekogugoru/stock-quotes-web/main/data/fx.json
https://raw.githubusercontent.com/nekogugoru/stock-quotes-web/main/data/dividends.json
```

## 新增或移除代號

改 `data/symbols.json`，格式 `{"mkt": "TW", "sym": "2330"}` 或 `{"mkt": "US", "sym": "NVDA"}`。

## 想立刻更新

Actions → 更新收盤價 → Run workflow。
