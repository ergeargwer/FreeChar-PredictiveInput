# 🧠 FreeChar AI 彩虹圓環預測輸入法 (FreeChar AI Predictive Input)

一個專為 PC 環境設計的創新 AI 預測輸入法原型，包含 **Web 網頁端** 與 **Python Pygame 桌面端** 兩種版本，旨在探索非傳統的文字聯想互動體驗。

---

## ✨ 核心創新特色

* **🌈 彩虹同心圓字圈 (Rainbow Rings)**
  * 打破傳統的水平線性預測列，將預測字詞分布於最多 3 層同心圓環中（內圈、中圈、外圈），結構類似彩虹層次。
* **📊 機率與透明度動態對應**
  * 預測字詞的透明度與其被選中的機率成正比。機率越高，字體越清晰；機率越低，字體越淡，且越外圈基本透明度越低。
* **🎹 流暢的鍵盤與物理旋轉動畫**
  * **`UP` / `DOWN` (上下鍵)**：滾動/旋轉當前焦點圓環來選詞。圓環具有平滑的彈性插值物理滾動動畫 (60 FPS)，並伴隨機械齒輪卡嗒聲 (`gear_click.wav`)。
  * **`RIGHT` (右鍵 [→])**：確認選定焦點圓環最頂端的字詞，寫入輸入框，播放確認鈴聲 (`bell_ring.wav`)，並將焦點向外移入下一圈。
  * **`LEFT` (左鍵 [←])**：返回上一圈，並自動退格刪除上一次已選定上字的詞彙。
* **🌐 OpenRouter API 非同步整合**
  * 採用 **OpenRouter API**（預設為 Google Gemini 2.5 Flash）作為聯想大腦。
  * **非同步執行緒 (Threading)** 與 **防抖 (Debounce 450ms)** 機制，保證在打字與網路連線時介面毫無卡頓。
  * 具備**本地預測快取**以達到 0ms 的重複打字反應。
* **🇹🇼 中英文 IME 支援**
  * 桌面版完美整合 Windows IME 系統（如微軟注音、新倉頡），在應用內可以直接切換輸入法並打出中文字。

---

## 📁 專案目錄結構

* `main.py` - 桌面端 Pygame 視窗、圓環渲染與 IME 互動主程式。
* `api_client.py` - 背景非同步 OpenRouter API 請求模組，負責載入金鑰與呼叫。
* `sound_generator.py` - 音效產生器，啟動時會自動在本地合成需要的齒輪與響鈴 `.wav` 音效。
* `run.bat` - 一鍵啟動批次檔，會自動偵測 Python 環境、下載必要依賴、產生音效並執行主程式。
* `FreeChar.html` - 網頁版原型，單一 HTML 檔，提供 OpenRouter 連線與快取聯想。
* `key.txt` - (本地專用，不加入 Git) 存放您的 API 金鑰（如 OpenRouter 的 `sk-or-`）。
* `.gitignore` - 已設定忽略 `key.txt` 及自動生成的 `.wav` 音效，防止金鑰外洩。

---

## 🚀 快速開始指南

### 1. 金鑰配置
在專案根目錄下建立名為 `key.txt` 的文字檔，並在其中貼入您的 OpenRouter API Key：
```text
openrouter
sk-or-xxxxxxxxxxxxxxxxxxxxxx...
```

### 2. 啟動 Python 桌面版
* 雙擊執行目錄下的 **`run.bat`**。
* 腳本會自動檢查並使用 pip 安裝 `pygame` 與 `jieba`。
* 自動生成需要的音效資源並開啟預測視窗。

### 3. 啟動 Web 網頁版
* 直接使用瀏覽器開啟 **`FreeChar.html`**。
* 可點擊介面上的「匯入 key.txt」按鈕，快速帶入您的 API 金鑰。

---

## 🛠️ 技術需求

* **作業系統**：Windows 10/11
* **程式語言**：Python 3.8+ (推薦使用 3.13 以搭配預設 pip 環境)
* **第三方套件**：
  * `pygame` (2.0+)
  * `jieba` (中文分詞)

---

## 🔒 安全聲明
本專案已在 `.gitignore` 排除 `key.txt`。**請絕對不要將 `key.txt` 發布至 GitHub 等公開代碼庫**，以免您的 API 額度遭到盜用。
