---
name: odoo
description: Odoo 報價到期提醒系統的操作與修改。當使用者說「跑報價提醒」「預覽今天的提醒信」「改提醒規則」「提醒要提早幾天」「提醒信加欄位」「報價提醒沒寄出」「設定每天自動提醒」，或要調整 Odoo 報價追蹤／到期通知時使用。
---

# Odoo 報價到期提醒

使用者會直接用口語要你改這套系統。你的任務是讓它照他要的方式運作，改完驗證，並用白話告訴他改了什麼。

先讀同資料夾的 `README.md`，裡面有規則、指令、檔案分工。

## 改之前先判斷

1. **改 `.env` 就能做到的**（天數、收件人、追蹤狀態）→ 只改 `.env`，不動程式。
2. **改規則**（什麼時候提醒）→ 只動 `sales_reminder/rules.py` 的 `evaluate()`，並在 `tests/test_reminder.py` 補上對應測試。
3. **改信件內容** → `sales_reminder/mailer.py` 的 `build()`。
4. **要讀更多 Odoo 欄位** → 在 `sales_reminder/odoo.py` 的 `FIELDS` 和 `to_quote()` 加欄位，`rules.Quote` 同步加。不確定欄位名稱時，先用 `fields_get` 查實際欄位，不要猜。
5. **新增別種提醒**（例如停滯商機）→ 另寫一支讀取函式加一個規則函式，沿用 `main.run()` 的去重與寄信流程；不要把邏輯塞進現有的報價規則裡。

## 鐵律

- **對 Odoo 只讀**：只能呼叫 `search_read`、`fields_get`、`search_count` 這類讀取方法。要寫入 Odoo，必須先問使用者。
- **不寄給客戶**：收件人只來自 `.env` 的 `MAIL_TO`；`INTERNAL_DOMAINS` 檢查不可拿掉。
- **API Key 不進程式碼、log 或聊天內容**。
- **改完一定要跑**：`python -m pytest tests`，以及 `python -m sales_reminder --dry-run`，把預覽結果給使用者看（macOS／Linux 把 `python` 換成 `python3`）。
- 沒有 `.env` 時，請使用者照 README「三步上手」填 key，不要自己找別處的 key 來用。

## Windows 以外的電腦

程式本身只用 Python 標準函式庫，Windows、macOS、Linux 都能跑。只有啟動方式不同：

- 先跑 `python3 --version`（Windows 是 `python --version`）確認 3.10 以上。沒有的話，帶使用者到 python.org 下載安裝，裝好再繼續。
- `1-預覽提醒信.bat`、`2-寄出提醒信.bat`、`run.bat` 只給 Windows 雙擊用。Mac 使用者要預覽或寄信時，由你在終端機幫他跑
  `python3 -m sales_reminder --dry-run`／`python3 -m sales_reminder`；寄信前一樣先問他。
- Mac 使用者要求「做成可以雙擊的檔」時，才幫他做 `.command` 檔（內容先 `cd` 到本資料夾，再跑上面的指令，並 `chmod +x`）。
  第一次開啟會被擋，請他到「系統設定 → 隱私權與安全性」按「仍要打開」。
- `docs/設定說明書.pdf` 的截圖是 Windows 畫面。Odoo 與 Gmail 的設定步驟在 Mac 上相同，只有「雙擊 .bat」那一步改由你代跑。

## 帶使用者設定「每天 9:00 自動執行」

使用者說「設定每天自動提醒」時，由你帶他用**他手邊有的工具**設起來，不要替他決定。

**先確認三件事**：`.env` 已填好、`--dry-run` 跑得出預覽、已經用他同意的收件人實寄過一封測試信（寄信前要先問他）。

**再問他要用哪一種**，照對應做法帶他完成：

| 工具 | 適合 | `STATE_MODE` | 做法 |
|---|---|---|---|
| Claude 雲端排程（routine） | 電腦不用開著 | `stateless` | 見下方 |
| Claude 桌面版排程任務 | 已經在用 Claude 桌面版 | `db` | 建每天 09:00 的排程任務，內容：「在 <資料夾> 執行 `python -m sales_reminder`，回報最後一行結果；失敗就說明原因」 |
| Windows 工作排程器 | 公司電腦每天都開機 | `db` | `schtasks /Create /TN "Odoo報價提醒" /SC DAILY /ST 09:00 /TR "\"<資料夾>\run.bat\""` |
| macOS launchd | 公司 Mac 每天都開機 | `db` | 在 `~/Library/LaunchAgents/` 建 plist：`StartCalendarInterval` 設 09:00，執行 `/bin/sh -c 'cd <資料夾> && python3 -m sales_reminder'`。先給使用者看內容，再用 `launchctl load` 啟用 |
| Linux 主機 cron | 有 24 小時開機的主機 | `db` | `CRON_TZ=Asia/Taipei` 加 `0 9 * * * cd <資料夾> && python3 -m sales_reminder` |

**Claude 雲端排程要注意**（用 `/schedule` 建立）：
1. 雲端每次都是全新環境，`data/` 留不住，所以 `.env` 要設 `STATE_MODE=stateless`（每個階段只在開始那天寄；缺點是某天沒跑成，那天的提醒不會補寄）。
2. 程式要放在雲端拿得到的 **private** GitHub repo；`ODOO_API_KEY`、`SMTP_PASSWORD` 這類密碼設在雲端環境的環境變數，**不要 commit 進 repo**。
3. 雲端時間是 UTC：台灣 09:00＝cron `0 1 * * *`。
4. 雲端網路不一定放行 Odoo 與 SMTP（port 587）。建好後先手動觸發一次，確認結果是 `ok` 或 `nothing`，不是連線錯誤。

**設好之後**：手動觸發一次，再用 `python -m sales_reminder --status` 或排程的執行紀錄確認，結果給使用者看。

## 回報方式

用白話說明：改了什麼、從哪天開始生效、dry run 的預覽長怎樣。不要貼程式碼 diff，除非使用者要求。
