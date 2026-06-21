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
                "你是中文與英文輸入法助手。請根據使用者輸入的上下文進行後續字詞預測。\n"
                "你必須同時預測三層同心圓環的候選詞：\n"
                "- layer1 (最內圈): 接續當前輸入最可能的 3 個候選字詞與其可能性機率(0.0 到 1.0)。\n"
                "- layer2 (中圈): 假設第一圈選了最可能項目後，再接續的 3 個候選字詞與機率。\n"
                "- layer3 (外圈): 再接續的 3 個候選字詞與機率。\n"
                "請嚴格以 JSON 格式輸出，不要包含任何 Markdown 標記或 ```json 包裝，格式如下：\n"
                "{\n"
                "  \"layer1\": [{\"word\": \"詞1\", \"prob\": 0.8}, {\"word\": \"詞2\", \"prob\": 0.6}, {\"word\": \"詞3\", \"prob\": 0.4}],\n"
                "  \"layer2\": [{\"word\": \"詞4\", \"prob\": 0.7}, {\"word\": \"詞5\", \"prob\": 0.5}, {\"word\": \"詞6\", \"prob\": 0.3}],\n"
                "  \"layer3\": [{\"word\": \"詞7\", \"prob\": 0.6}, {\"word\": \"詞8\", \"prob\": 0.4}, {\"word\": \"詞9\", \"prob\": 0.2}]\n"
                "}"
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
                
                # 嘗試解析 JSON
                predictions = self.parse_json_response(raw_content)
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

    def parse_json_response(self, text):
        # 尋找第一個 { 與最後一個 } 來容錯 markdown ```json 標記
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            try:
                data = json.loads(json_str)
                # 驗證格式並填補預設值
                result = {}
                for layer in ['layer1', 'layer2', 'layer3']:
                    result[layer] = []
                    items = data.get(layer, [])
                    # 確保每層最多 3 個
                    for item in items[:3]:
                        word = item.get('word', '').strip()
                        prob = float(item.get('prob', 0.5))
                        if word:
                            result[layer].append({'word': word, 'prob': prob})
                    # 如果該層為空，加入填充字詞
                    if not result[layer]:
                        result[layer] = [{'word': '...', 'prob': 0.1}]
                return result
            except Exception as e:
                print(f"JSON 解析出錯: {e}, 原始文字: {text}")
        
        # 退化處理：如果不是 JSON，嘗試按行解析
        return self.fallback_parse(text)

    def fallback_parse(self, text):
        # 將所有中英文單字/詞語抓出來，平分到三層
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z\d\-\']+', text)
        words = [w for w in words if len(w) > 0][:9]
        
        result = {'layer1': [], 'layer2': [], 'layer3': []}
        for i, word in enumerate(words):
            prob = max(0.2, 0.9 - (i % 3) * 0.25)
            if i < 3:
                result['layer1'].append({'word': word, 'prob': prob})
            elif i < 6:
                result['layer2'].append({'word': word, 'prob': prob})
            else:
                result['layer3'].append({'word': word, 'prob': prob})
                
        # 補空值
        for layer in ['layer1', 'layer2', 'layer3']:
            if not result[layer]:
                result[layer] = [{'word': '...', 'prob': 0.1}]
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
