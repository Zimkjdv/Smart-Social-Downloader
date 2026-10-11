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
| FFmpeg 執行檔 | 依使用者環境而定 | 依編譯選項可能適用 LGPL 或 GPL；Python wrapper 的 BSD 授權不等於 FFmpeg 的授權。[FFmpeg 官方授權說明](https://ffmpeg.org/legal.html) |
| Playwright（選配） | 1.63.0 | Apache-2.0；[上游 LICENSE](https://github.com/microsoft/playwright-python/blob/main/LICENSE)。包含驅動依賴，並未納入本專案原始碼包。 |
| greenlet（選配） | 3.5.6 | MIT AND PSF-2.0；以安裝套件 metadata／licenses 為準。 |
| pyee（選配） | 13.0.1 | MIT；以安裝套件 metadata／licenses 為準。 |
| typing-extensions（選配） | 4.16.0 | PSF-2.0；以安裝套件 metadata／licenses 為準。 |

本專案直接呼叫 gallery-dl 的 Python API。MIT 與 GPL 相容，但散布包含 GPL 元件的組合程式時仍須遵守 GPL 的條件；不能宣稱整個組合產品只有 MIT 條件。[GNU 授權相容性說明](https://www.gnu.org/licenses/license-list.html#Expat)、[GNU 對結合模組的說明](https://www.gnu.org/licenses/gpl-faq.html#IfInterpreterIsGPL)

如果日後要達成「所有組合功能都只受 MIT 條件限制」，需要重新評估 GPL 依賴及其整合方式。現在的 MIT LICENSE 適用於作者自己的程式碼，不抹除第三方義務。

## 發布形式

目前提供原始碼與安裝腳本，不把 `.venv`、引擎套件、FFmpeg 執行檔或私人資料打包到 ZIP。完整依賴版本見 `requirements.lock.txt`，元件授權也可在安裝後的套件 metadata／licenses 目錄查閱。

動態捕捉的選配版本見 `requirements-browser.txt`。Google Chrome 由使用者另行安裝，適用自己的條款；不下載或散布 Chrome／Chromium 執行檔，也不把 Playwright 的 Node 驅動放進原始碼包。

若將來提供含第三方引擎的 EXE、可攜版或離線安裝包，需要按實際打包的版本整理完整授權文字、版權聲明及適用的對應原始碼／建置資訊。不能只附本頁連結就視為完成二進位散布要求。
