# AISkill

FlyAdvisor 共用的 Claude／AI skill。每個資料夾是一個獨立的 skill，裡面的 `SKILL.md` 是入口。

| 資料夾 | 用途 |
|---|---|
| [`odoo/`](odoo/) | Odoo 報價到期提醒：每天撈快到期／已逾期的報價單，寄提醒信給業務。設定步驟見 `odoo/docs/設定說明書.pdf` |
| [`find-scout/`](find-scout/) | 找出 Dronetag Scout 管理介面目前的網址（Scout 用 DHCP，位址會變） |

## 安裝

把要用的資料夾複製到 Claude 的 skill 目錄（例如 `~/.claude/skills/`），或直接在這個 repo 裡開 Claude。

### 叫 Claude 幫你裝（Windows、Mac 都適用）

複製整段貼給 Claude Code。Claude 會先判斷你的電腦是 Windows 還是 Mac，再一步步帶你裝；
遇到要你決定、或要你自己輸入 key／密碼的地方，它會停下來問你。

只要裝其中一個，就貼那一段；兩個都要就兩段都貼。

**odoo（報價到期提醒）**

```text
請幫我安裝 Claude skill「odoo」（Odoo 報價到期提醒），一步一步帶我做：
1. 先判斷我的作業系統（Windows／macOS／Linux），之後的指令都用這個系統的寫法。
2. 從 https://github.com/youllook-flyadvisor/AISkill 取得 odoo/ 資料夾：有 git 就 clone 到暫存資料夾，沒有 git 就下載 main 分支的 zip 解壓。
3. 把 odoo/ 整個複製到我家目錄下的 .claude/skills/odoo。已經存在就先問我要不要覆蓋。
4. 確認有 Python 3.10 以上（Mac 通常是 python3）。沒有的話告訴我怎麼裝，等我裝好再繼續；不用裝任何套件。
5. 把 .env.example 複製成 .env，但不要替我填任何 key 或密碼。
6. 讀 SKILL.md 和 README.md，用白話告訴我要填哪幾格、去哪裡拿；等我填好，幫我跑一次預覽（不寄信）。
資料夾裡的 .bat 只給 Windows 雙擊用。我如果是 Mac，就直接在終端機幫我跑對應指令。
```

**find-scout（找 Scout 設定頁位址）**

```text
請幫我安裝 Claude skill「find-scout」（找 Dronetag Scout 設定頁位址），一步一步帶我做：
1. 先判斷我的作業系統（Windows／macOS／Linux）。
2. 從 https://github.com/youllook-flyadvisor/AISkill 取得 find-scout/ 資料夾：有 git 就 clone 到暫存資料夾，沒有 git 就下載 main 分支的 zip 解壓。
3. 把 find-scout/ 整個複製到我家目錄下的 .claude/skills/find-scout。已經存在就先問我要不要覆蓋。
4. 讀 SKILL.md。find-scout.ps1 只給 Windows 用；我如果是 Mac 或 Linux，不用裝 PowerShell，之後找 Scout 時照 SKILL.md 的 macOS／Linux 做法現場查。
5. 不要修改電腦的執行原則或網路設定。完成後告訴我：之後只要說「找 Scout」就會觸發。
```

裝完要重開 Claude Code（或開新對話）才會載入新 skill。

## 注意

這是**公開** repo。金鑰、密碼一律放在各自的 `.env`（已列入 `.gitignore`），不要 commit。
