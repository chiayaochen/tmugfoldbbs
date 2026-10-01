# 手機版與典藏驗收

完整網站：2,534 篇不同文章，2,547 個分類文章頁，167 個分類，34 個空分類。2,534 份 EML、TXT 各自 byte/hash 驗證通過；170 份原始分類與典藏 sidecars 同樣原樣保存。50,418 個站內連結全部有效，搜尋包含所有 2,534 篇，沒有轉換失敗。

七項 Python 保留／安全測試及 208 項瀏覽器檢查通過。Chromium 151／WebKit 26.5，測試寬度 320、375、390、430、768、1280px；JS runtime errors 為零。Browser plugin 在此環境不存在，使用已安裝的 Playwright 引擎直接測試。

|驗收項目|證據與限制|
|---|---|
|一般手機正文|各尺寸整頁沒有額外橫向捲動；18px 預設，最小 16px|
|固定欄位|與實際 ASCII DOM 寬度比對，中文字恰為兩欄；不是拿同一個 Canvas 假設自證|
|ANSI|跨行、reset、亮色、底線、反白、閃爍、Big5 byte 間插碼測試；半色字與彩色表格截圖|
|框線／區塊|glyph 的實際 transformed 寬度填滿兩欄，字型 fallback 不使框線留下水平縫隙|
|導覽|上一／下一篇及返回分類可用；底部高度 ≥44px，末段未被遮蓋|
|觸控|圖形區域的水平拖動不觸發換文；列表整列可以點擊|
|設定|字體、閱讀模式重新載入後保留；首頁繼續閱讀可回到最近文章|
|搜尋|繁體中文「基服」可找到結果並直達文章；首頁沒有請求全文 JSON|
|PWA|manifest/icons/scope 正確；關閉真實 HTTP origin 後，兩引擎可讀最近文章與離線清單|
|錯誤隔離|單篇壞 EML 保留來源與 fallback，下一篇仍產生；錯誤 exit code 不誤報完成|

Playwright 的 WebKit `setOffline()` 在這個 macOS runtime 會於 service worker 執行前回報內部錯誤；離線驗收改用專用 HTTP server 真實關閉連線，實際觸發 fetch 失敗與 cache fallback，沒有跳過 WebKit 離線測試。

這些是引擎、尺寸及觸控模擬，沒有實體 iPhone／Android 裝置可操作，故不宣稱已完成手機硬體或主畫面安裝驗收。README 列出實機清單。

## 效能

核心 CSS 7,290 bytes；app JS 8,883 bytes；搜尋 worker 2,730 bytes。首頁 initial transfer 約 82.7KB，沒有框架或全站正文。4G 模擬 1.6Mbps／150ms RTT／4x CPU throttling：首頁 DOM 約 0.59 秒、一般文章約 0.36 秒、中文搜尋約 1.83 秒。5G 模擬約 0.12／0.08／0.30 秒。完整數值與環境在 performance.json；本機未壓縮 HTTP，不是手機實機的網路實測。

少數大型彩色版宣保留大量圖形、固定欄位與逐字顯示，最大 HTML 約 3.93MB，整站約 169MB；一般文章測試約 36KB。可在支援的主機啟用 gzip/Brotli 改善傳輸；若未來擴充為十萬篇，可進一步按結果文件分片與 lazy raw view，不應改用首頁載入全部正文。這批資料的搜尋已按查詢只載入必要索引／結果分片。

## 介面參考圖比對

使用 imagegen 的雙手機介面概念作為結構參考，保留五個核心關係：緊湊頁首、搜尋與分類優先、炭灰／灰字／玉綠點綴、正文為主、底部三個閱讀導航。實際手機截圖已用 view_image 檢查；桌面延伸成雙欄分類列表，文章保留閱讀寬度。

成品與概念的差異：所有分類／文章／數量換成真實來源，沒有採用示意文章文字；保留完整 BBS header 而非用概念中的段落取代；工具列在較窄手機分成兩行；長分類階層移到完整 metadata，頁首只顯示目前分類；原始模式與圖形顯示額外的可捲動欄位。這些差異服從資料忠實保存與手機可操作性。

截圖：browser-full/ 下有兩引擎各尺寸首頁／文章，以及 390px 彩色圖形。concept.png 僅是設計參考，不是網站生產素材。

## 隱私狀態

自動盤點包含 681 次 Email、498 次電話格式、841 次 IP、98 次疑似地址，以及作者識別碼與 EML routing headers。這些是 regex 命中次數，不代表有同樣數量的不同個人；也可能漏掉其他資訊。

依使用者指示製作完整 gh-pages 典藏。既有 repository 與 Pages 是公開的。已產生逐 message ID 盤點與公開前檢查流程，沒有自動匿名化或改寫原文，也**沒有宣稱完成逐篇人工同意／隱私審核**。需要私人版本時，README 提供全站 Access 或 VPN／Tailscale 部署，必須連原始檔、索引與來源 repository 存取權一併處理。

## 正式網站驗證

GitHub Pages 的 index.html 以 HTTP 200 回應，內容與本機產物 byte-identical。線上 390px Chromium 與 WebKit 都確認繁體中文搜尋、直達文章、PWA service worker 與實際 CJK/ASCII 欄寬比例（約 1.99982），沒有 JS runtime errors。詳見 deployment-verification.json 與 *-390-live.png。
