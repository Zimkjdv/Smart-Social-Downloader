# 安裝、隱私與原始碼發布

## 「不可信來源會被拒絕」是什麼？

這裡檢查的是誰能讀取或操作**本機下載工具的 API**。

正常從 `http://127.0.0.1:8765` 使用網頁介面會被允許。本機命令列工具沒有瀏覽器 Origin 時，只要 Host 合法，也可以讀取狀態。

如果以 `SSDL_PORT` 設定其他連接埠，合法來源會使用該服務實際連接埠；Chrome 連接器也必須由使用者在擴充功能視窗選定相同數字。這不會放寬成任意遠端網址，詳細步驟見 [操作與排錯](TROUBLESHOOTING.md)。

其他網站如果嘗試讀取本機下載清單、檔案路徑，或操作本機工具，會因不符 Host／Origin／跨站請求政策而收到 HTTP 403。拒絕回應只有錯誤文字，不包含工作資料、路徑或登入資訊。Chrome 登入連接器另有只允許指定 extension ID 與配對端點的流程。

**這項檢查不限制輸入的媒體網站。** 仍可貼入 YouTube、X 或其他受支援的媒體網址。它也不代表建立了使用者帳號權限系統；能在同一台電腦執行程式的其他人仍有本機存取能力。

## Windows 安裝版與來源版

D05 新增 PyInstaller 資料夾 EXE／ZIP 與每位使用者 Inno 安裝程式；程式與使用者資料分開，含必要工具、授權文字與對應原始碼，提供備份／匯入／回復。建置、產物、安裝、移除及目前主機驗收見 [Windows 發行指南](WINDOWS_DISTRIBUTION.md)。沒有公開 Release／tag，也尚未宣稱乾淨 Windows 10／11 驗收通過。以下批次檔與 Python 說明適用來源版本。

## 乾淨環境安裝與啟動

目前以 Windows 為主要支援環境，Python 3.12 為安裝與 CI 基準，與本機環境一致；最低版本為 3.12。Chrome 自動登入及開啟檔案／資料夾採用 Windows 功能。

1. 從 GitHub 取得程式碼，解壓到自己的資料夾。
2. 第一次執行 `setup.bat`：建立 `.venv`，安裝 `requirements.lock.txt` 的基準版本，檢查套件及 FFmpeg。
3. 執行 `start.bat`，在瀏覽器開啟 `http://127.0.0.1:8765`。未完成安裝時，start 會先呼叫 setup。
4. 後續 `start.bat` 只做本機環境檢查及啟動，包含 `pip check`，不安裝或更新套件；下載外部媒體仍需要網路。
5. 需要更新引擎時，先停止服務再執行 `update.bat`。它依 `requirements.txt` 的相容範圍更新，完成後重新啟動。
6. 若更新後有相容性問題，`setup.bat` 可重新安裝發布時的基準版本。

`requirements.lock.txt` 固定 Python 3.12 基準的直接及間接依賴版本，不再保留舊版 websockets 分支。GitHub CI 僅使用 Python 3.12，尚未在 GitHub 執行的結果不能視為通過。版本鎖定不是完整的檔案雜湊驗證。

首次安裝優先以 Windows Python launcher 的 `py -3.12` 建立專案環境；未安裝 launcher 或未登記該版本時改用 PATH 的 `python`，安裝程式仍檢查最低版本 3.12。既有 `.venv` 沿用原環境。如果它的 Python 版本低於 3.12，請停止服務、重新建立該虛擬環境，再執行 setup。

前輪已在 Windows 的獨立原始碼副本與全新 Python 3.12.10 虛擬環境驗證基準安裝、環境檢查，以及停用套件下載後的 `start.bat` 啟動。未複製作者的歷史、Cookie 或下載檔。這不等同驗證全新 Windows 系統或 Chrome 登入流程；介面診斷及自訂連接埠流程仍待乾淨環境驗收。

