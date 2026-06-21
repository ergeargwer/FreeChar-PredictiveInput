import json
import urllib.request
import urllib.error
import threading
import re
import os

class OpenRouterClient:
    def __init__(self):
        self.api_key = ''
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.cache = {}
        self.load_key_from_file()

    def load_key_from_file(self):
        # 尋找本地 key.txt
        if os.path.exists('key.txt'):
            try:
                with open('key.txt', 'r', encoding='utf-8') as f:
                    content = f.read()
                self.api_key = self.parse_key(content)
                if self.api_key:
                    print(f"成功從 key.txt 載入 OpenRouter API 金鑰: {self.api_key[:10]}...")
            except Exception as e:
                print(f"讀取 key.txt 失敗: {e}")

    def parse_key(self, text):
        lines = [line.strip() for line in text.split('\n')]
        # 1. 尋找 sk-or-
        for line in lines:
            if line.startswith('sk-or-'):
                return line
        # 2. 尋找 openrouter 下一行
        for i in range(len(lines) - 1):
            if 'openrouter' in lines[i].lower():
                if len(lines[i+1]) > 15:
                    return lines[i+1]
        return None

    def set_api_key(self, api_key):
        self.api_key = api_key.strip()

    def predict_async(self, text, model, callback, temperature=0.3):
        if not self.api_key:
            callback(None, "未設定 API Key")
            return

        cache_key = (text.strip(), model)
        if cache_key in self.cache:
            # 立即回傳快取結果
            callback(self.cache[cache_key], None)
            return

        # 在背景執行緒發送請求
        t = threading.Thread(
            target=self._predict_worker,
            args=(text, model, callback, temperature, cache_key),
            daemon=True
        )
        t.start()

    def _predict_worker(self, text, model, callback, temperature, cache_key):
        try:
            # 設計 JSON 格式的 Prompt
            system_prompt = (
                "你是中文與英文輸入法助手。請根據使用者輸入的上下文預測下一個可能的字詞。\n"
                "請直接回傳 12~15 個最可能的中文或英文候選字詞，並給予每個字詞 0~100 的信心分數。\n"
                "格式為：字詞:分數,字詞:分數,字詞:分數...\n"
                "例如：氣:92,很:85,的:78,天氣:72,好:68\n"
                "注意：不要包含任何編號、說明、解釋、Markdown 標記或額外的標點符號。"
            )

            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"使用者目前已輸入: {text}"}
                ],
                "temperature": temperature,
                "max_tokens": 200
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "FreeChar Desktop Predictor"
            }

            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(data).encode('utf-8'),
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=4.0) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                raw_content = res_data['choices'][0]['message']['content'].strip()
                
                # 嘗試解析
                predictions = self.parse_ai_response(raw_content)
                if predictions:
                    self.cache[cache_key] = predictions
                    callback(predictions, None)
                else:
                    callback(None, "無法解析 API 回傳格式")

        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            try:
                err_json = json.loads(err_msg)
                callback(None, err_json.get('error', {}).get('message', f"HTTP {e.code}"))
            except:
                callback(None, f"HTTP 錯誤: {e.code}")
        except Exception as e:
            callback(None, f"連線錯誤: {str(e)}")

    def parse_ai_response(self, text):
        # 尋找 詞:分數
        matches = re.findall(r'([^:,\s\n]+)\s*:\s*(\d+)', text)
        candidates = []
        for word, score_str in matches:
            try:
                score = int(score_str)
                prob = score / 100.0
                candidates.append({'word': word.strip(), 'prob': prob})
            except ValueError:
                continue
                
        # 退化處理：如果沒解析出東西，使用正則表達式隨機分詞，並分配預設分數
        if not candidates:
            words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z\d\-\']+', text)
            words = [w for w in words if len(w) > 0][:12]
            for i, word in enumerate(words):
                prob = max(0.2, 0.9 - (i % 4) * 0.2)
                candidates.append({'word': word, 'prob': prob})

        # 將候選詞分配到三層同心圓中，每層 4 個詞，共 12 個詞
        result = {'layer1': [], 'layer2': [], 'layer3': []}
        
        # 確保有足夠的填充詞以防 API 回傳不夠
        while len(candidates) < 12:
            candidates.append({'word': '...', 'prob': 0.1})
            
        for i, cand in enumerate(candidates[:12]):
            if i < 4:
                result['layer1'].append(cand)
            elif i < 8:
                result['layer2'].append(cand)
            else:
                result['layer3'].append(cand)
                
        return result

    def test_connection_async(self, api_key, model, callback):
        t = threading.Thread(
            target=self._test_connection_worker,
            args=(api_key, model, callback),
            daemon=True
        )
        t.start()

    def _test_connection_worker(self, api_key, model, callback):
        try:
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 5
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "FreeChar Desktop Predictor Test"
            }
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(data).encode('utf-8'),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=4.0) as response:
                if response.status == 200:
                    callback(True, None)
                else:
                    callback(False, f"HTTP狀態碼: {response.status}")
        except Exception as e:
            callback(False, str(e))
