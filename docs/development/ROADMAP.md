# Roadmap

更新於 2026-11-21，以本機 `main` 的 `727a9d4` 為審查基準。下列核取方塊只列未完成工作。已交付功能、已發布版本及各環境曾通過的範圍可查 [CHANGELOG](../history/CHANGELOG.md)。

<a id="本輪整體審查"></a>

## 下一輪改善

優先處理會誤導使用者或妨礙重現的問題，再改善操作流程及維護成本。Browser 與 pywebview 共用 Web UI 和 HTTP API，以下介面修正可沿用同一套前端。後端已有獨立的排程、保存與下載引擎，架構調整可限於佇列新增流程。[架構與模組責任](../reference/ARCHITECTURE.md)

### 優先處理


### 操作流程與文件

- [ ] **讓使用者在送出前看到 30 筆上限。** 一般網址、X 帳號與 Pixiv 作者共用計數器，目前只顯示筆數，超過限制要送出才收到後端錯誤。計數旁顯示上限及超額筆數，讓使用者能原地修改。驗收三種輸入模式的 30／31 筆邊界、貼上後刪減、鍵盤送出，以及伺服器對超額請求的獨立驗證。[表單](../../static/app.js) · [API 契約](../reference/API_CONTRACT.md)
- [ ] **釐清 Windows 下載頁的交付狀態。** README 連到已發布的 Preview 來源 ZIP，Windows 發行指南仍寫著尚未建立 GitHub Release/tag，接著直接指示執行安裝程式。將來源 ZIP 的下載／啟動步驟、本機可建置的 EXE／安裝程式、乾淨機器待驗條件分別標明。驗收時從中英文 README 各走一次，確認讀者能找到實際可下載的檔案，也能判斷哪個流程需要自行建置。[英文入口](../../README.md) · [中文入口](../README_CN.md) · [Windows 發行指南](../deployment/WINDOWS_DISTRIBUTION.md)

### 程式與架構

- [ ] **抽出佇列新增操作（暫緩）。** 若新增另一個入列入口，或下一次需要跨模式修改入列規則，再把去重、容量檢查、建立或沿用工作及保存交給單一佇列操作。現有 Browser／pywebview 走同一條 HTTP 路由。路由負責請求與回應，共用操作負責同一個鎖內的決策與提交，鎖外等待保存確認。[現行路由](../../ssdl/http_api.py) · [佇列與去重規則](../reference/DOWNLOAD_DEDUP.md)

## 既有環境與發布驗收

| 待驗項目 | 前置條件與完成標準 |
| --- | --- |
| D04 桌面顯示與權限 | 在每種縮放比例重新啟動、跨不同 DPI 的螢幕移動視窗，驗證真實剪貼簿拒絕及乾淨機器缺少 WebView2 的處置。分別記錄 OS 與 renderer 的縮放。[GUI 驗收](../testing/DESKTOP_GUI_ACCEPTANCE.md) |
| D05 安裝版 | 取得未預裝 Python／Node 的乾淨 Windows 10／11。驗收安裝、缺 Runtime 的線上安裝／離線處置、雙擊／捷徑／原生提示、安裝版 Chrome 授權、更新保留資料、回退及解除安裝。[Windows 發行指南](../deployment/WINDOWS_DISTRIBUTION.md) |
| Windows 來源版 | 在全新一般桌面完成 Python 3.12／Node／Chrome 安裝，人工雙擊 start.bat／stop.bat，核對預設瀏覽器關聯、鍵盤與終端提示、實際 X 授權。[安裝驗收](../testing/INSTALLATION_ACCEPTANCE.md) · [控制台驗收](../testing/CONSOLE_ACCEPTANCE.md) |
| 線上下載 | 取得適用素材，逐平台抽驗 Best／指定畫質、登入失效、限流恢復、帳號媒體掃描及缺檔補抓。記錄素材類型、引擎版本與可重現結果。[畫質契約](../guides/VIDEO_QUALITY.md) |
| Pixiv 授權 | 驗收全新連接器安裝／權限提示、OAuth 進行中的 worker 休眠／Chrome 重啟／分頁關閉、外部 code 過期或取消、Docker 自動回接、金鑰登入恢復及儲存權限故障的人工處置。[授權驗收](../testing/PIXIV_AUTH_ACCEPTANCE.md) · [Chrome 配對](../testing/CHROME_PAIRING_ACCEPTANCE.md) |
| Pixiv 內容與資料搬遷 | 抽驗真實作者新增、刪除／私密／不可存取作品、限流與傳輸中斷、Ugoira 原始影格數與解碼。取得作者更名及舊資料庫樣本後，再驗 Windows 絕對路徑／根目錄移至 Linux，以及 Linux／Docker 的登入、作者標題與媒體恢復。[故障恢復](../testing/PIXIV_RECOVERY_ACCEPTANCE.md) · [作者目錄](../testing/PIXIV_PATH_ACCEPTANCE.md) |
| <a id="docker-化部署"></a>Docker 真人操作 | 主機 Chrome 首次安裝、預設／自訂 port、取消／十分鐘過期後重配、登入失效；人工驗證播放控制、聲音、其他編碼、Windows 預設播放器與檔案總管。[互動驗收](../testing/DOCKER_INTERACTION_ACCEPTANCE.md) · [播放驗收](../testing/DOCKER_BROWSER_ACCEPTANCE.md) |
| Docker 跨主機與版本 | 跨實體主機依先前決定暫緩；恢復時核對另一台主機的目錄分享、權限及備份搬遷。有不同發布版本後，驗證資料遷移與匹配舊版回復。完成安裝、重啟、媒體與登入驗收後，再將實驗部署指引升格。[跨主機驗收](../testing/DOCKER_HOST_ACCEPTANCE.md) · [升級驗收](../testing/DOCKER_UPGRADE_ACCEPTANCE.md) |
| 後續依賴與二進位散布 | 每次新提案核對固定版本與相容範圍，執行受影響的引擎／Chrome／Playwright 故障回歸、原生 GUI 驗收與 CI。散布二進位檔前逐版核對第三方授權。[依賴審查](../history/DEPENDENCY_ACCEPTANCE.md) · [故障追蹤](DEPENDENCY_FAULTS.md) · [第三方元件](../reference/THIRD_PARTY_NOTICES.md) |

