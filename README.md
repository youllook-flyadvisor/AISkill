# AISkill

FlyAdvisor 共用的 Claude／AI skill。每個資料夾是一個獨立的 skill，裡面的 `SKILL.md` 是入口。

| 資料夾 | 用途 |
|---|---|
| [`odoo/`](odoo/) | Odoo 報價到期提醒：每天撈快到期／已逾期的報價單，寄提醒信給業務。設定步驟見 `odoo/docs/設定說明書.pdf` |
| [`find-scout/`](find-scout/) | 找出 Dronetag Scout 管理介面目前的網址（Scout 用 DHCP，位址會變） |

## 安裝

把要用的資料夾複製到 Claude 的 skill 目錄（例如 `~/.claude/skills/`），或直接在這個 repo 裡開 Claude。

## 注意

這是**公開** repo。金鑰、密碼一律放在各自的 `.env`（已列入 `.gitignore`），不要 commit。
