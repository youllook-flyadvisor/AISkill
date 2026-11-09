---
name: mocker
description: 操作 Dronetag Mocker 建立虛擬飛行、列出虛擬設定資料、結束模擬。當用戶說「建一架虛擬飛行」「開個模擬」「跑 Mocker」「列出虛擬設定」「現在有哪些模擬在跑」「結束模擬」「/mocker」，或要用模擬資料測 Dronetag Data Push 整合時使用。
---

# Mocker 虛擬飛行

[Dronetag Mocker](https://mocker.dronetag.app) 是 Dronetag 官方給開發者用的模擬工具，不用實機就能產生虛擬飛行資料，用來測整合
（官方說明：[Using Simulated Data](https://help.dronetag.com/developers/guides/using-simulated-data/)）。

這個 skill 用 **Claude in Chrome** 開 Mocker 網頁，在頁面注入 `mocker-helper.js`，
之後全部透過 Mocker 網頁自己的 REST API（`/api/v1/simulations/`）操作，不點下拉選單。

## 事前準備

- 先寫信向 Dronetag 申請**虛擬裝置**。Mocker 的使用權限通常會跟第一台虛擬裝置一起開通。
- 瀏覽器要安裝 Claude in Chrome 擴充功能，而且要在**有 Mocker 權限的 Dronetag 帳號**登入。
- 模擬資料跟實體裝置一樣，會走該帳號設定的 Data Push。

## 安全

- Token 只存在頁面記憶體，**絕不印出、不寫檔、不放進回覆**。
- 頁面出現 SIGN IN 時，請用戶自己登入。不代填帳號密碼。

## 步驟

1. 用 Claude in Chrome 開新分頁到 `https://mocker.dronetag.app`。
2. **注入 helper**：Read 本 skill 資料夾裡的 `mocker-helper.js`，把整段內容丟給 `javascript_tool` 執行。可以重複執行，結果一樣。
3. **拿 token**：
   1. 用 `computer` **真的點一下地圖空白處**，會開出 Create Simulation 視窗。
   2. 按 `Escape` 關掉視窗。
   3. 執行 `await mk.ready()`，回 `ready` 才繼續。
   - 回 `NO_TOKEN` 就重點一次。合成事件點不開視窗。
   - 先注入 helper 再點地圖。順序反了攔不到 token。
   - Token 會過期。之後任何呼叫報 401，就重做這一步。
4. 依需求呼叫下面的 API，結果用 `await mk.table()` 回報給用戶。
5. 到用戶自己的 Data Push 接收端（例如自家平台）確認資料有收到。
6. **收尾一定執行 `await mk.endAll()`**，再用 `mk.table()` 確認回傳「目前沒有執行中的模擬」。

## API（`window.mk`）

| 呼叫 | 用途 |
|---|---|
| `mk.create({engine, scenario, at, ...})` | 建立模擬，回 `{sent, created}` |
| `mk.table()` | 列出目前所有模擬的設定和即時狀態（Markdown 表）。「列出虛擬設定資料」用這個 |
| `mk.list()` | 同上，回 JSON 物件。含完整 `state`：位置、速度向量、電量、衛星數、RSRP 等 |
| `mk.schema(engine, scenario)` | 該組合的表單定義：必填欄位、可選的 Sensor ID 和 UAS ID、逾時選項 |
| `mk.end(uasId)` | END FLIGHT（`?kill=false`） |
| `mk.kill(uasId)` | FORCE KILL（`?kill=true`） |
| `mk.endAll()` | 全部正常結束 |
| `mk.pause(uasId, true/false)` | 暫停或恢復 |
| `mk.setState(uasId, {location:{latitude,longitude,altitude}, battery_percentage,...})` | 注入狀態，例如手動移動位置、改電量 |

路徑參數一律用 **uas_id**，不是 list 裡的 UUID。

### create 參數

| 參數 | 預設 | 說明 |
|---|---|---|
| `engine` | 必填 | `nri_via_live`（網路 RID）、`nri_via_funnel`（網路 RID 系列，可指定傳輸方式）或 `dri_via_funnel`（接收器偵測） |
| `scenario` | `circle` | `circle`、`random` 或 `realistic_survey` |
| `at` | `'neihu'` | 預設點名稱或 `{lat, lon}`。`neihu` 是臺北市內湖運動中心（25.07820, 121.57503）。可在 helper 的 `PRESETS` 加自己的點 |
| `alt` | 100 | 起點高度（m） |
| `uas_id` | 自動 | 兩種 nri 只能用虛擬裝置序號，會自動帶入。dri 會自動產生 `1596F…` |
| `sensor_id` | 自動 | dri 必填，會自動帶入帳號下可選的虛擬裝置 |
| `radius` | 150 | circle 的半徑（m） |
| `speed` | 30 | 速度（km/h），circle、random、survey 都會用 |
| `passes` | 5 | realistic_survey 的趟數 |
| `length` | 200 | realistic_survey 每趟長度 |
| `separation` | 10 | realistic_survey 的趟距 |
| `altVar` | 3 | realistic_survey 的高度擾動 |
| `tech` | `bluetooth_long_range` | 只有 nri_via_funnel 有：`bluetooth_long_range` 或 `ads_b` |
| `timeout` | 900 | 逾時秒數：900、1800 或 3600 |
| `interval` | 500 | 取樣間隔（ms），最少 50 |

範例：`await mk.create({engine:'dri_via_funnel', scenario:'realistic_survey', speed:30})`

## 實測限制（2026-11，Mocker 0.22.0）

- 兩種 nri 引擎都綁同一台虛擬裝置的序號，所以**同一台虛擬裝置同時只能跑一個 nri**。dri 可以和 nri 一起跑。
- **nri_via_funnel 選 `ads_b` 時，Data Push 只送一筆 operation-update，沒有位置資料（tele-ua）**。需要位置就用 `bluetooth_long_range`。
- 結束訊號只有 `nri_via_live` 的 END FLIGHT 會送出飛行結束狀態。nri_via_funnel、dri 和 FORCE KILL 都只是停止送資料，接收端要靠逾時判斷訊號中斷。
- 模擬的高度和速度不等於設定值。dri 的速度一直是 0，nri 的高度會到數百公尺。
- `realistic_survey` 的航線：
  - 起點在西南角，東西向來回飛，每趟往北推進一個趟距。
  - 掃完斜線飛回起點，然後無限重複。
  - 不能設定方向、航點或排程。
- Mocker 自己的地圖固定顯示布拉格，不會跳到起點。要看位置，請用接收端或 `mk.table()`。
- 關掉瀏覽器後模擬還會繼續跑，到逾時才結束。所以收尾一定要執行 `endAll()`。
- javascript_tool 的回傳如果含 `key=value` 長字串，會被擋下（BLOCKED: Cookie/query string data）。輸出請改用 `:` 或空白分隔。
- 這個 skill 用的是 Mocker 網頁自己的 API（頁面上有 `/openapi.json`）。官方沒有把它當公開 API 發布，改版時可能失效。
- 官方提醒：模擬資料不一定和實機相同，上線前仍要用實體裝置測過。

## 參考

- 官方說明：<https://help.dronetag.com/developers/guides/using-simulated-data/>
- 完整 API：Mocker 頁面上的 `/openapi.json`（需要 token）。用 OPTIONS 呼叫 `/api/v1/ui/simulations?scenario=&engine=`，會回表單定義。
