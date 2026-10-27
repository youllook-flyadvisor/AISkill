---
name: find-scout
description: 找出 Dronetag Scout 管理介面（設定頁）目前的網址。當使用者說「找 Scout」「Scout 設定頁在哪」「Scout 位址」「打不開 Scout」「Scout 的 IP 是多少」「連不到 Scout 管理介面」，或要開 Scout 設定頁卻不知道位址時使用。Scout 出廠是 DHCP，位址會隨網路環境改變，所以不能寫死。
---

# 找 Scout 設定頁位址

Dronetag Scout 是只有有線網路的 Remote ID 接收器，接法是 PoE injector → 筆電乙太網路。
它出廠用 **DHCP**，所以位址取決於當下誰在發位址；找不到 DHCP 伺服器時，
約 60 秒後會退回 **`192.168.100.100`**。不同電腦、不同日子位址可能都不一樣，**每次都要現查**。

## 步驟

### 1. 偵測（先看作業系統）

偵測只能**讀**：不改網卡、不改 IP、不改裝置。依使用者的系統二選一：

#### Windows：跑現成腳本

腳本與本檔放在同一個資料夾。**用 `-ExecutionPolicy Bypass -File` 執行**：這只影響這一次的行程，
不會改到系統的執行原則；有些電腦的 LocalMachine 原則是 Restricted，直接跑 `.ps1` 會被擋。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<本 skill 資料夾>\find-scout.ps1"
```

如果路徑含有中文（例如 `桌面`），**不要把中文直接寫進命令字串**，部分 shell 會把它改壞，
導致 `PathNotFound`。改用列舉的方式取得路徑：

```powershell
$desk = (Get-ChildItem "$env:USERPROFILE\OneDrive" -Directory | Where-Object { $_.Name -match '^[\u684C][\u9762]$' }).FullName
```

腳本是**唯讀**的，不會改網卡設定，也不會改裝置。它會依序：

1. 列出有線網卡的狀態與位址
2. 在鄰居表找 Dronetag MAC 前綴 `2C-CF-67` 的位址
3. 對每個候選位址發 HTTPS 請求，回應帶 `X-DRONETAG-PRODUCT: Scout` 標頭的才算數。
   光看 MAC 不可靠：ARP 表裡可能有以前手動加的殘留條目，指到早就不用的位址
4. 都找不到時，對有線網卡所在的 /24 網段平行 ping 一輪，讓 ARP 表暖機後再找。
   Scout 不一定回 ping，但 ARP 照樣會解析出來
5. 最後試出廠退回位址 `192.168.100.100`

#### macOS／Linux：照同樣五步，自己下指令

沒有現成腳本，也**不要叫使用者裝 PowerShell**。照上面同樣的五步，用該系統的內建指令自己查：

| 步驟 | macOS | Linux |
|---|---|---|
| 1. 有線網卡 | `networksetup -listallhardwareports` 找 Ethernet／USB LAN 對應的 `enX`，再 `ifconfig enX` 看 `status: active` 與 `inet` | `ip -4 addr`、`ip link` |
| 2. 鄰居表 | `arp -an` | `ip neigh` |
| 3. HTTPS 驗證 | `curl -k -s -I --connect-timeout 3 --max-time 5 https://<IP>/` | 同左 |
| 4. 網段暖機 | 平行 `ping -c 1 -t 1 <網段>.<1..254>`，等全部結束再讀一次 `arp -an` | 平行 `ping -c 1 -W 1 …`，再讀 `ip neigh` |
| 5. 出廠位址 | 對 `192.168.100.100` 做第 3 步 | 同左 |

