# 杏林綠意 BBS 手機典藏

從不可變的 `archive/gmail-tmu-service` 來源產生完整靜態網站，發佈分支為 `gh-pages`，入口為根目錄 `index.html`。原始 Gmail 分類與交叉收錄全部保留，顯示原始看板名稱；網址採穩定 Gmail label ID 與 message ID，沒有中文檔名或後端依賴。

## 來源與重建

來源 commit：`01008ff3d636695b06f73c303637838d8f0d1fa6`。這批資料實際是 RFC822 `.eml`，不是獨立 TXT：先抽取完整 MIME 文字 bytes，再分析 Big5／CP950、Big5-HKSCS、ANSI、CRLF 與 FireBird 格式。EML 和抽出的原始 TXT 都逐一比對 SHA-256；TXT **保留來源編碼與換行**，不是重新編寫的 UTF-8 文本。

Python 3.10+，僅使用標準函式庫；不需要 pip、Node 或任何永久執行的伺服器。轉換工具在 `rebuild/tools/`，模板在 `rebuild/templates/`，CSS/JS 原始碼在 `rebuild/assets/`。開發工作目錄中的相對路徑則是 `tools/`、`templates/`、`assets/`。

```sh
# 在獨立目錄讀取來源分支，不切換或改寫原始備份。
git clone --branch archive/gmail-tmu-service --single-branch \
  https://github.com/chiayaochen/tmugfoldbbs.git ../bbs-source
git -C ../bbs-source checkout 01008ff3d636695b06f73c303637838d8f0d1fa6

# 由 gh-pages checkout 的 rebuild/ 執行。
python3 tools/analyze.py ../bbs-source/北醫基服
python3 tools/build.py ../bbs-source/北醫基服 --sample --output ../sample-site --reports ../sample-reports
python3 tools/build.py ../bbs-source/北醫基服 --output ../generated-site --reports ../build-reports
python3 -m http.server 8000 --directory ../generated-site
```

開啟 `http://localhost:8000/index.html`。也可直接開啟產生的 HTML 閱讀，全文搜尋與 PWA 需 HTTP/HTTPS；localhost 可測 service worker。發佈時將 generated-site **內容**置於 `gh-pages` 根目錄，保留 `rebuild/`、`README.md` 與報告；不要將 `site/` 本身再包一層。

`build.py` 也接受只有 `.txt` 的資料夾樹。未來新增 TXT 後可再次整批執行；看板使用完整路徑雜湊、文章使用來源相對檔名雜湊，移動或改名 TXT 會改變 URL，故請將來源路徑視為永久識別碼。Gmail 資料維持 message ID URL；主題與日期改變不影響網址。同一 message ID 位於多個分類，逐分類產生文章頁，原始下載只有一份；每份頁面 metadata 使用相同 message ID。新增 TXT 不會使既有 Gmail manifest 的數量檢核失效。

輸出目錄由 `.bbs-generated` 標记識別；工具拒絕覆蓋未標記的非空目錄，也拒絕把輸出放在來源裡面。每次重建先產生獨立暫存目錄，再替換上一版產物。請勿手動編輯產生的 HTML，修改工具或模板後重建。

## 資料忠實度與限制

* 2,534 篇不同文章，2,547 個分類文章頁，167 個分類；空分類有頁面。13 篇跨分類重複保留，原先父子去重結果不變。
* BBS 作者、暱稱、標題、信區、發信站、轉信、簽名分隔線、引用行、來源 IP 均額外辨識，**不移除原文的對應段落**；沒有可靠原始文章編號時記為 null。
* 170 份來源 index、空分類標記、manifest 與驗證／錯誤報告另以原始 bytes 保存於 `provenance/`，且每篇 metadata 附上完整 Gmail thread ID、labels、headers 與 MIME 清單。
* 2,494 篇使用 BBS 日期；其餘 40 篇只有轉寄日期或無法辨識 BBS 日期，畫面明確標示，不能視為 2017 年 BBS 文章。
* 多種編碼皆嚴格解碼成功時，根據臺灣 BBS 語境優先 CP950。`‧/•`、`～/∼` 等字元存在 Big5 映射歧義，並非可百分之百斷言的來源 charset；逐篇 metadata 保留候選編碼資訊。12 篇需 Big5-HKSCS。殘缺位元組以可追溯 `\xNN` 顯示，原始 bytes 永久可下載，不以亂碼 replacement character 猜字。
* ANSI 在解碼**之前**分離，因此插入中文字兩個 Big5 bytes 中間的色碼不會破壞文字。有效半色字用同一字元左右裁切，兩邊保留各自顏色。孤立 lead byte 是來源損壞，不能假裝是有效半色字。
* 支援 30–37、40–47、90–97、100–107、256 色、RGB、reset、高亮、底線、閃爍、反白及取消設定；狀態跨行。閃爍預設暫停，可自願開啟，並尊重減少動態設定。
* 游標／捲動／刪行與私有 `=m/=S/=M`、不完整控制序列記錄於 metadata/log。沒有原始 terminal viewport 與實作規格時，重播會刪掉典藏文字，所以不套用破壞性刪行。這是非破壞性的文章呈現，不宣稱重建互動 terminal 的每個畫面。
* 原始模式以 ASCII 的實測字寬為一欄，所有東亞寬／模糊寬度字元固定兩欄；框線與區塊符號再按實測 glyph advance 縮放填滿欄位，避免接縫；含全形空白、框線、區塊符號。逐字欄位避免裝置字型比例不同而累積錯位，停用 ligature。字形外觀仍取決於系統字型；要統一外觀，可依法自託管授權的 Noto Sans Mono CJK TC WOFF2 並重新測字形，但不要使普通文章先下載巨大字型。
* 閱讀模式保留換行且合理換行；圖形啟發式偵測維持固定欄寬，不能保證所有特殊排版都正確，因此原始模式永遠可切換。
* 全文 HTML escape；原文的 script/img/iframe 等僅顯示文字。其他 MIME HTML 部分同樣 escaped，不執行內容。

