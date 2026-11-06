# Roadmap

更新：2026-10-29。此檔是**未完成工作與最新審查發現的唯一總清單**；完成紀錄移至 [CHANGELOG](CHANGELOG.md)。目前基準為 Windows／Python 3.12，沒有 Python 3.10 驗收工作。未勾選項目尚未完成；已勾選階段仍以所列驗收範圍為準，不代表已發布。N01～N08 已完成並移到 [CHANGELOG](CHANGELOG.md#unreleased)，回歸結果見 [TESTING](docs/TESTING.md)。N07 的索引評估已記錄，實際索引／游標儲存列為後續選配，尚未實作。

## 本輪整體審查

重新檢查 API／本機來源政策、Chrome 登入、下載與串流、排程／子程序、保存／去重、前端／設定、檔案架構、安裝與發布。既有 P0／P1／P2 的主要功能與本輪 N01～N08 已實作，仍有下列環境驗收與選配工作；功能完成不等於沒有 bug。前輪六個已修正問題保留於 [歷史審查](docs/PROJECT_AUDIT.md)，不與本輪待辦項目混用。

審查與回歸使用暫存目錄、隔離 HTTP 服務及合成資料重現。本機套用狀態另記於 CHANGELOG；測試沒有讀取真實 Cookie 或下載外部平台媒體。這是程式審查與有限的故障重現，不是完整滲透測試或所有依賴的漏洞掃描。

N01～N08 已移至 [CHANGELOG](CHANGELOG.md#unreleased)。本輪列出的修正與維護改善已完成，仍需以下環境／發布驗收及選配功能；不代表沒有其他潛在缺陷。[N08 共用 fixture 與來源包驗收](docs/SOURCE_TESTING.md) 已實作，HTTP 讀取期限、併發限制與輸入契約見 [可靠性文件](docs/RELIABILITY.md)。

## 架構與檔案結構

目前根目錄入口＋`ssdl/`／`static/`／`chrome-extension/`／`tools/`／`docs/`／`tests/` 的分層保留。AppContext 與共用測試 fixture 已實作，runtime 位置保持相容；完整樹見 [ARCHITECTURE](docs/ARCHITECTURE.md)。

每次只改一個責任邊界，維持入口、API、資料路徑及 Chrome extension ID 相容；共用鎖與關閉順序已列於架構文件。

## Windows 桌面版：先 pywebview，保留 Electron 遷移路線

2026-10-26 規劃，D01～D03 已完成並記錄於 CHANGELOG；D04 自動化與目前 Windows 主機的人工基線驗收已完成，額外環境限制列於驗收指南。D05 的資料夾型發行包、安裝程式與目前主機驗收已實作，乾淨 Windows 驗收仍待環境；D06 保留後續。決策依據為使用者指定的「先做 pywebview，業務功能走標準 API，桌面專屬功能集中封裝」，並參考 [Python WebUI 轉 Windows GUI 對話](chatgpt-conversation://6ade3c59-7034-83e8-843b-79c106709fe9)。目標是瀏覽器版與桌面版共用同一份 Web UI／Python 後端，日後替換外殼時保留業務程式與資料。

### 現況判斷與必要前置

**現有前後端已具備可沿用的分離，不需要先重寫或拆成兩個 repository。** `static/` 提供 HTML／CSS／JavaScript，`static/api.js` 集中 HTTP／JSON 請求與回應檢查，`ssdl/http_api.py` 提供路由，`AppContext`／scheduler／repository 處理工作與保存。先補齊桌面差異的 Interface 與生命週期，再接 pywebview；不把改用 FastAPI、React、TypeScript、bundler 或 WebSocket 列為前置。

以下盤點以 D01 實作前的結構為基準；各階段完成紀錄見下方與 CHANGELOG。

| 原始位置 | 規劃當時的能力／耦合 | 需要的調整 | 時機 |
| --- | --- | --- | --- |
| `static/api.js`、各 controller | 已透過 HTTP 操作工作、設定、登入及診斷；API client 有期限、取消、schema 與不確定寫入結果處理 | 整理共用業務契約；controller 不直接使用外殼 bridge | D01，GUI 前 |
| `static/jobs_controller.js`、`diagnostics_controller.js`、登入腳本 | 分散使用 `window.open`、Blob 匯出、剪貼簿及 browser／desktop 檔案操作分支 | 以集中式 `DesktopInterface` 與 Browser／Pywebview Adapter 承接實際差異 | D01／D03 |
| `ssdl/http_api.py` | 開資料夾／開檔路由內直接呼叫 `os.startfile` | 路徑與工作檔案驗證留在後端；Windows 分派集中至平台 Module | D01，GUI 前 |
| `ssdl/desktop_service.py`、`tools/manage.py`、`ssdl/app.py` | 已有 Windows 互斥鎖、ready／stop／done、日誌及正常關閉；啟動成功會直接開瀏覽器 | 分離「確保服務可用」與「顯示介面」，形成可供不同外殼使用的控制 Interface | D02，GUI 前 |
| `AppContext.ROOT`、`desktop_service.ROOT`、`job_runtime.py` | 靜態資源、狀態／登入／SQLite、cache 及預設 downloads 依賴專案 root；子程序使用 `sys.executable -m ...` | 開發版保留現有位置；安裝版前分開資源與可寫資料，定義 frozen EXE 的 backend／worker 入口 | D05，安裝版前；不阻塞來源版原型 |

### 共用架構與責任

```text
共用 static/ Web UI
  ├─ SSDLApi → 同源 HTTP／JSON → Python 工作／設定／登入／媒體／保存
  └─ DesktopInterface → Browser Adapter 或 Pywebview Adapter
                                      └─ 未來 Electron preload／IPC Adapter

桌面外殼 → BackendSupervisor 的控制 Interface → 獨立 Python 後端程序
```

`DesktopInterface` 是放置可替換實作的 Seam；Browser 與 Pywebview 是第一批實際 Adapter，Electron 先記錄對應方式，不建立沒有使用者的空實作。外殼只處理視窗、原生互動與後端程序管理，不能擁有第二份佇列、下載狀態、資料庫、登入憑證或下載引擎。

建議落點為 `static/desktop.js`（Interface／組裝與 Browser Adapter）、`static/desktop_pywebview.js`（唯一直接接觸 pywebview bridge 的前端 Adapter）、`ssdl/platform_actions.py`（後端 OS 分派）、`ssdl/desktop_control.py`（Supervisor／薄控制入口）及 `desktop/pywebview_app.py`（GUI 啟動與視窗）。現有 `desktop_service.py` 的 Windows 控制實作繼續沿用；名稱與檔案數於實作時依責任調整，不先建立空檔案。未來 Electron 的主程序／preload／打包設定再放入獨立外殼目錄。

| Interface | 職責與契約 |
| --- | --- |
| `SSDLApi` | 工作加入／暫停／停止／重試、設定、X／Pixiv 授權狀態、診斷、檔案清單及媒體內容一律使用共用 HTTP API；保留相對 `/api/...`、現有輪詢與錯誤語意。只有實際需求與量測支持時才增加 SSE／WebSocket。 |
| `DesktopInterface` | 由組裝入口注入 controller；集中原生選擇資料夾、開外部連結、診斷匯出及必要的視窗操作。動作方法使用 Promise、可序列化資料及一致的取消／不支援／錯誤結果；保留點擊手勢的分頁預留及 dispose 是同步的本機生命週期操作，不跨 bridge；先訂版本與能力清單，能力缺少時保留瀏覽器替代操作，不依 user-agent 猜測。 |
| 工作檔案與 OS 操作 | 前端以工作 ID、檔案索引與既有檔名核對欄位提出開檔／顯示位置需求。後端保留檔案範圍、存在性、類型及過期選取驗證，再交平台 Module 執行 OS 分派；不讓 renderer 以任意路徑或 shell command 繞過驗證。現有 HTTP 開檔路由維持相容。 |
| `BackendSupervisor` | 集中啟動／附接、就緒、身分與版本核對、服務擁有權、正常停止及錯誤處理。pywebview 呼叫共用 Python 實作；為未來 Electron 保留薄的控制 CLI／私有程序通道與 JSON 結果／退出碼，不在 JavaScript 重寫服務管理。控制協定與業務 HTTP 分開，不新增無保護的 HTTP 關機入口。 |

一般 controller 不直接存取 `window.pywebview.api`、`ipcRenderer`、Node／Python 物件或框架型別；框架偵測、bridge ready 時序及轉換只在 Adapter／組裝入口。bridge 僅暴露必要桌面方法，不能把整個 AppContext 或任意 method／IPC channel dispatcher 交給網頁。若新增本機驗證憑證，使用外殼無關的協定，不能把業務 HTTP 契約綁到 `pywebview.token`。

### D01：共用契約與平台操作（已完成）

2026-10-26 完成，實作／測試範圍見 [共用契約](docs/API_CONTRACT.md) 及 [CHANGELOG](CHANGELOG.md#unreleased)。業務 API 保留；Browser Adapter 已承接開頁、配對分頁預留、診斷下載、剪貼簿與取消清理，Windows 開檔分派集中於平台 Module。未宣稱 pywebview／WebView2 已驗收。

### D02：後端與視窗生命週期（已完成）

2026-10-26 完成，見 [Supervisor 契約](docs/DESKTOP_CONTROL.md) 及 [CHANGELOG](CHANGELOG.md#unreleased)。啟動／附接與開頁分離；核對 Windows 控制鎖、HTTP 身分、版本及執行個體，缺引擎仍可取得 UI／API 就緒。外殼停止使用執行個體專屬事件；單視窗與喚回事件已通過原生雙程序驗證，關閉視窗控制不停止後端。真正 GUI 與關窗提示由 D03 接上。

### D03：pywebview／WebView2 來源版本（已完成）

2026-10-26 完成，使用方式見 [桌面指南](docs/DESKTOP_GUI.md)，實作與證據見 [CHANGELOG](CHANGELOG.md#unreleased) 及 [測試紀錄](docs/TESTING.md)。`desktop.bat` 使用選配鎖定依賴載入相同 HTTP UI；原生視窗、資料夾選擇、診斷另存、專用 profile、關窗續抓與明確停止均已接上。原生 guard 限制導航／frame／彈窗與 bridge 訊息來源，X／Pixiv 授權沿用一般 Chrome。

兩次真實 WebView2 隔離啟動已驗證 UI／bridge、共用 HTTP 寫入、重複開啟喚回、語言／頁數保存、拒絕導航後 bridge 仍可使用、關窗續留後端與 owned stop；當前實際 devicePixelRatio 為 2。D03 是來源版本與基本 smoke；D04 擴充結果列於下方，也不是 D05 安裝包。

### D04：共用介面與實際 Windows GUI 驗收（目前主機基線完成）

- [x] 以同一組 Interface 契約驗證 Browser／Pywebview Adapter，包括能力缺少、bridge 尚未就緒、取消、拒絕、逾時及視窗已關閉；業務測試跨 HTTP 執行，不為每個外殼複製下載引擎／佇列測試。核心匯入與實際 HTTP 請求在禁止 GUI 匯入的獨立 interpreter 通過；一般 Web／Docker 與既有 CI 不增加 GUI 套件。
- [x] 在暫存資料與專用 profile 自動化驗收真實 WebView2：啟動、既有／重複／同時啟動、埠衝突、後端退出、關窗續抓、明確停止與重啟恢復；缺少套件／Runtime 有明確失敗碼，不能跳過當作通過。實際未安裝 Runtime 的乾淨機器與人手操作仍屬人工觀察；實機 GUI 與 Chrome fixture 證據分列。
- [x] 對照瀏覽器版與桌面版的工作／設定／錯誤／語系／媒體頁：鍵盤與焦點、捲動、100／125／150／200% DPI、中文及空白路徑、資料夾選擇取消、開檔／顯示位置、圖片及影片 Range／播放、Blob 匯出、剪貼簿、外部頁與一般 Chrome 授權回接。以相同 viewport 截圖比較；訂明可接受的原生視窗／字型差異，不宣稱不同引擎逐像素相同。

2026-10-26 已新增 `tools/check_desktop_gui.py --matrix` 與 [D04 驗收指南](docs/DESKTOP_GUI_ACCEPTANCE.md)。WebView2／Chrome 共用 UI 流程與 1280×800 CSS viewport 截圖、實際圖片／影片／Range、原生剪貼簿還原及瀏覽器 Blob 已通過；原生對話框回傳與檔案／外部分派明確標示為注入／攔截。四種 renderer scale 是 CDP 模擬，與使用者另外完成的實際 Windows 100／125／150／200% 縮放分列。人工已確認鍵盤／原生對話框與提示、中文空白路徑、開檔／位置／外部頁、覆寫與唯讀拒絕、桌面發起的 X／Pixiv 一般 Chrome 回接及後端重啟登入保留；第 2 輪關窗續留後端後，已清除隔離登入、正常停止 8877 並恢復連接器 8765。每個比例重新啟動、多螢幕 DPI、真實剪貼簿權限拒絕與未安裝 Runtime 的乾淨機器未測，詳見指南；D04 完成範圍如驗收指南。

### D05：Windows 發行包與安裝版（實作／目前主機通過；乾淨機器待驗收）

- [x] 在打包前區分唯讀程式資源、使用者資料／登入／SQLite、cache／WebView profile 與使用者選擇的媒體目錄。開發版預設保持既有路徑；安裝版使用可寫使用者目錄並提供有備份與回退的明確遷移，不把資料寫進 Program Files 或 onefile 解壓暫存目錄，不因切換外殼就另建一份歷史／登入。服務／視窗互斥與擁有權識別須對齊同一資料 scope，不能因版本安裝位置不同而允許兩個 backend 共寫。需跨外殼保存的語言／清單偏好採有版本的中立資料格式或共用 API，不以複製 WebView2 profile 到 Electron 作為遷移機制。
- [x] 處理 `desktop_service` 與 `job_runtime` 目前依賴 `sys.executable -m ...` 的 frozen 相容性：定義 GUI／backend／下載 worker 的明確程序角色與啟動方式，避免 EXE 子程序遞迴開 GUI；驗證 FFmpeg／Node／下載引擎、靜態資源、Chrome 連接器、DLL 與 WebView2 Runtime 的定位、日誌與正常關閉。先做可檢查的資料夾型發行包，再評估單一 EXE。
- [x] 補上選配依賴與實際元件授權／對應原始碼、來源封裝 allowlist／排除規則、Windows 打包 CI，以及 README／架構／安裝／回復文件。使用 PyInstaller onedir＋每位使用者 Inno Setup；Node／FFmpeg 內附，WebView2 缺少時使用已校驗的 Microsoft bootstrapper。
- [ ] 在沒有預裝 Python／Node 的乾淨 Windows 10／11 驗收安裝、缺少 Runtime 的線上安裝／離線失敗處置、真人雙擊／捷徑／原生提示及安裝版 Chrome 授權，並在該環境核對更新保留資料、回退與解除安裝。目前無 Windows Sandbox，使用者確認沒有其他乾淨測試機；不把 PATH 隔離或目前主機當作乾淨 OS 通過。自動更新、簽章、托盤與開機啟動不在本階段。

2026-10-26 已在 Windows 10 build 19045 產生真正的 GUI／runtime EXE、資料夾 ZIP 與安裝程式；新程序以限定 PATH 驗證內附工具、實際 WebView2／bridge／HTTP 偏好、獨立 worker／Pixiv 管線、跨安裝位置共用資料 scope、DPAPI 合成登入／歷史恢復、正常停止，以及真實安裝／更新／回退／拒絕使用中程式／解除安裝保留資料。匯入先驗證及備份，SQLite 連線正常關閉後原子替換；中斷與明確回復均保留新舊資料。詳細範圍、指令及限制見 [Windows 發行指南](docs/WINDOWS_DISTRIBUTION.md)。本輪不實作 D06，也不建立公開 Release。

### D06：Electron 遷移保留與成本控制

- [ ] 在 Browser／Pywebview 兩個 Adapter 通過後記錄 Electron 對應表：同一份 `static/` 與標準 HTTP API、同一個 Python backend／資料格式／授權流程，替換的部分是主程序、視窗生命週期、桌面 Adapter、後端啟動入口與打包。先保留設計與契約，待使用者決定再實作 Electron。
- [ ] 未來 Electron 以 preload／`contextBridge` 暴露相同 `DesktopInterface`；renderer 不直接拿 Node、檔案系統或任意 IPC。逐方法驗證參數、來源／frame 與能力，維持 `contextIsolation`／sandbox，透過同一個 Supervisor 控制協定管理 Python 子程序。重跑 Adapter 契約及真實外殼驗收；不承諾只改啟動檔即可零成本遷移。

實作順序為 **D01 → D02 → D03 → D04 → D05**；D06 是將來替換外殼的保留規劃。先交付可在現有 Python 環境執行的單視窗版本，再處理免裝 Python 的安裝包。每一步以獨立 diff／明確通過條件收斂，不為桌面化順帶重寫後端、導入前端框架或實作選配索引；所需時間與 token 在第一個 WebView2 原型驗證後再細估，避免把打包／真人授權排錯算成幾行外殼程式的成本。

技術依據：[pywebview 架構](https://pywebview.flowrl.com/guide/architecture)支援直接載入既有 HTTP 服務；[pywebview 官方文件](https://pywebview.flowrl.com/api/)說明 GUI 主執行緒、bridge 與 profile 設定；[Electron context isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)及[安全建議](https://www.electronjs.org/docs/latest/tutorial/security)作為未來 preload／IPC 設計依據。上述後續階段為依本專案現況提出的工程規劃，官方文件不代表此專案已完成整合驗收。

## 安裝、真實使用與 GitHub 發布驗收

Windows 背景啟停的 7 項原生隔離驗收已於 2026-10-24 通過並移至 [CHANGELOG](CHANGELOG.md#unreleased)：自訂／重複／同時啟動、瀏覽器網址分派、不同專案隔離、下載中停止與待辦／Rate 恢復、日誌輪替及前景服務佔用拒絕。範圍與指令見 [背景驗收](docs/DESKTOP_ACCEPTANCE.md)；瀏覽器視窗及人手操作保留如下。

- [ ] **一般桌面 Windows／互動驗收**：全新一般 Windows 的 Python／Node／Chrome 安裝、實際雙擊 start.bat／stop.bat、預設瀏覽器視窗／作業系統關聯、鍵盤／終端批次提示及授權 X 登入仍待驗收。新來源／新 venv 安裝、離線重啟、自動修復、更新／基準恢復，以及獨立控制台真正 Ctrl+C 的閒置／下載中關閉、程序清理及待辦恢復已自動化並移至 [CHANGELOG](CHANGELOG.md#unreleased)，見 [安裝驗收](docs/INSTALLATION_ACCEPTANCE.md) 與 [控制台驗收](docs/CONSOLE_ACCEPTANCE.md)。這些隔離副本／程式產生的事件不等於出廠桌面或人手按鍵；沒有 Python 3.10 工作。

依使用者要求先處理 CI；路徑別名修正已在 GitHub 通過。後續介面測試補強連線容量與必要腳本失敗診斷，紀錄見 [TESTING](docs/TESTING.md#browser-ui-ci-fixture-capacity-and-diagnostics--2026-10-25)。最新 `d22c9a8` 的 GitHub Actions 三個工作（Windows、全新安裝、Docker）已全部通過，見 [CI 確認](docs/TESTING.md#hosted-ci-confirmation--2026-10-25)。Chrome 真實配對的獨立實測結果如下。

一般 Chrome 原生配對主流程已於 2026-10-25 完成實機驗收：取消後重配、真實 600 秒票證逾時後重配、離線失敗／上線重試、Pixiv 真實 claim／callback 自動回接、原生 DPAPI 保存及自訂 port 的後端重啟恢復、真正 Chrome 重啟後重配，以及使用者觀察 worker 無法使用後的真實重連。驗收紀錄區分人工操作、實際 HTTP 與內部狀態；專門的 OAuth 進行中 worker 休眠不在這個主流程結論內，仍列於下方授權剩餘環境。完成紀錄見 [CHANGELOG](CHANGELOG.md#unreleased) 及 [Chrome 驗收](docs/CHROME_PAIRING_ACCEPTANCE.md#follow-up-evidence--2026-10-25)。

- [ ] **線上平台抽樣**：實際 Best／指定畫質、登入失效、限流與恢復、帳號媒體掃描、缺檔補抓；先取得適合的測試素材。104＋10 合成測試不代表所有平台即時相容。
- [ ] **GitHub 設定與發布**：啟用並確認私人漏洞回報入口，核對 tag、版本、來源 ZIP、release notes 後發布 preview。repo 已公開、Windows／Python 3.12 CI 已通過，目前沒有 tag／Release。
- [ ] **後續依賴更新提案驗收**：首輪 pycryptodomex 3.24.1 修補驗收已完成。Actions #5 已收到並核對官方 SHA，須統一更新來源與 D05 打包流程的五處呼叫；其整合／CI 證據見 [PR 整合紀錄](docs/PR_INTEGRATION.md)與[依賴審查](docs/DEPENDENCY_ACCEPTANCE.md)。Python #3／#2 保留 Draft：新引擎／Playwright 候選仍有未釐清的原生 GUI 驗收失敗，main 保留 gallery-dl 1.32.16／Playwright 1.63.0／pyee 13.0.1。候選 Playwright 1.64.0 已允許 pyee 14，但尚未整合，不能跳過前置驗收直接強裝。後續提案仍逐次驗收、不自動合併，未宣稱完成 CVE 掃描。

依賴故障追蹤工具、CI／來源包檢查及本輪 HTTP 錯誤回應資源修正已完成，移至 [CHANGELOG](CHANGELOG.md#unreleased)。後續每次引擎／Chrome／Playwright 升級仍須重跑；已知 SSL 棄用、10053 的驗證範圍與故障處置維護在[追蹤文件](docs/DEPENDENCY_FAULTS.md)，不代表所有上游問題已消失。未來二進位散布仍須逐版核對第三方授權。

## Pixiv 作者作品驗收

Windows／一般 Chrome 授權主流程，以及 Hoshirapu（82728784）的 22 作品／24 檔案實際同步、原圖解碼、暫停／停止續傳、重複同步不重抓、單頁缺檔／修改時間補抓、正常 Windows 使用者環境重啟登入恢復與中英文作者標題已於 2026-10-24 驗收；完成紀錄移至 [CHANGELOG](CHANGELOG.md#unreleased)，詳細證據與範圍見 [Pixiv 驗收](docs/PIXIV_ACCEPTANCE.md)。

Pixiv 授權生命週期的自動化部分已於 2026-10-25 完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)：16 個 manager／實際 loopback API 案例與四個 connector 腳本案例，驗證 PKCE、取消／過期、來源與錯誤 port 拒絕、模擬 worker 重載、加密／記憶體保存與失效登入恢復，並修正失效憑證重啟再現與 :0 回呼判定。範圍見 [授權驗收](docs/PIXIV_AUTH_ACCEPTANCE.md)。

- [ ] **其他授權的剩餘真實環境**：Docker 真實 OAuth 自動回接、全新連接器安裝／權限提示、OAuth 進行中的 worker 休眠或 Chrome 重啟與授權分頁關閉、外部 code 過期／取消、Docker secret 登入恢復，以及儲存權限故障的真人處置。一般 Chrome 的正常 OAuth 回接、原生 DPAPI／後端恢復與重啟後新配對已完成主流程驗收；未對 OAuth 進行中休眠／跨重啟延續作出完成聲明。模擬 Chrome API、固定時鐘及自建 AES 金鑰不代表這些剩餘環境已完成。
Pixiv 新增內容與故障恢復的自動化部分已於 2026-10-25 完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)。[16 項合成故障驗收](docs/PIXIV_RECOVERY_ACCEPTANCE.md)涵蓋新增／不可存取作品、掃描不完整、頁碼缺口與重複、限流、停止／傳輸中斷、已完成頁面保留、只補缺頁及登入敏感資料遮蔽，並修正完整性與錯誤恢復問題。

- [ ] **內容與故障的剩餘真實驗收**：作者在平台新增作品後同步、Pixiv 實際不可存取／刪除／私密回應、真實平台限流與傳輸故障恢復，以及 Ugoira 原始影格完整數量／解碼。合成 API／傳輸案例與此次 22 作品／24 檔案不代表以上真人平台情境已完成。
Windows／Linux 的合成作者目錄驗收已於 2026-10-25 通過並移至 [CHANGELOG](CHANGELOG.md#unreleased)：中文／特殊／長名稱、同名不同 ID、模擬作者更名、數字 ID／舊作者名完整與部分紀錄重用、換根目錄、整個資料夾搬移，以及等待期間缺頁補抓。原生檔案與實際 SQLite 驗證詳見 [目錄驗收](docs/PIXIV_PATH_ACCEPTANCE.md)。

- [ ] **作者目錄剩餘真實／跨環境驗收**：作者在 Pixiv 實際更名、未知舊版資料庫結構、Windows 路徑字串／絕對根目錄 scope 搬遷到 Linux，以及 Linux／Docker 真實登入、作者標題與原始媒體恢復。合成目錄與保存紀錄測試不代表以上情境已完成。

## 後續功能

### 大型媒體清單索引（選配）

- [ ] 實作獨立的工作檔案索引及游標分頁，配套增量 IPC、snapshot generation 發布、恢復／回退、舊資料遷移及精確檔案操作。N07 的[評估與取捨](docs/DATABASE_MAINTENANCE.md#indexed-file-detail-assessment)已完成；此實作是後續功能，屬於未來選配。
- [ ] 工作清單生命週期與有效去重紀錄分開；原位置檔案不存在就重新取得。現有 HTTP 分頁仍從記憶體清單取得，64 MiB 限制維持，不以直接提高上限取代索引設計。

### Docker 化部署

第 1～4 項的來源實作、第 5 項的隔離 runtime 驗收及第 2／3 項的本機 Compose 驗收已完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)。2026-10-21 已實際通過 9 項 FFmpeg／Node／來源排除及 14 項服務／儲存驗收，含 UID 權限、資料保留、故障健康狀態、備份校驗、真正還原中斷、跨專案搬遷及保留映像回復。範圍見 [Docker 文件](docs/DOCKER.md)、[服務驗收](docs/DOCKER_SERVICE_ACCEPTANCE.md)及[實測紀錄](docs/TESTING.md)。動態 Chrome 仍為選配，沒有發布預建映像；同機隔離驗收不代表以下跨主機／登入工作完成。

2026-10-22 已完成第 4 項可自動化的 [15 項登入／媒體容器驗收](docs/DOCKER_INTERACTION_ACCEPTANCE.md)：記憶體登入、獨立金鑰生成／權限／唯讀掛載、AES-GCM 保存與重啟、錯誤／遺失金鑰保留原資料、金鑰恢復與斷開連接；合成 connector 取消／重配及網頁分頁、原始 PNG／MP4 位元組、HEAD／Range、路徑拒絕、改名及併發讀取恢復。Windows 原生檔案／資料夾分派與失效選取新增隔離回歸，沒有啟動真實播放器。

同日完成 [8 項真實主機掛載驗收](docs/DOCKER_HOST_ACCEPTANCE.md)：私有 Windows ACL、原始 Compose bind／檔案型 secret、唯讀金鑰、加密登入重啟、主機備份校驗／排除金鑰，以及新專案還原登入。9＋14＋15＋8 項已在本機 Docker Desktop 實測通過；Linux CI 也納入該工具。記錄 Desktop 自動建立缺少來源目錄的實際差異與 OWNER RIGHTS 別名，補上操作前確認路徑的說明。完成紀錄移至 CHANGELOG；仍需下列真人與另一台主機驗收。

同日完成 [7 項主機 Chrome 實際 UI／播放驗收](docs/DOCKER_BROWSER_ACCEPTANCE.md)，完整工具共 53 項在本機通過；圖片解碼、鍵盤選檔、H.264 播放／跳轉、重整不改變工作、改名拒絕與後續讀取恢復均有實測。修正影片原生頁面 sandbox 產生 null Origin 而被拒絕的問題，保留腳本與不可信來源限制。真人登入與其他編碼仍保留如下。

2026-10-29 新增並通過 [8 項不同來源映像升級／回復驗收](docs/DOCKER_UPGRADE_ACCEPTANCE.md)，以兩份真正不同的來源建置映像，驗證升級／重啟、設定寫入、三份 SQLite 完成紀錄、合成加密登入及原映像備份回復到新 volumes。原始舊來源因還原未保留檔案修改時間而無法通過；已修正新備份的奈秒時間保存與還原，並明確區分回補此修正的舊來源。兩份來源仍為同一 preview 版本，不能視為跨發布版本遷移；實測與限制見 [TESTING](docs/TESTING.md#docker-source-upgrade-and-timestamp-recovery--2026-10-29)。

- [ ] **跨實體主機與實際版本升級（跨主機部分依使用者要求先跳過，2026-10-22）**：在另一台主機驗收備份搬遷及該主機的目錄分享／權限；有真實新版本時驗收資料遷移與匹配舊版本回復。既有驗收涵蓋同一引擎上的獨立 volumes／專案、真實主機備份／金鑰掛載及僅加標籤的不同映像；本輪另通過回補時間修正的同 preview 版本來源升級／回復，仍不能據此宣稱跨硬體或跨發布版本遷移已完成。
- [ ] **第 4 項真人操作驗收**：主機 Chrome 首次安裝、預設／自訂 port、取消／十分鐘過期／重配、真實登入失效；人手確認播放控制、聲音／其他編碼及 Windows 預設播放器／檔案總管。新增的 [7 項主機 Chrome 自動化驗收](docs/DOCKER_BROWSER_ACCEPTANCE.md)涵蓋真實 UI／鍵盤選檔、PNG 解碼與 H.264 播放／跳轉，完成紀錄見 CHANGELOG；自動化解碼與合成 API 配對不等於真人登入或全部編碼已驗收。
- [ ] 完成安裝、重啟恢復、媒體持久化與登入驗收，再將文件中的實驗操作程序升格為正式部署指引。Docker 不算目前已驗收的 P0／P1／P2。

### 去重與匯入選配

Pixiv 單篇作品穩定 ID 已於 2026-10-25 完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)：已確認的標準／英文語系／短網址／舊網址共用佇列與完成識別，保留畫質、媒體選取、未知 query 與原位置規則；相同舊網址的可信紀錄可安全轉存。14 項檔案／SQLite 合成驗收及一項 HTTP 佇列驗收，範圍與相容限制見 [來源識別](docs/SOURCE_IDENTITY.md)。

- [ ] 擴充**其他平台**可靠的穩定 ID，保留畫質／媒體差異；簽章更新是否能合併須逐平台確認。無法回推來源的舊 hash 不自動合併。

跨 URL／平台內容雜湊評估已於 2026-10-25 完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)。[評估與量測](docs/CONTENT_HASH_ASSESSMENT.md)建議保留原路徑規則，以選配 SHA-256 索引顯示相同內容候選；量測工具只讀取自建合成資料，未接入下載流程。

- [ ] 若採用內容雜湊比對索引，另行實作排程／取消、完整檔案核對、私有索引保存／恢復、候選 UI 及驗收。原位置缺檔、搬移、改名或換下載根目錄仍重新下載；不以跨來源雜湊自動略過或刪除檔案。
- [ ] 為已清除清單、沒有可信成功紀錄的舊檔提供可確認完整性的匯入流程，不因同名就直接認定完成。背景見 [DOWNLOAD_DEDUP](docs/DOWNLOAD_DEDUP.md)。

## 名稱與發布資料建議

建議保留 **Smart Social Downloader**，repo 為 **`smart-social-downloader`**。目前沒有改名。備選 Local Media Queue（`local-media-queue`）較偏通用網頁媒體；MediaQueue（`mediaqueue`）較短但用途不夠直觀。這些名稱尚未查核衝突、帳號可用性或商標。

推薦 GitHub description：

> Local-first video and image downloader with a web UI, queued downloads, X account media sync, and HLS/DASH support. Powered by yt-dlp and gallery-dl.

中文：在本機執行的多平台影片與圖片下載工具，提供網頁介面、下載佇列、X 帳號媒體同步與 HLS／DASH 支援。

建議 topics：`python`、`yt-dlp`、`gallery-dl`、`video-downloader`、`image-downloader`、`download-manager`、`hls`、`local-first`。

若日後改名，須同步 README、頁面標題、語系、Chrome 顯示名稱與發布檔；不要順便更動 extension 公開金鑰／ID、runtime 路徑或配對協定。