## 有條件啟動的功能與設計

- [ ] <a id="大型媒體清單索引暫緩"></a>**大型媒體清單索引（暫緩）。** 當代表性工作反覆觸及 64 MiB 保存上限、必要歷史長期接近警示且無法清理，或可重現的整份保存延遲已影響操作，再用該案例評估索引成本與效益。[既有量測與重啟條件](../reference/DATABASE_MAINTENANCE.md#indexed-file-detail-assessment)
- [ ] **其他平台的穩定來源 ID。** 逐平台驗證網址變體、簽章更新、畫質與媒體選取，再擴充可合併的識別。無法回推來源的舊紀錄維持獨立。[來源識別](../reference/DOWNLOAD_DEDUP.md)
- [ ] **跨來源相同內容候選。** 若採用選配 SHA-256 索引，再實作可取消排程、完整檔核對、私有索引保存與恢復、候選清單。驗收原位置缺檔、改名、搬移或換根目錄時仍會補抓，且比對本身不會刪檔。[雜湊評估](../research/CONTENT_HASH_ASSESSMENT.md)
- [ ] **匯入缺少可信紀錄的舊檔。** 為已清除工作清單的使用者提供可核對完整性與來源的匯入流程，以同名不同內容與不完整檔案驗收。[去重規則](../reference/DOWNLOAD_DEDUP.md)
- [ ] **D06 Electron。** Browser／pywebview Adapter 通過後，先記錄桌面方法、視窗生命週期、Supervisor 和打包對應。待使用者決定採用再實作。沿用 Web UI、HTTP、Python 後端、資料與授權流程；逐方法驗證 preload／contextBridge 的來源、frame、參數及權限，維持隔離與 sandbox，重跑契約與真實外殼驗收。[桌面契約](../reference/API_CONTRACT.md) · [Supervisor](../reference/DESKTOP_CONTROL.md)
- [ ] **發布名稱與資料（如需調整）。** 首選 Smart Social Downloader，儲存庫建議名為 `smart-social-downloader`。備選 Local Media Queue、MediaQueue 的名稱、帳號及商標仍待查核。若改名，核對 README、頁面標題、語系、Chrome 顯示名稱與發布檔，保留 extension ID、資料路徑與配對協定。建議介紹涵蓋本機影音／圖片下載、佇列、X 帳號同步及 HLS／DASH；topics 可用 `python`、`yt-dlp`、`gallery-dl`、`video-downloader`、`image-downloader`、`download-manager`、`hls`、`local-first`。
