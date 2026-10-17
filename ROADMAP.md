# Roadmap

更新：2026-10-17。此檔是**未完成工作與最新審查發現的唯一總清單**；完成紀錄移至 [CHANGELOG](CHANGELOG.md)。目前基準為 Windows／Python 3.12，沒有 Python 3.10 驗收工作。下列核取方塊均尚未完成，不代表已修正或已發布。N01～N08 已完成並移到 [CHANGELOG](CHANGELOG.md#unreleased)，回歸結果見 [TESTING](docs/TESTING.md)。N07 的索引評估已記錄，實際索引／游標儲存列為後續選配，尚未實作。

## 本輪整體審查

重新檢查 API／本機來源政策、Chrome 登入、下載與串流、排程／子程序、保存／去重、前端／設定、檔案架構、安裝與發布。既有 P0／P1／P2 的主要功能與本輪 N01～N08 已實作，仍有下列環境驗收與選配工作；功能完成不等於沒有 bug。前輪六個已修正問題保留於 [歷史審查](docs/PROJECT_AUDIT.md)，不與本輪待辦項目混用。

審查與回歸使用暫存目錄、隔離 HTTP 服務及合成資料重現。本機套用狀態另記於 CHANGELOG；測試沒有讀取真實 Cookie 或下載外部平台媒體。這是程式審查與有限的故障重現，不是完整滲透測試或所有依賴的漏洞掃描。

N01～N08 已移至 [CHANGELOG](CHANGELOG.md#unreleased)。本輪列出的修正與維護改善已完成，仍需以下環境／發布驗收及選配功能；不代表沒有其他潛在缺陷。[N08 共用 fixture 與來源包驗收](docs/SOURCE_TESTING.md) 已實作，HTTP 讀取期限、併發限制與輸入契約見 [可靠性文件](docs/RELIABILITY.md)。

## 架構與檔案結構

目前根目錄入口＋`ssdl/`／`static/`／`chrome-extension/`／`tools/`／`docs/`／`tests/` 的分層保留。AppContext 與共用測試 fixture 已實作，runtime 位置保持相容；完整樹見 [ARCHITECTURE](docs/ARCHITECTURE.md)。

每次只改一個責任邊界，維持入口、API、資料路徑及 Chrome extension ID 相容；共用鎖與關閉順序已列於架構文件。

## 安裝、真實使用與 GitHub 發布驗收

- [ ] **一般桌面 Windows／互動驗收**：全新一般 Windows 的 Python／Node／Chrome 安裝、一般終端 Ctrl+C 關閉及授權 X 登入。新來源／新 venv 的安裝、離線啟動／重啟、自動修復、更新／基準恢復已自動化並移至 [CHANGELOG](CHANGELOG.md#unreleased)，操作及界線見 [安裝驗收](docs/INSTALLATION_ACCEPTANCE.md)。Hosted runner／既有 Windows 的隔離副本不等於出廠桌面系統；沒有 Python 3.10 工作。
- [ ] **一般 Chrome 真實配對**：重新載入 connector 1.1.0、自訂 port、取消／過期／失敗後重配及重啟恢復。先前預設 port 曾成功配對，不代表新版自訂 port 已驗收。正常 Windows 使用者環境的 DPAPI 是前提，不能以受限工具環境的失敗宣稱 DPAPI 普遍失效。
- [ ] **線上平台抽樣**：實際 Best／指定畫質、登入失效、限流與恢復、帳號媒體掃描、缺檔補抓；先取得適合的測試素材。104＋10 合成測試不代表所有平台即時相容。
- [ ] **GitHub 設定與發布**：啟用並確認私人漏洞回報入口，核對 tag、版本、來源 ZIP、release notes 後發布 preview。repo 已公開、Windows／Python 3.12 CI 已通過，目前沒有 tag／Release。
- [ ] **依賴更新提案驗收**：確認 Dependabot 首輪 Actions／Python 更新 PR 的發現範圍、版本／完整 SHA 變更及 Windows 回歸結果，再由維護者審查合併。固定 SHA、離線政策檢查與更新／回歸／恢復流程已完成，見 [CHANGELOG](CHANGELOG.md#unreleased) 與 [維護指南](docs/MAINTENANCE.md#dependency-updates-and-action-pins)；尚未宣稱更新提案已合併或已完成 CVE 掃描。
- [ ] **依賴故障追蹤**：追蹤 SSL 棄用／socket ResourceWarning 與其他 Windows 傳輸異常。未讀 POST body 拒絕回應的 10053 再現後，已加入嚴格 framing／大小／時間限制的回應後清理及回歸；細節見 [TESTING](docs/TESTING.md)，尚未宣稱涵蓋所有 Windows 10053。引擎／Chrome／Playwright 升級後重跑相關驗收，二進位散布另行核對第三方授權。

## 後續功能

### 大型媒體清單索引（選配）

- [ ] 實作獨立的工作檔案索引及游標分頁，配套增量 IPC、snapshot generation 發布、恢復／回退、舊資料遷移及精確檔案操作。N07 的[評估與取捨](docs/DATABASE_MAINTENANCE.md#indexed-file-detail-assessment)已完成；此實作是後續功能，屬於未來選配。
- [ ] 工作清單生命週期與有效去重紀錄分開；原位置檔案不存在就重新取得。現有 HTTP 分頁仍從記憶體清單取得，64 MiB 限制維持，不以直接提高上限取代索引設計。

### Docker 化部署

- [ ] Python 3.12 Dockerfile／Compose 與可重現部署文件；目前沒有可使用的 Docker 映像。
- [ ] 設定／歷史／快取與下載媒體分開持久化，制定權限、備份、升級及回復流程。
- [ ] 容器監聽與 port 對應、Host／Origin、健康檢查，預設僅本機可存取；沿用下載來源的公開位址檢查。
- [ ] 處理 Linux 容器沒有 Windows DPAPI 的登入保存方式、本機 Chrome 配對及主機檔案／資料夾操作。
- [ ] FFmpeg／JavaScript runtime；動態 Chrome 捕捉維持選配，build context／映像排除私人資料。
- [ ] 完成安裝、重啟恢復、媒體持久化與登入驗收，再提供部署指令。Docker 不算目前已完成的 P0／P1／P2。

### 去重與匯入選配

- [ ] 擴充可靠的平台穩定 ID，保留畫質／媒體差異；簽章更新是否能合併須逐平台確認。
- [ ] 評估跨 URL／平台的內容雜湊比較；目前網址指紋不是內容雜湊。
- [ ] 為已清除清單、沒有可信成功紀錄的舊檔提供可確認完整性的匯入流程，不因同名就直接認定完成。背景見 [DOWNLOAD_DEDUP](docs/DOWNLOAD_DEDUP.md)。

## 名稱與發布資料建議

建議保留 **Smart Social Downloader**，repo 為 **`smart-social-downloader`**。目前沒有改名。備選 Local Media Queue（`local-media-queue`）較偏通用網頁媒體；MediaQueue（`mediaqueue`）較短但用途不夠直觀。這些名稱尚未查核衝突、帳號可用性或商標。

推薦 GitHub description：

> Local-first video and image downloader with a web UI, queued downloads, X account media sync, and HLS/DASH support. Powered by yt-dlp and gallery-dl.

中文：在本機執行的多平台影片與圖片下載工具，提供網頁介面、下載佇列、X 帳號媒體同步與 HLS／DASH 支援。

建議 topics：`python`、`yt-dlp`、`gallery-dl`、`video-downloader`、`image-downloader`、`download-manager`、`hls`、`local-first`。

若日後改名，須同步 README、頁面標題、語系、Chrome 顯示名稱與發布檔；不要順便更動 extension 公開金鑰／ID、runtime 路徑或配對協定。
