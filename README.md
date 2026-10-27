# AISkill

FlyAdvisor 共用的 Claude／AI skill。每個資料夾是一個獨立的 skill，裡面的 `SKILL.md` 是入口。

| 資料夾 | 用途 |
|---|---|
| [`odoo/`](odoo/) | Odoo 報價到期提醒：每天撈快到期／已逾期的報價單，寄提醒信給業務。設定步驟見 `odoo/docs/設定說明書.pdf` |
| [`find-scout/`](find-scout/) | 找出 Dronetag Scout 管理介面目前的網址（Scout 用 DHCP，位址會變） |

## 安裝

把要用的資料夾複製到 Claude 的 skill 目錄（例如 `~/.claude/skills/`），或直接在這個 repo 裡開 Claude。

### 叫 Claude 幫你裝（複製整段貼給 Claude Code）

只要裝其中一個，就貼那一段；兩個都要就兩段都貼。

**odoo（報價到期提醒）**

```text
請幫我安裝 Claude skill「odoo」：
1. 從 https://github.com/youllook-flyadvisor/AISkill 取得 odoo/ 資料夾
   （有 git 就 clone 到暫存資料夾；沒有 git 就下載 https://github.com/youllook-flyadvisor/AISkill/archive/refs/heads/main.zip 解壓）。
2. 把 odoo/ 整個複製到 ~/.claude/skills/odoo（Windows 是 %USERPROFILE%\.claude\skills\odoo），已存在就先問我要不要覆蓋。
3. 確認 ~/.claude/skills/odoo/SKILL.md 存在，並檢查 python --version 是 3.10 以上（不用裝任何套件）。
4. 在該資料夾把 .env.example 複製成 .env，但不要替我填任何 key 或密碼。
5. 完成後讀 README.md，用白話告訴我接下來要填哪幾格、怎麼先跑預覽（--dry-run）。
```

**find-scout（找 Scout 設定頁位址）**

```text
請幫我安裝 Claude skill「find-scout」：
1. 從 https://github.com/youllook-flyadvisor/AISkill 取得 find-scout/ 資料夾
   （有 git 就 clone 到暫存資料夾；沒有 git 就下載 https://github.com/youllook-flyadvisor/AISkill/archive/refs/heads/main.zip 解壓）。
2. 把 find-scout/ 整個複製到 ~/.claude/skills/find-scout（Windows 是 %USERPROFILE%\.claude\skills\find-scout），已存在就先問我要不要覆蓋。
3. 確認 SKILL.md 和 find-scout.ps1 都在，不要修改電腦的 PowerShell 執行原則。
4. 完成後告訴我：之後只要說「找 Scout」就會觸發。
```

裝完要重開 Claude Code（或開新對話）才會載入新 skill。

## 注意

這是**公開** repo。金鑰、密碼一律放在各自的 `.env`（已列入 `.gitignore`），不要 commit。
