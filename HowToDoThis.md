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

### 安裝 python
- brew install pyenv
- brew install pyenv-virtualenv
- Add pyenv init to your shell
    - 讀取順序是 .zshenv → [.zprofile if login] → [.zshrc if interactive] → [.zlogin if login] → [.zlogout sometimes].
    - 輸入 cd ~
    - 輸入 touch .zshrc
    - 輸入 open -e .zshrc
    - 就可以很簡單的用文字編輯器來讀寫這個檔案。
    - 在文字編輯器中寫入

### For pyenv
```
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if which pyenv > /dev/null;
then eval "$(pyenv init -)";
fi
```

### For pyenv-virtualenv auto-activation
```
if which pyenv-virtualenv-init > /dev/null;
then eval "$(pyenv virtualenv-init -)";
fi
```
- 承上，這除了設定環境變數之外，也會讓虛擬環境自動啟動
- 輸入 source .zshrc
    - source 指令，能從指定的檔案中讀取指令來執行，常用以執行修改過後的特殊檔案。
- 輸入 exec "$SHELL" 重新啟動SHELL
- pyenv versions
    - 查詢已經安裝的python版本
- pyenv install --list
    - 列出可以安裝的python版本
- pyenv install [python版本]
    - 安裝python
- pyenv uninstall [虛擬環境名稱]
    - 刪除安裝的版本，包含虛擬環境
- pyenv virtualenv [python版本] [虛擬環境名稱]
    - 安裝虛擬環境

----