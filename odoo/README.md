# Odoo 報價到期提醒

每天早上 9 點自動讀取 Odoo 的報價單，找出「該追了」的案件，彙整成一封繁體中文信寄給內部業務。
**只讀 Odoo、不改報價單、不寄給客戶、不用 AI。**

---

> 第一次設定請看 **`docs/設定說明書.pdf`**：每個欄位要填什麼、去哪裡找，都有圖文步驟。

## 三步上手

1. **填 key**：把 `.env.example` 複製成 `.env`，填入 `ODOO_URL`、`ODOO_DB`、`ODOO_API_KEY`
   （API Key 在 Odoo 右上頭像 → 我的偏好 → 帳戶安全 → 新增 API 金鑰）
2. **預覽**：`python -m sales_reminder --dry-run`
   畫面上會印出今天那封信的內容，不會真的寄出。
3. **開始寄信**：在 `.env` 填好 SMTP 與收件人，把 `EMAIL_ENABLED` 改成 `true`，再設定每天自動執行（見下方）。

需要 Python 3.10 以上，不必安裝任何套件。

---

## 它會提醒什麼

只看「已發送」的報價（`TRACK_STATES=sent`），到期日一律以報價單上的**有效期限**為準。

| 階段 | 什麼時候 | 例：9/9 報價、10/16 到期 |
|---|---|---|
| 效期過半 | 報價日到有效期限之間過了一半 | 9/28 |
| 即將到期 | 剩 7 天（可設 7–14） | 10/9 |
| 已逾期 | 過了有效期限還沒成交 | 10/17 |

- 同一張報價、同一個到期日、同一階段，**只寄一次**。重跑也不會重寄。
- 業務改了到期日 → 視為新的一輪，重新計算。
- 成交或取消 → 自動停止提醒；寄信前還會再向 Odoo 確認一次狀態。
- 「效期過半」和「即將到期」日期太近（不到 3 天）→ 只寄第二次。
- 建立未滿 1 天、缺少有效期限、逾期超過 30 天的報價 → 略過，原因記在 log。
- 寄信失敗不會記成「已寄」，下次執行會補寄。

---

## 常用指令

```bash
python -m sales_reminder                      # 正式執行（EMAIL_ENABLED=true 才會寄信）
python -m sales_reminder --dry-run            # 只預覽
python -m sales_reminder --dry-run --date 2026-10-09   # 模擬某一天會寄什麼
python -m sales_reminder --status             # 最近 10 次執行紀錄
python -m pytest tests                        # 跑測試
```

執行紀錄、寄送紀錄與 log 都在 `data/` 資料夾。刪掉 `data/reminder.db` 等於清空寄送紀錄，之後會從頭再提醒一輪。

---

## 每天 9:00 自動執行

直接跟 Claude 說「**幫我設定每天自動提醒**」，它會問你手邊有什麼工具，再一步步帶你設好。可用的有：

- **Claude 雲端排程**：電腦不用開著。要把 `.env` 的 `STATE_MODE` 改成 `stateless`。
- **Claude 桌面版排程任務**、**Windows 工作排程器**：電腦要在 9 點開著。
- **Linux 主機 cron**：適合 24 小時開機的主機。

各工具的細節都寫在 `SKILL.md`。同一台機器上就算不小心排了兩個排程，也不會重複寄信。

---

## 想改什麼

**大部分調整只要改 `.env`，不用改程式：**

| 想要 | 改這個 |
|---|---|
| 提早到 10 天前提醒 | `DUE_SOON_DAYS=10` |
| 草稿報價也要追蹤 | `TRACK_STATES=sent,draft` |
| 逾期很久的舊單也要列出 | `OVERDUE_MAX_DAYS=90` |
| 換收件人／多人 | `MAIL_TO=a@公司.com,b@公司.com` |
| 防止誤寄外部信箱 | `INTERNAL_DOMAINS=公司.com` |

**要改邏輯，直接跟 AI（Claude Code）說就好**，例如：
- 「提醒信改成依業務分開寄，每人只收到自己的報價」
- 「信裡加上報價的產品明細」
- 「效期過半改成 60% 才提醒」
- 「另外再提醒超過 14 天沒更新的商機」

AI 會照 `SKILL.md` 的說明找到要改的地方，改完會跑測試。

### 程式在哪裡

| 檔案 | 負責 |
|---|---|
| `sales_reminder/config.py` | 所有設定與預設值 |
| `sales_reminder/rules.py` | **提醒規則**：什麼時候該提醒（純計算，最常改的就是這支） |
| `sales_reminder/odoo.py` | 連 Odoo、讀報價單（只讀） |
| `sales_reminder/mailer.py` | 信件內容與寄送 |
| `sales_reminder/store.py` | 寄送紀錄、執行紀錄、防重複執行 |
| `sales_reminder/main.py` | 主流程與指令 |
| `tests/test_reminder.py` | 驗收測試（不連 Odoo、不寄信） |

---

## 技術備註

- 適用 Odoo 19（實測 19.0+e，Odoo Online），走 JSON-2 API（`/json/2/<model>/<method>`，Bearer API Key）。
- 讀取 `sale.order` 的欄位：`name`、`state`、`partner_id`、`user_id`、`date_order`（報價日）、`validity_date`（有效期限）、`amount_total`、`currency_id`。
- 為什麼不用 Odoo 內建排程：那樣得在 Odoo 裡寫伺服器動作和排程，等於改動正式系統，Dry Run 和測試也不好做。這套程式在 Odoo 外面跑，對 Odoo 只讀不寫。
- API Key 只從 `.env`／環境變數讀取，log 只記單號與原因，不記 key 和客戶資料。
