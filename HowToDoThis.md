### SSH的問題造成無法上傳檔案
- 在使用者的主目錄 ls -a 檢查看看
    - 有沒有 .ssh 目錄
    - 有沒有 id_rsa 這個檔案
    - 有沒有 id_rsa.pub 這個檔案
- 如果有缺，則必須自己建立新的  
  ssh-keygen -t rsa -C "[這邊填寫我的Email]"
- 完成之後在 .ssh 目錄下面應該可以找到  
  公鑰 id_rsa.pub
- 在網頁 https://github.com/settings/keys 裡面
    - 按下 New SSH key
    - open id_rsa.pub -e  
      把公鑰 id_rsa.pub 的內容複製貼上

----

### 新增 Github 上的 Repo
- 在網頁上新增 Repo 名字叫做 tmugfoldbbs
- git clone git@github.com:chiayaochen/tmugfoldbbs.git
- 嘗試 touch index.html 建立 index.html 並看看能不能上傳
    - git add --all
    - git commit -m "Initial commit"
    - git push -u origin main
- git checkout -b gh-pages
    - 然後把 gh-pages 推回去
    - git push -u origin gh-pages
- 那麼在網址 http://chiayaochen.github.io/tmugfoldbbs/ 就是屬於這個倉庫的網頁了
- 記得在 VScode 新增這個專案的資料夾，編輯上就更方便了

----