要注意：
- **macOS 的 `arp` 會把 MAC 寫成小寫、冒號分隔、省略前導 0**（例如 `2c:cf:67:3:a:1b`）。比對 `2c:cf:67` 前綴時不分大小寫。
- 判定標準跟 Windows 一樣：回應標頭有 `X-DRONETAG-PRODUCT: Scout` 才算找到。光看 MAC 不算。
- 序號在 `WWW-Authenticate` 的 realm 最後一段，只取**末四碼**回報。
- 沒有任何有線網卡是 active → 視為 `NO_LINK`；有線路但五步都沒找到 → 視為 `NOT_FOUND`。
- 可以先寫成暫存 shell 腳本再跑。使用者想留著重複用時，才存成本資料夾的 `find-scout.sh`（一樣只讀，存之前先給他看內容）。

### 2. 依結果回報

Windows 腳本的最後一行是 `RESULT:`；macOS／Linux 由你依同樣的標準自己判定：

| 結果 | 意思 | 怎麼做 |
|---|---|---|
| `FOUND https://x.x.x.x/` | 找到了 | 把網址給使用者，並說明下方的登入步驟 |
| `NO_LINK` | 沒有任何有線網卡連上 | 請使用者檢查：網路線接在 injector 的 **LAN/DATA** 埠（不是 PoE/OUT 埠）、injector 有通電、筆電那端的線有插好 |
| `NOT_FOUND` | 有線路但找不到 Scout | 見下方「找不到時」 |

找到時回報的序號只顯示末四碼。**不要把完整序號寫進回覆或檔案**，它在 Dronetag 雲端 URL 裡等同密碼。
若要自己用 `curl -I` 複查，回應標頭 `X-DRONETAG-SERIAL` 和 realm 都會印出**完整序號**，請過濾掉，例如
Windows：`curl.exe -k -s -I https://x.x.x.x/ | Select-String -NotMatch 'SERIAL|realm'`
macOS／Linux：`curl -k -s -I https://x.x.x.x/ | grep -iv -e serial -e realm`

**HTTPS 標頭驗證過就是答案（Windows 腳本的 FOUND 也已驗證過），不需要再手動複查。**

### 3. 開啟設定頁（告訴使用者）

1. 用瀏覽器開 `FOUND` 給的網址。
2. 憑證是自簽的，會出現「不安全／您的連線不是私人連線」→ 按 **進階 → 繼續前往**。
3. 跳出登入視窗，帳號是 `admin`，**密碼請使用者自己輸入**，不要代填。
4. 瀏覽器的已存帳密是**依位址分開記的**。Scout 換了位址，就要重新輸入一次。

## 找不到時

依序排查，每一項都先問使用者或請他看，不要自行修改系統設定：

1. **Scout 剛通電？** 開機約需 1 分鐘，等一下再跑一次腳本。
2. **電腦有沒有在發 DHCP？** 直連筆電時通常沒有 DHCP 伺服器，Scout 會退回 `192.168.100.100`。
   但筆電要有同網段的位址才連得到：請使用者手動設 `192.168.100.10`、遮罩 `255.255.255.0`
   （需要系統管理員權限，由使用者自己操作），設好後再偵測一次。用完記得改回自動取得。
   - Windows：「乙太網路 → IPv4 內容」
   - macOS：「系統設定 → 網路 → 乙太網路（或 USB LAN）→ 詳細資訊 → TCP/IP」，「設定 IPv4」選「手動」
   ⚠ 如果這張網卡開著 Windows「網際網路連線共用」（ICS，位址是 `192.168.137.1`），
   代表電腦**有在**發 DHCP，Scout 應該會拿到 `192.168.137.x`，不會退回 `.100.100`。
   這時不要手動改 IP（會跟 ICS 衝突、拆掉分享），先回到第 1 點等 Scout 開機完成再跑。
   macOS 的「網際網路共享」也一樣，通常發 `192.168.2.x`。
3. **Scout 被設成固定 IP 了？** 位址可能在別的網段，鄰居表也還沒有它。
   這時腳本找不到，可以請使用者看 Scout 包裝上或前次設定的記錄；最終手段是向 Dronetag 詢問重置方式
   （管理介面上**沒有**恢復原廠設定的按鈕）。
4. 若同時找到多台 Scout（`FOUND` 有多行），請使用者用末四碼序號辨認是哪一台。
