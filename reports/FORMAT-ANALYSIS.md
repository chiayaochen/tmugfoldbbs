# 原始格式分析與轉換決策

來源：`archive/gmail-tmu-service` commit `01008ff3d636695b06f73c303637838d8f0d1fa6`。在批次轉換前，先掃描原始 bytes，並選取 10 篇不同年代、看板／分類與類型的樣本檢查。

|項目|實際結果|
|---|---|
|來源|2,547 個 RFC822 EML；2,534 個不同 Gmail message IDs|
|分類|167 個 Gmail labels；34 個沒有直接文章的分類|
|換行|全部 CRLF；正文總計 170,795 組 CRLF，沒有孤立 LF/CR|
|選用編碼|2,522 篇 CP950；12 篇 Big5-HKSCS；沒有直接假設 UTF-8|
|編碼歧義|2,172 篇有不同 legacy codec 映射，詳細候選寫在每篇 metadata|
|來源殘缺|350 篇有無法嚴格解碼的 bytes；原始 bytes 不變，以 `\xNN` 保留顯示|
|有效半色字|59 篇、3,641 個字符；先解析 byte 控制序列再 incremental decode|
|文章格式|2,495 篇 FireBird 發信人格式；39 篇沒有完整標準 header，保留全文|
|BBS 日期|2,494 篇可判定；40 篇顯示未辨識並標示轉寄日期來源|
|年代|可靠 BBS 日期為 1998–2012；2017 是 Gmail 轉寄時間|
|原始看板|basic_serve 2,494 篇、BulletinWanted 1 篇，其餘未辨識|
|ANSI|172,522 組 CSI；m 172,447，S 36，M 37，A 1，其他 `[` 1|

Big5 和 CP950 的差異包含 `‧/•`、`～/∼`、`﹨/＼`、`⊙/☉`、`∕/／`；臺灣來源優先採 CP950，但無 charset 的備份不能百分之百證明映射。不能以 UTF-8 replacement characters 替代，也不能憑語意補寫殘缺字。

樣本包括 1998 的出隊心得、2000 的長篇轉載與跨看板文章、2002 隊聚心得、2006 聯合成果展含半色字及版宣、2009 HKSCS 文章，以及無標準 header 的完整 ANSI 圖。所有樣本 EML 與抽出的 MIME 本文逐一 hash 比對；單篇失敗的 fallback 另用刻意損壞的 fixture 驗證，不混入典藏文章。

Parser 規則以發信人／作者、可選暱稱、信區／看板／板名、標題、發信站／時間辨識；前導空白與沒有暱稱的 FireBird 格式另外處理。metadata 無法確定時記錄例外，原文、簽名檔、引用與來源訊息完整留在文章正文。標題不足時採郵件 Subject 並記錄 fallback；日期不足時清楚區別 BBS 日期與郵件 Date。原始文章編號無可靠來源，不自行推算。

ANSI 支援前景、背景、亮色、底線、閃爍、反白、reset、256 色、RGB，以及跨行狀態。含 private `=m/=S/=M` 等游標／視窗指令時保留原始序列紀錄，不進行會刪除文字的 destructive replay。共有 107 篇有特殊 ANSI 註記，包括未支援 SGR，這不等於整篇轉換失敗。

手機閱讀使用可換行的原文區塊；框線、區塊符號與可靠辨識的圖形區塊固定欄寬。原始模式全部固定欄寬，ASCII 一欄、CJK／全形空白／東亞模糊寬度符號兩欄。實際 DOM 量測檢查 ASCII 與 CJK 比例，框線 glyph 另外縮放填滿欄位，避免字型 fallback 造成斷線。原始檔下載保留 CRLF、ANSI、編碼及所有原始 bytes。

完整來源索引、manifest、驗證與錯誤檔、空標記共 170 份均原樣保存在 `provenance/`；每篇 metadata 附上原 Gmail thread ID、labels、headers、MIME metadata。這些檔案與 EML 一起使顯示層的解析選擇可以重新追查與更換。
