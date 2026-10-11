# 全專案複查：問題、修正與剩餘驗收

日期：2026-10-11。對應尚未發布的 `0.1.0-preview.2`。

## 結論

前輪 P0、P1、P2、README／維護配套及選配動態捕捉已完成主要實作；完成紀錄見 [CHANGELOG](../CHANGELOG.md)。本輪重新檢查後端、介面、連接器、安裝與打包，重現並修正下列 **6 個問題**；完成實作不代表乾淨系統、真實帳號及 GitHub 發布驗收已完成。

## 已重現並修正

| 編號／優先序 | 問題及影響 | 修正與回歸證據 |
| --- | --- | --- |
| A01／P1 | 主紀錄缺失／損壞時，新版 schema 備份被當成一般壞備份；後續兩次保存可將唯一新版備份覆寫為 schema 2。有效舊主檔搭配新版備份也有此問題。 | `persistence.py` 在備份恢復與保存前都檢查 FutureState，阻止覆寫主檔及備份。`test_persistence.py` 涵蓋缺失主檔、損壞主檔及有效舊主檔三種情況，核對原內容保留。 |
| A02／P1 | 沒有明確播放器標記的來源只以 URL path 分組；`/stream.mp4?id=A`、`?id=B` 會被當成同一播放器的替代來源，可能自動選錯內容。 | 靜態 literal 與動態 network 分組保留完整媒體 URL 的 query，使用 opaque 雜湊 ID。`test_browser_media.py` 重現靜態及真實 Chrome 網路捕捉兩條路徑；既有同播放器多畫質分組測試仍通過。 |
| A03／P2 | POST `/api/jobs/unknown/<存在的工作 ID>` 落入刪除路由，會移除該清單列。合法來源檢查仍有效，但錯誤本機 API 路徑不應有刪除效果。 | 刪除只接受精確 `/api/jobs/<id>`；未知巢狀路徑回傳 404。`test_p2.py` 核對錯誤路徑後工作及佇列仍存在，合法刪除仍可用。下載檔案不受此路由刪除。 |
| A04／P2 | 刪除保存的 X 登入檔案失敗時，記憶體 Cookie 已清空，但介面仍回報 connected；重新啟動又可能載入尚在磁碟上的登入。 | 停用先完成保存檔移除，再清除記憶體；移除失敗回報 failed，保留一致的登入狀態以便重試。`test_queue_auth.py` 使用合成登入及 PermissionError，核對失敗狀態與成功重試。 |
| A05／P2 | 彈窗焦點管理漏列原生 summary；展開進階 Cookie 設定後按 Tab，焦點跳到關閉鈕，無法依自然順序進入輸入欄。 | 加入 summary 焦點處理。`test_browser_ui.py` 在真實 Chrome 核對 Enter 展開、Tab 到路徑欄、Shift+Tab 返回 summary，以及 Esc 焦點返回。 |
| A06／P2 | 較早的狀態輪詢晚於操作回應返回時，會把剛更新的暫停／下載介面狀態覆蓋；後端工作本身不會因此回退。 | API 在鎖內產生遞增 `state_sequence` 與服務實例 `state_instance`；介面拒絕同實例較舊快照及已退役實例回應。`test_p2.py` 核對序號，Node 測試模擬較晚返回的舊輪詢、暫停操作及服務重啟。欄位成對驗證，仍相容不含此欄位的舊狀態格式。 |

上述測試先在修正前失敗以確認可重現，修正後再通過。用到的資料、網址、Cookie、API 與影片均為隔離測試資料。

程式：[狀態保存](../ssdl/persistence.py)、[靜態解析](../ssdl/web_media.py)、[動態捕捉](../ssdl/browser_media.py)、[API](../ssdl/http_api.py)、[X 登入](../ssdl/x_auth.py)、[狀態快照](../ssdl/app_context.py)、[鍵盤](../static/ui_accessibility.js)、[介面呈現](../static/app.js)。

## 複查範圍

- 下載與排程：單 worker、失敗後繼續、停止／服務關閉、程序範圍、無進度期限、合併活動、Rate／冷卻與帳號逐篇閘門。
- 媒體與去重：來源 query／畫質／播放器身份、manifest、原路徑／大小／修改時間、缺檔補抓、原始位元組、HLS／DASH 缺片與畫質上限。
- 狀態與快取：schema、原子保存、有效備份、恢復、分頁、增量容量、縮圖生成／回收及原檔保留。
- API 與登入：Host／Origin、公開媒體 DNS／數字連線、重新導向及串流子資源、Cookie 配對期限、來源／port、登入保存失敗、診斷遮蔽。
- 介面：離線／逾時／未知操作結果、回應順序、設定草稿、語言、分頁／捲動、播放器選擇、鍵盤／焦點及窄視窗。
- 發布：安裝基準、選配依賴、版本、MIT／第三方說明、Git 排除、允許清單打包及 CI 設定。

本機 **104 項 Python＋10 項 Node 全部通過，沒有略過**；Python 完整執行耗時 52.765 秒。完整測試結果、指令與限制見 [TESTING.md](TESTING.md)。語法、依賴一致性及發布檔案清單另外檢查。這輪沒有新增真實平台下載或使用一般 Chrome 的私人個人檔案。

正式服務已在佇列及登入操作閒置時於一般 Windows 使用者環境重啟，確認 25 筆完成紀錄、每小時上限 80 與 X 已連接狀態保留；13 項環境診斷正常、worker 存活、保存健康，新快照序號生效。只核對摘要，不查看或輸出登入 Cookie。

發布包 `dist/smart-social-downloader-0.1.0-preview.2-source.zip` 已重新生成，包含 113 個允許清單來源檔案；逐項核對與來源位元組一致、ZIP CRC 正常，未包含 `data/`、`downloads/`、`.venv/`、`dist/` 或 `.git/`。語法、套件相依性、626 個中英文 key 與本機文件連結檢查也通過。尚未建立 GitHub repo，這不是已發布的 Release。

## 仍待環境／發布驗收

安裝與 CI 基準統一為 Python 3.12，與本機環境一致；不再把舊版 Python 的測試列為待完成項目。

- [ ] 乾淨 Windows 使用 Python 3.12：首次安裝、一般啟動、選配安裝與更新後的完整流程。
- [ ] 真實 Chrome 連接器重新載入及自訂 port 的帳號配對；合成 API 測試不等同實際登入驗收。
- [ ] 建立 GitHub repo 後執行 CI、檢查首次提交、啟用私人漏洞回報，然後發布 prerelease。
- [ ] 真實平台變動後的解析器與動態播放器驗收。互動式、登入限定、DRM、POST-only 與 WebSocket 媒體仍屬既有支援限制。

CI 使用的 v7 action 已核對官方發布頁：[checkout](https://github.com/actions/checkout/releases)、[setup-python](https://github.com/actions/setup-python/releases)、[setup-node](https://github.com/actions/setup-node/releases)。設定可用版本不代表 GitHub CI 已執行成功。

## 後續工作

本文件保留前輪六項修正的歷史證據。容量／IPC、HTTP 期限、SQLite 維護、架構、GitHub 及 Docker 等未完成工作，以及後續複查的新發現，統一追蹤於 [Roadmap](../ROADMAP.md)。
