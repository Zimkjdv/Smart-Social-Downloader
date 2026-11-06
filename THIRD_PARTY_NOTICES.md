# 授權與第三方元件

## 本專案程式碼

作者已選擇 MIT：本專案自行撰寫的程式碼與文件依根目錄 [LICENSE](LICENSE) 授權，允許商用、修改及散布，須保留版權與授權聲明。[MIT 說明](https://choosealicense.com/licenses/mit/)

這裡的授權是「軟體使用與散布規則」，與 X 登入、Cookie 或帳號授權無關。授權程式碼也不會授予下載媒體本身的版權。

## 第三方元件

以下元件由安裝程序另外安裝，保留各自的授權；不能因本專案有 MIT LICENSE 就把它們重新授權成 MIT。

| 元件 | 檢查版本 | 授權及來源 |
| --- | --- | --- |
| yt-dlp | 2026.8.19 | Unlicense；[上游 LICENSE](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE)。其額外依賴也各有授權。 |
| gallery-dl | 1.32.16 | GPL-2.0-only；[上游 LICENSE](https://github.com/mikf/gallery-dl/blob/master/LICENSE)。 |
| imageio-ffmpeg 的 Python wrapper | 0.6.0 | BSD-2-Clause；[上游 LICENSE](https://github.com/imageio/imageio-ffmpeg/blob/main/LICENSE)。 |
| pycryptodomex | 3.24.1 | BSD／Public Domain，依元件檔案保留適用聲明；[對應版本 LICENSE](https://github.com/Legrandin/pycryptodome/blob/v3.24.1/LICENSE.rst)。由安裝程序另行安裝。 |
| FFmpeg 執行檔 | 依使用者環境而定 | 依編譯選項可能適用 LGPL 或 GPL；Python wrapper 的 BSD 授權不等於 FFmpeg 的授權。[FFmpeg 官方授權說明](https://ffmpeg.org/legal.html) |
| Playwright（選配） | 1.63.0 | Apache-2.0；[上游 LICENSE](https://github.com/microsoft/playwright-python/blob/main/LICENSE)。包含驅動依賴，並未納入本專案原始碼包。 |
| greenlet（選配） | 3.5.6 | MIT AND PSF-2.0；以安裝套件 metadata／licenses 為準。 |
| pyee（選配） | 13.0.1 | MIT；以安裝套件 metadata／licenses 為準。 |
| typing-extensions（選配） | 4.16.0 | PSF-2.0；以安裝套件 metadata／licenses 為準。 |
| pywebview（桌面選配） | 6.2.1 | BSD-3-Clause；[上游來源／授權](https://github.com/r0x0r/pywebview/tree/6.2.1)，以安裝套件 LICENSE 為準。 |
| pythonnet（桌面選配） | 3.2.1 | MIT；以安裝套件 metadata／licenses 為準。 |
| clr-loader（桌面選配） | 0.3.1 | MIT；以安裝套件 licenses/LICENSE 為準。 |
| cffi（桌面選配） | 2.1.1 | MIT-0；以安裝套件 metadata／licenses 為準。 |
| pycparser（桌面選配） | 3.12 | BSD-3-Clause；以安裝套件 metadata／licenses 為準。 |
| proxy-tools（桌面選配） | 0.1.0 | metadata 標 MIT，但程式碼標 BSD；保留[上游 BSD LICENSE](https://github.com/jtushman/proxy_tools/blob/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/LICENSE.txt)的原始文字與版權。 |
| bottle（pywebview 依賴） | 0.13.4 | MIT；以安裝套件 metadata 為準。本專案桌面版仍載入既有 HTTP 後端，不另建 Bottle 業務服務。 |

本專案直接呼叫 gallery-dl 的 Python API。MIT 與 GPL 相容，但散布包含 GPL 元件的組合程式時仍須遵守 GPL 的條件；不能宣稱整個組合產品只有 MIT 條件。[GNU 授權相容性說明](https://www.gnu.org/licenses/license-list.html#Expat)、[GNU 對結合模組的說明](https://www.gnu.org/licenses/gpl-faq.html#IfInterpreterIsGPL)

如果日後要達成「所有組合功能都只受 MIT 條件限制」，需要重新評估 GPL 依賴及其整合方式。現在的 MIT LICENSE 適用於作者自己的程式碼，不抹除第三方義務。

## D05 Windows 二進位建置

D05 另產生目錄型 EXE 與 Inno 安裝程式，與下方來源 ZIP 區分。安裝包保留各 runtime 套件的授權／聲明、CPython LICENSE、Node 22.23.4 的完整 LICENSE、WebView2 SDK 1.0.3856.49 的 LICENSE／NOTICE，並附應用程式原始碼 ZIP、gallery-dl／mutagen 對應版本來源檔。GPL 元件不因與本專案一起打包就改成 MIT；不得拿掉這些檔案後宣稱整份組合只有 MIT 條件。

FFmpeg 8.1.3 由固定來源及 Debian 快照工具鏈交叉建置，禁用 GPL／version3／nonfree 與外部自動偵測，只另啟用 zlib 1.3.2 與 Windows 系統 TLS。保留 LGPL-2.1、MinGW／GCC runtime／zlib 聲明、FFmpeg／zlib 完整來源、實際 configure 記錄與建置 recipe；排除 imageio wheel 內另一份較廣泛的 GPL FFmpeg 執行檔。實際 `ffmpeg -L` 必須報 Lesser GPL 才允許封裝。這不是宣稱所有 FFmpeg 編譯組態都適用同一授權。

PyInstaller 6.22.3 的 COPYING（含 bootloader 例外）與 proxy-tools 在 wheel 缺漏的上游 BSD 授權文字，均另附於 licenses。PyInstaller 採 GPL 加 bootloader 散布例外；[官方例外](https://pyinstaller.org/en/v6.22.3/license.html)不取代應用程式依賴的授權。Inno Setup 6.7.3 為建置工具，保留[官方使用條款](https://jrsoftware.org/isinfo.php)；不把 compiler 當成應用程式 runtime。Microsoft WebView2 bootstrapper 由官方固定 CDN 下載，校驗 SHA-256 及 Microsoft 簽章，依 [Microsoft 部署說明](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)在缺少 Runtime 時下載安裝；SDK／Runtime 適用 Microsoft 條款，Chrome 仍由使用者另行安裝。

每次升級依賴或實際散布形式都必須重新核對建置輸入、附帶聲明及對應來源；目前仍為 unsigned preview，沒有公開正式發行。指令與範圍見 [Windows 發行](docs/WINDOWS_DISTRIBUTION.md)。

## 發布形式（來源 ZIP）

來源 ZIP 提供原始碼與安裝腳本，不把 `.venv`、引擎套件、FFmpeg 執行檔或私人資料打包到 ZIP。完整依賴版本見 `requirements.lock.txt`，元件授權也可在安裝後的套件 metadata／licenses 目錄查閱。

動態捕捉的選配版本見 `requirements-browser.txt`。Google Chrome 由使用者另行安裝，適用自己的條款；不下載或散布 Chrome／Chromium 執行檔，也不把 Playwright 的 Node 驅動放進原始碼包。

桌面選配版本見 `requirements-desktop.txt`，這些套件與其 DLL 不包含在本專案來源 ZIP。Microsoft Edge WebView2 Runtime 由使用者另行安裝並適用 Microsoft 條款；來源版不重新散布 Runtime。安裝與範圍見 [桌面指南](docs/DESKTOP_GUI.md)。

D05 Windows 預覽包的內容與聲明見上節。後續每個二進位版本仍依實際元件保留完整授權文字、版權聲明及對應原始碼／建置資訊。

## Docker 來源設定

目前新增的是 Dockerfile／Compose 與[建置文件](docs/DOCKER.md)，未發布預建映像。來源 ZIP 仍不含第三方執行檔；使用者依設定建置的映像則會包含 Python、Node、Debian／FFmpeg 及 Python 依賴，保留各元件授權。Dockerfile 保留安裝套件的 metadata／licenses、Debian 版權檔及 Node LICENSE，並記錄實際套件版本。

若日後散布映像，須依其實際內容完成授權、聲明及適用的對應原始碼義務審查；來源基礎設定完成不等於已完成映像散布審查。Python 與 Node 來源及授權可分別見 [Python](https://github.com/python/cpython/blob/3.12/LICENSE)、[Node](https://github.com/nodejs/node/blob/v22.23.3/LICENSE)，Debian 套件聲明位於映像的 `/usr/share/doc/`。

## Pixiv 功能的設計參考

2026-10-23 的 Pixiv 作者同步沿用 gallery-dl 既有 Pixiv／OAuth 實作及本專案的佇列／保存服務。設計參考 [PixivUtil2](https://github.com/Nandaka/PixivUtil2) 的作者、作品、漫畫頁碼分層與缺檔檢查，參考專案採 [BSD-2-Clause](https://github.com/Nandaka/PixivUtil2/blob/master/LICENSE)。本次沒有新增 PixivUtil2 套件依賴，gallery-dl 的原有 GPL 義務維持。功能與驗收範圍見 [Pixiv 文件](docs/PIXIV.md)。