## 手機、搜尋與離線

正文預設 18px（16–26px），1.65 行高；按鈕至少 44px。底部上一頁／返回看板／下一頁導航有 safe-area padding。一般正文不橫向捲動，圖形在自己的橫向捲動容器裡。滑動換頁只適用一般區域，不攔截圖形、按鈕、連結、選取文字或垂直閱讀。

字體、閱讀／原始模式、深色主題、最近看板／文章與近 100 篇的捲動位置存 localStorage；不需要帳號。Web Share API 不支援時複製連結，clipboard 不可用時直接顯示網址。

搜尋 worker 採 NFKC、小寫、中文單字／雙字與 Latin 完整詞倒排索引，AND 比對查詢詞；不是語意搜尋，也不保證完整短語命中。64 份倒排索引按查詢需求載入，結果 metadata 與正文每 40 篇一個分片，僅下載目前 20 個結果需要的分片；可逐頁載入全部結果。首頁與單篇文章不預載全文資料。

PWA scope 使用相對網址，支援 GitHub Pages 的 `/tmugfoldbbs/` 子路徑。核心快取很小，只快取最近 50 個讀過的 HTML 頁面，原始檔與全文索引不自動整批快取。離線文章列表可直接閱讀已保存文章，未保存頁面回退到離線說明。service worker 版本依來源與程式雜湊更新；保留近讀頁面快取，清除舊核心快取。可手動清除離線頁面／閱讀紀錄。瀏覽器可能清除本機儲存；快取不是永久典藏備份。

## 測試

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
# 瀏覽器測試需開發用 Playwright；正式網站沒有 Node dependency。
BBS_URL=http://127.0.0.1:8000/ node tests/browser.cjs
python3 tools/verify_site.py ../generated-site ../build-reports
```

瀏覽器測試涵蓋 Chromium／WebKit 的 320、375、390、430、768、1280px，檢查頁面溢出、點擊區、中文字兩欄、字體／模式保存、繁體中文搜尋、連續閱讀、圖形滑動不換頁與關閉本機 HTTP 服務後離線閱讀。這是桌面引擎的手機尺寸與觸控模擬，**不等於實際 iPhone Safari／Android Chrome 硬體驗收**。上線後實機清單：Safari 加入主畫面、Android 安裝、旋轉螢幕、VoiceOver/TalkBack、低電量與減少動態設定、飛航模式、Home Indicator、作業系統清除快取後的回退。

`conversion.log` 逐篇記錄解碼歧義、殘缺 bytes、metadata 缺失、ANSI 例外、真正轉換失敗。單篇失敗保留原檔與 fallback 文字，仍處理下一篇；最後以非零 exit code 提醒禁止誤報成功。`build-verification.json` 比對來源數量、每個分類與下載 hashes；`site-integrity.json` 驗證所有內部網址、搜尋文件、文章與原始檔。

## 公開部署與私人部署

**公開：** GitHub Pages 將來源設為 `gh-pages`、`/(root)`，入口是 index.html；Cloudflare Pages／Netlify 可直接部署同一產出，不需要 build server 或資料庫。Pages 的設定與上線結果應以實際網址檢查，不能僅因 push 成功就宣稱已上線。相關官方說明：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)。

**私人：** 建議先將完整靜態站放在 NAS 或受控主機，用 Tailscale/VPN 限定網路；或以 Cloudflare Tunnel 到內部靜態伺服器，再用 [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/) 限定使用者。必須同時保護 HTML、`originals/`、`metadata/`、`search/`，並避免留下可繞過 Access 的公開 origin；不能只有首頁登入。既有 GitHub repository 是公開的，私人前端不能使已公開的 Git commit 變成私人；原始來源存取權也必須一併處理。

noindex/nofollow、robots.txt、難猜網址不等於存取控制。私人共用裝置應清除快取與閱讀紀錄；若政策禁止離線內容，可刪除 app.js 的 service worker 註冊、取消快取並調整 manifest，在私人網站用全新 origin 測試。登出 Access 不會自動清除已下載的離線頁面。

## 正式公開前的隱私檢查流程

1. 執行完整轉換，檢閱 `privacy-review.json`：email、電話、IP、疑似地址與作者識別碼逐篇列出 message ID 與數量，避免報告再複製個資。
2. 人工讀取旗標文章，另外逐篇檢查姓名、暱稱、健康、關係與社團內部內容；自動掃描無法識別所有個資或同意狀態。
3. 確認公開範圍包括全文搜尋、原始 TXT、EML 的收件人／寄件人與 routing headers。只改 HTML 不足以去識別。
4. 保存審查者、日期、用途與批准範圍。未批准者選擇私人部署；若需公開去識別版，另建明確標示的衍生輸出，**不修改典藏原檔**，並重新產生對應搜尋索引。
5. 部署後用未登入／無 VPN 的另一個瀏覽器檢查整站存取權，並重新確認 repository 可見性與備份保存政策。

自動掃描是風險清單，不代表完成同意或法律審查。此專案不自動刪文、改字或猜測匿名化。