YouTube 等部分網站需要 Node.js 22+ 或 Deno 2.3+；啟動與設定中的環境診斷會檢查執行檔及版本。腳本不會靜默安裝全域 JavaScript runtime。[yt-dlp 官方 EJS 說明](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

命令列與設定介面共用 `ssdl/environment.py` 的檢查，必要套件、FFmpeg 與相依性失敗時阻止啟動；選配功能警告不阻止其他下載。服務啟動時背景檢查一次，輪詢讀取快取，使用者可手動重新檢查。詳見 [環境診斷與操作一致性](TROUBLESHOOTING.md)。

診斷現有環境：

```powershell
.\.venv\Scripts\python.exe tools/manage.py check
```

## 「發布包」是什麼？

發布包是給別人下載的 ZIP，包含程式碼、README、授權文件及安裝腳本。使用者解壓後自行安裝與啟動，不需要複製作者的本機環境。

GitHub 本身就可以下載 repo 的原始碼；另外製作 ZIP 是方便 Releases 使用，並非建立 repo 的必要條件。

本專案的原始碼 ZIP 採檔案允許清單，**不遍歷** `data/`、`downloads/` 或 `.venv/`，因此不會把下載檔、帳號紀錄、Cookie 或私人環境直接包進去。

檢查並列出預計納入的檔案：

```powershell
.\.venv\Scripts\python.exe tools/package_source.py --check
```

建立原始碼 ZIP：

```powershell
.\.venv\Scripts\python.exe tools/package_source.py
```

預設輸出：`dist/smart-social-downloader-<application-version>-source.zip`。`dist/` 已排除 Git 追蹤。腳本另檢查來源檔中明確的私人 Windows 路徑、私人金鑰及 Netscape Cookie 匯出標記，只回報檔名，不回顯疑似敏感值。這是輔助檢查，發布前仍要檢視檔案清單與內容。

新增子套件與共用 fixture 時，來源打包會依明確的 `ssdl/`、測試及 `tests/helpers/` 程式碼邊界遞迴，其他目錄仍使用固定檔名／globs。連結及 Windows reparse 路徑會被拒絕，runtime 目錄不遍歷。發布前再執行 `python tools/check_source_archive.py`，在暫存目錄核對 ZIP 成員／CRC／來源位元組、解壓並執行完整 Python／Node 測試。它沿用目前已安裝的依賴，不等於新 Windows 或新 venv 安裝驗收，詳見 [SOURCE_TESTING](SOURCE_TESTING.md)。

## Git 提交前的隱私檢查

`.gitignore` 已排除 runtime 資料夾、Cookie 常見檔名、`.env`、金鑰、日誌及打包產物。**Git 忽略規則不會移除已追蹤或已提交的資料。**

建立 repo 後，在推送前執行 `git status --short`、`git diff --cached --stat` 及 `git diff --cached`，確認沒有登入資訊、個人路徑、帳號紀錄或下載媒體。任意命名的 Cookie 檔仍需自行辨識；不能把整個工作目錄當作提交清單。

Chrome manifest 的公開金鑰用於維持 extension ID，不是私人憑證，可納入原始碼。截圖請使用適合公開的範例，避免含有私人帳號、網址、下載紀錄或路徑。

軟體及第三方授權見 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## P1 保存與診斷資料

`data/` 同時包含 schema 2 的工作清單（可讀入 schema 0／1）、有效備份、保留的損壞輸入、SQLite 媒體 manifest、帳號保存紀錄及加密登入資料；這些均不納入原始碼包。備份與資料庫也可能包含私人路徑與歷史，不能因不是 Cookie 檔就公開。

「匯出診斷」為省略歷史網址／路徑、遮蔽已知秘密的分享報告，由使用者自行下載／分享。首次 Git 提交仍須人工檢視檔案清單。CI 使用 Python 3.12 及 Node.js 22 跑 Python／前端測試，不使用私人登入或真實平台下載；尚未執行的 GitHub 結果不視為通過。

停止／無進度期限、manifest、備份恢復及公開網路目標政策見 [RELIABILITY.md](RELIABILITY.md)。

## 應用程式版本與維護配套

目前原始碼版本為 `0.1.0-preview.2`，尚未在 GitHub 發布。`ssdl/version.py` 是唯一的應用程式版本來源；頂部、設定診斷、匯出診斷、啟動訊息及原始碼包名稱皆使用它。引擎及 Chrome 連接器版本分開維護，`update.bat` 不會更新應用程式原始碼。

原始碼包包含 `requirements-browser.txt` 與動態捕捉／瀏覽器驗收測試，仍不包含選配套件、Chrome 執行檔或臨時 profile。Python 3.12 CI 安裝選配並要求 Chrome 可用，讓瀏覽器驗收不能靜默略過。GitHub CI 已有通過紀錄；每次提交仍需確認該 commit 的結果，本機結果見 [TESTING.md](TESTING.md)。

更新紀錄見 [CHANGELOG](../CHANGELOG.md)，錯誤／功能回報及貢獻方式見 [CONTRIBUTING](../CONTRIBUTING.md)，私人安全回報方式見 [SECURITY](../SECURITY.md)。GitHub Issue 表單存於 `.github/ISSUE_TEMPLATE/`；建立 repo 後才會出現在 GitHub。私人漏洞回報入口也須在 repo 設定中啟用，加入文件不代表已完成此 GitHub 設定。

完整版本規則及發布檢查清單見 [MAINTENANCE.md](MAINTENANCE.md)。本輪首頁展示圖為虛構資料的介面示意，不包含作者的歷史、登入資料或私人路徑，也不代表真實瀏覽器驗收已通過。
