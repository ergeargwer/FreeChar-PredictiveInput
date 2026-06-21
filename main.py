import pygame
import pygame.gfxdraw
import math
import sys
import os
import time
from api_client import OpenRouterClient

# 初始化 Pygame 與音效系統
pygame.init()
pygame.mixer.init()

# 設定視窗大小與標題
WIDTH, HEIGHT = 1050, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF | pygame.HWSURFACE)
pygame.display.set_caption("OpenRouter AI 彩虹圓環預測輸入法")
clock = pygame.time.Clock()

# 載入音效
try:
    sound_click = pygame.mixer.Sound("gear_click.wav")
    sound_bell = pygame.mixer.Sound("bell_ring.wav")
    # 設定適度音量
    sound_click.set_volume(0.4)
    sound_bell.set_volume(0.7)
except Exception as e:
    print(f"音效載入失敗 (請確認已先執行 sound_generator.py): {e}")
    sound_click = None
    sound_bell = None

# 尋找中文字型
def get_font(size, bold=False):
    font_names = ['microsoftjhenghei', 'jhenghei', 'msgothic', 'simsun', 'dengxian', 'arial']
    for name in font_names:
        path = pygame.font.match_font(name)
        if path:
            # 建立字型
            font = pygame.font.Font(path, size)
            font.set_bold(bold)
            return font
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font

FONT_TITLE = get_font(32, bold=True)
FONT_SUBTITLE = get_font(16)
FONT_TEXT = get_font(24)
FONT_UI = get_font(14)
FONT_RING_WORD = get_font(18, bold=True)
FONT_RING_0 = get_font(24, bold=True)
FONT_RING_1 = get_font(20, bold=True)
FONT_RING_2 = get_font(16, bold=True)

def draw_text_with_glow(surf, text, font, pos, color, alpha):
    # 1. 繪製發光底影 (在 pos 四周稍微偏移繪製半透明的文字，實現發光感)
    glow_alpha = int(alpha * 0.35)
    if glow_alpha > 0:
        glow_color = color[:3] + (glow_alpha,)
        glow_surf = font.render(text, True, glow_color)
        glow_rect = glow_surf.get_rect(center=pos)
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            surf.blit(glow_surf, (glow_rect.x + dx, glow_rect.y + dy))
            
    # 2. 繪製主文字
    main_color = (255, 255, 255)
    main_surf = font.render(text, True, main_color)
    main_surf.set_alpha(alpha)
    main_rect = main_surf.get_rect(center=pos)
    surf.blit(main_surf, main_rect)


# 顏色定義 (現代暗色系風格)
BG_COLOR = (13, 17, 23)        # 深灰藍
CARD_BG = (22, 27, 34, 180)     # 半透明卡片背景
TEXT_COLOR = (240, 246, 252)    # 亮白
BORDER_COLOR = (48, 54, 61)     # 灰框
ACCENT_COLOR = (88, 166, 255)   # 藍色焦點

# 圓環漸層主題定義
THEMES = {
    "rainbow": {
        "name": "彩虹漸層",
        "layer1": (255, 92, 141),   # 珊瑚橘紅
        "layer2": (0, 230, 118),    # 亮綠色
        "layer3": (141, 110, 255)   # 亮紫色
    },
    "blue": {
        "name": "海洋藍色",
        "layer1": (0, 210, 255),    # 天藍
        "layer2": (0, 150, 255),    # 湛藍
        "layer3": (0, 80, 255)      # 深藍
    },
    "yellow": {
        "name": "黃金亮橙",
        "layer1": (255, 234, 0),    # 明黃
        "layer2": (255, 145, 0),    # 橙色
        "layer3": (213, 0, 0)       # 磚紅
    }
}

# 推薦模型列表
MODELS = [
    {"name": "Gemini 2.5 Flash", "id": "google/gemini-2.5-flash"},
    {"name": "DeepSeek V3", "id": "deepseek/deepseek-chat"},
    {"name": "Llama 3.1 8B (免費)", "id": "meta-llama/llama-3.1-8b-instruct:free"},
    {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"}
]

# 應用程式狀態管理
class AppState:
    def __init__(self):
        self.api_client = OpenRouterClient()
        self.input_text = "今天天氣"
        self.editing_text = ""
        
        # 圓環設定
        self.current_theme = "rainbow"
        self.global_alpha = 0.9      # 使用者可調的整體介面透明度 (0.2 ~ 1.0)
        self.selected_model_idx = 0
        
        # 鍵盤互動焦點圈 (0=內圈, 1=中圈, 2=外圈)
        self.focus_layer = 0
        
        # 圓環旋轉控制 (角度皆以度數 degree 表示)
        # 每層有 3 個預測詞，在 0, 120, 240 度。
        # 指標選定位置固定在正上方 (即 270 度)。
        # 因此，當某個詞的當前旋轉角度為 270 度時，它就是被選中的詞。
        self.layers = {
            0: {"target_angle": 270.0, "current_angle": 270.0, "words": []},
            1: {"target_angle": 270.0, "current_angle": 270.0, "words": []},
            2: {"target_angle": 270.0, "current_angle": 270.0, "words": []}
        }
        
        # 預測資料預設填充
        self.fill_default_predictions()
        
        # 連線狀態與提示
        self.connection_status = "idle"  # idle, testing, connected, error
        self.connection_message = "請點擊匯入或輸入 API Key"
        if self.api_client.api_key:
            self.connection_status = "testing"
            self.connection_message = "自動測試連線中..."
            self.test_api_connection(self.api_client.api_key)

        # 請求防抖
        self.last_input_time = time.time()
        self.debounce_triggered = False
        
        # 啟動 IME 系統輸入法支援
        pygame.key.start_text_input()
        
        # 預先請求一次預測
        self.request_predictions()

    def fill_default_predictions(self):
        # 每一層 3 個候選項，包含詞語與機率
        self.layers[0]["words"] = [
            {"word": "很好", "prob": 0.9},
            {"word": "不錯", "prob": 0.6},
            {"word": "一般", "prob": 0.4}
        ]
        self.layers[1]["words"] = [
            {"word": "適合", "prob": 0.8},
            {"word": "出去", "prob": 0.5},
            {"word": "睡覺", "prob": 0.3}
        ]
        self.layers[2]["words"] = [
            {"word": "散步", "prob": 0.75},
            {"word": "玩耍", "prob": 0.5},
            {"word": "旅遊", "prob": 0.25}
        ]

    def test_api_connection(self, api_key):
        self.connection_status = "testing"
        self.api_client.set_api_key(api_key)
        model = MODELS[self.selected_model_idx]["id"]
        
        def callback(success, error_msg):
            if success:
                self.connection_status = "connected"
                self.connection_message = "連線成功！Gemini 已就緒"
                self.request_predictions()
            else:
                self.connection_status = "error"
                self.connection_message = f"連線失敗: {error_msg}"
                
        self.api_client.test_connection_async(api_key, model, callback)

    def request_predictions(self):
        if self.connection_status != "connected":
            return
        
        full_text = self.input_text
        model = MODELS[self.selected_model_idx]["id"]
        
        def callback(predictions, error_msg):
            if predictions:
                # 在非同步回呼中更新圓環資料
                self.layers[0]["words"] = predictions.get("layer1", [])
                self.layers[1]["words"] = predictions.get("layer2", [])
                self.layers[2]["words"] = predictions.get("layer3", [])
                # 重設各層的旋轉角度回歸預設位置 (270度代表頂部選中)
                for i in range(3):
                    self.layers[i]["target_angle"] = 270.0
                    self.layers[i]["current_angle"] = 270.0
                self.focus_layer = 0
            elif error_msg:
                print(f"預測錯誤: {error_msg}")

        self.api_client.predict_async(full_text, model, callback)

    def update(self):
        # 平滑滾動插值
        for i in range(3):
            diff = self.layers[i]["target_angle"] - self.layers[i]["current_angle"]
            # 角度溢出包裝處理
            diff = (diff + 180) % 360 - 180
            
            # 播放齒輪卡嗒聲 (當轉動角度跨越 10 度時)
            if abs(diff) > 1.5:
                prev_angle = self.layers[i]["current_angle"]
                self.layers[i]["current_angle"] += diff * 0.16
                
                # 計算是否有跨越 120 度分割線的卡嗒點
                step = 120.0
                if int(prev_angle / step) != int(self.layers[i]["current_angle"] / step):
                    if sound_click:
                        sound_click.play()
            else:
                self.layers[i]["current_angle"] = self.layers[i]["target_angle"]

        # 防抖 API 預測請求
        if not self.debounce_triggered and (time.time() - self.last_input_time > 0.45):
            self.request_predictions()
            self.debounce_triggered = True

    def rotate_layer(self, layer_idx, direction):
        # 3個選項在 0, 120, 240。旋轉 120 度可切換選項。
        if direction == "up":
            self.layers[layer_idx]["target_angle"] += 120.0
        elif direction == "down":
            self.layers[layer_idx]["target_angle"] -= 120.0

    def get_selected_word(self, layer_idx):
        layer = self.layers[layer_idx]
        words = layer["words"]
        if not words:
            return ""
            
        # 計算哪個單字最靠近 270 度
        current_angle = layer["target_angle"] % 360
        # 選項初始分配角度為：[0, 120, 240]，對應索引 0, 1, 2
        # 相對的，我們找出哪一個項目旋轉後對齊 270 度。
        # 角度公式：WordAngle = (InitialAngle + current_angle - 270) % 360
        # 我們直接看當前 target_angle 與 270 的差值來推算選中了哪一個索引。
        # 或者我們用精準的幾何對齊：
        best_idx = 0
        min_diff = 999.0
        for idx in range(len(words)):
            init_angle = idx * 120.0
            word_angle = (init_angle + layer["current_angle"]) % 360
            diff = abs((word_angle - 270 + 180) % 360 - 180)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        return words[best_idx]["word"] if best_idx < len(words) else ""

# 初始化狀態
state = AppState()

# UI 交互滑桿定義
class Slider:
    def __init__(self, x, y, w, h, label, min_val, max_val, current_val):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.val = current_val
        self.is_dragging = False

    def draw(self, surf):
        # 標題
        lbl_surf = FONT_UI.render(f"{self.label}: {int(self.val*100) if self.max_val <= 1.0 else int(self.val)}%", True, TEXT_COLOR)
        surf.blit(lbl_surf, (self.rect.x, self.rect.y - 20))
        
        # 槽線
        pygame.draw.rect(surf, BORDER_COLOR, self.rect, border_radius=3)
        
        # 滑塊位置
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + int(ratio * self.rect.w)
        handle_rect = pygame.Rect(handle_x - 6, self.rect.y - 4, 12, self.rect.h + 8)
        
        # 拖曳狀態顏色
        color = ACCENT_COLOR if self.is_dragging else (150, 150, 150)
        pygame.draw.rect(surf, color, handle_rect, border_radius=4)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.inflate(10, 20).collidepoint(event.pos):
                self.is_dragging = True
                self.update_val(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.is_dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                self.update_val(event.pos[0])

    def update_val(self, mouse_x):
        ratio = (mouse_x - self.rect.x) / self.rect.w
        ratio = max(0.0, min(1.0, ratio))
        self.val = self.min_val + ratio * (self.max_val - self.min_val)

# 按鈕定義
class Button:
    def __init__(self, x, y, w, h, text, callback, color=BORDER_COLOR):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.color = color

    def draw(self, surf):
        is_hover = self.rect.collidepoint(pygame.mouse.get_pos())
        color = tuple(min(255, c + 30) for c in self.color) if is_hover else self.color
        pygame.draw.rect(surf, color, self.rect, border_radius=6)
        pygame.draw.rect(surf, BORDER_COLOR, self.rect, 1, border_radius=6)
        
        txt_surf = FONT_UI.render(self.text, True, TEXT_COLOR)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surf.blit(txt_surf, txt_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.callback()

# 文字輸入框元件 (針對金鑰手動輸入)
class InputBox:
    def __init__(self, x, y, w, h, text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.active = False

    def draw(self, surf):
        color = ACCENT_COLOR if self.active else BORDER_COLOR
        pygame.draw.rect(surf, color, self.rect, 2, border_radius=6)
        
        # 密碼遮罩顯示
        display_text = "*" * len(self.text) if self.text else "請在此點擊輸入 API Key..."
        color_text = TEXT_COLOR if self.text else (120, 120, 120)
        
        txt_surf = FONT_UI.render(display_text, True, color_text)
        surf.blit(txt_surf, (self.rect.x + 10, self.rect.y + (self.rect.h - txt_surf.get_height())//2))

    def handle_event(self, event, active_ime):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.active = self.rect.collidepoint(event.pos)
                if self.active:
                    # 當點選 API Key 輸入時，暫停全域的 IME 文字編輯以防衝突
                    pygame.key.stop_text_input()
                else:
                    pygame.key.start_text_input()
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
                pygame.key.start_text_input()
            elif event.key not in [pygame.K_ESCAPE, pygame.K_TAB, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                self.text += event.unicode

# 實例化 UI 元件
slider_alpha = Slider(760, 480, 200, 8, "整體介面透明度", 0.2, 1.0, state.global_alpha)
api_input = InputBox(50, 600, 500, 36, state.api_client.api_key)

def import_key_file():
    # 本地嘗試讀取並重新測試連線
    state.api_client.load_key_from_file()
    if state.api_client.api_key:
        api_input.text = state.api_client.api_key
        state.test_api_connection(state.api_client.api_key)

def test_api():
    if api_input.text:
        state.test_api_connection(api_input.text)
        # 寫入 key.txt
        try:
            with open("key.txt", "w", encoding="utf-8") as f:
                f.write(f"openrouter\n{api_input.text}\n")
        except Exception as e:
            print(f"寫入 key.txt 失敗: {e}")

btn_import = Button(560, 600, 110, 36, "匯入 key.txt", import_key_file)
btn_test = Button(680, 600, 100, 36, "測試與儲存", test_api, color=(46, 125, 50))

# 渲染帶有半透明圓角的背景
def draw_rounded_panel(surf, rect, color, radius=10):
    shape_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(shape_surf, color, shape_surf.get_rect(), border_radius=radius)
    surf.blit(shape_surf, rect.topleft)

# 渲染文字游標與文字框
def draw_input_area(surf, state):
    panel_rect = pygame.Rect(50, 100, 500, 120)
    # 半透明黑底卡片
    draw_rounded_panel(surf, panel_rect, (22, 27, 34, int(200 * state.global_alpha)), 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    # 標題
    lbl = FONT_UI.render("📝 鍵盤輸入區 (切換 Windows 中文輸入法直接打字)", True, ACCENT_COLOR)
    surf.blit(lbl, (65, 110))
    
    # 計算文字與游標渲染
    render_text = state.input_text
    edit_text = state.editing_text
    
    # 已完成文字
    txt_surf = FONT_TEXT.render(render_text, True, TEXT_COLOR)
    surf.blit(txt_surf, (70, 150))
    
    # IME 候選字 (拼音中)
    x_offset = 70 + txt_surf.get_width()
    if edit_text:
        edit_surf = FONT_TEXT.render(edit_text, True, (136, 192, 250))
        surf.blit(edit_surf, (x_offset, 150))
        # 繪製下劃線表示未確定輸入
        pygame.draw.line(surf, ACCENT_COLOR, (x_offset, 180), (x_offset + edit_surf.get_width(), 180), 2)
        x_offset += edit_surf.get_width()
        
    # 閃爍游標
    if int(time.time() * 2) % 2 == 0:
        pygame.draw.line(surf, ACCENT_COLOR, (x_offset + 2, 148), (x_offset + 2, 178), 2)
        
    # 底部提示
    hint_surf = FONT_SUBTITLE.render("方向鍵: 滾動選詞 | 右鍵 [→]: 選定字詞 | 左鍵 [←]: 回退字詞", True, (120, 130, 140))
    surf.blit(hint_surf, (70, 192))
    
    return x_offset, 150  # 傳回游標位置以供字圈定位

# 繪製彩虹同心圓字圈
def draw_rainbow_rings(surf, state, cursor_x, cursor_y):
    # 字圈的圓心定位在游標右側，若是游標太靠右則限縮在 780, 220 處以獲得平衡
    center_x = min(800, max(680, cursor_x + 180))
    center_y = 220
    
    # 3 層圓環半徑
    radii = [60, 105, 150]
    
    theme = THEMES[state.current_theme]
    
    # 從最外層向最內層繪製，確保內層疊加在外層上
    for layer_idx in range(2, -1, -1):
        radius = radii[layer_idx]
        layer_data = state.layers[layer_idx]
        words = layer_data["words"]
        
        # 層基本透明度係數
        layer_base_factor = [1.0, 0.75, 0.55][layer_idx]
        
        # 焦點層突出效果
        is_focused = (state.focus_layer == layer_idx)
        
        # 取得對應的主題層顏色
        base_color = theme[f"layer{layer_idx+1}"]
        
        # 1. 繪製多層底圈（增加厚度感與霓虹發光效果）
        for k in range(5):
            glow_radius = radius + (k - 2) * 3  # 在 radius 附近擴散 [-6, -3, 0, 3, 6]
            glow_alpha = int((50 - k * 8) * layer_base_factor * state.global_alpha)
            glow_alpha = max(5, min(255, glow_alpha))
            glow_color = base_color + (glow_alpha,)
            
            glow_width = 3 if k == 2 else 1
            if is_focused:
                glow_width += 1
                
            shape_surf = pygame.Surface((glow_radius * 2 + 10, glow_radius * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(shape_surf, glow_color, (glow_radius + 5, glow_radius + 5), glow_radius, glow_width)
            surf.blit(shape_surf, (center_x - glow_radius - 5, center_y - glow_radius - 5))
        
        # 2. 繪製圓環上的預測字詞 (依層數使用不同大小字體與發光效果)
        font = [FONT_RING_0, FONT_RING_1, FONT_RING_2][layer_idx]
        
        for idx in range(len(words)):
            item = words[idx]
            word = item["word"]
            prob = item["prob"]
            
            # 計算這個詞目前的角度位置 (弧度)
            init_angle = idx * 120.0
            total_angle = (init_angle + layer_data["current_angle"]) % 360
            rad = math.radians(total_angle)
            
            # 計算在圓周上的座標位置
            word_x = center_x + int(radius * math.cos(rad))
            word_y = center_y + int(radius * math.sin(rad))
            
            # 根據機率 prob 計算透明度
            alpha_prob = int(255 * prob * layer_base_factor * state.global_alpha)
            alpha_prob = max(35, min(255, alpha_prob))
            
            # 若此詞選定焦點(頂部對齊 270 度)
            angle_diff = abs((total_angle - 270 + 180) % 360 - 180)
            is_pointing = (angle_diff < 15.0) and is_focused
            
            # 動態依據字型大小與字長計算膠囊背景尺寸
            word_w, word_h = font.size(word)
            pad_w, pad_h = 16, 10
            bg_w = word_w + pad_w
            bg_h = word_h + pad_h
            
            card = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
            
            # 卡片背景透明度與發光效果
            bg_alpha = int(140 * prob * state.global_alpha)
            if is_pointing:
                bg_alpha = min(255, bg_alpha + 70)
                # 金色高亮邊框
                pygame.draw.rect(card, (255, 215, 0, bg_alpha), card.get_rect(), border_radius=6)
                pygame.draw.rect(card, base_color + (bg_alpha,), card.get_rect().inflate(-2, -2), border_radius=5)
            else:
                pygame.draw.rect(card, (22, 27, 34, bg_alpha), card.get_rect(), border_radius=6)
                pygame.draw.rect(card, base_color + (alpha_prob,), card.get_rect(), 1, border_radius=6)
                
            # 在卡片內部繪製發光文字
            draw_text_with_glow(card, word, font, (bg_w // 2, bg_h // 2), base_color, alpha_prob)
            
            # 疊加到主畫面
            surf.blit(card, (word_x - bg_w//2, word_y - bg_h//2))

            
            # 繪製指向頂端選取位置的箭頭或指標 (僅在目前焦點層)
            if is_focused:
                pygame.draw.polygon(surf, ACCENT_COLOR, [
                    (center_x - 6, center_y - radius - 15),
                    (center_x + 6, center_y - radius - 15),
                    (center_x, center_y - radius - 5)
                ])

# 繪製側邊控制面板
def draw_control_panel(surf, state):
    panel_rect = pygame.Rect(740, 100, 260, 360)
    draw_rounded_panel(surf, panel_rect, CARD_BG, 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    # 標題
    lbl = FONT_UI.render("⚙️ 預測客製化設定", True, ACCENT_COLOR)
    surf.blit(lbl, (760, 115))
    
    # 1. 顏色主題切換
    lbl_theme = FONT_UI.render("字圈主題色:", True, TEXT_COLOR)
    surf.blit(lbl_theme, (760, 150))
    
    y_offset = 180
    for key, data in THEMES.items():
        is_selected = (state.current_theme == key)
        color = ACCENT_COLOR if is_selected else BORDER_COLOR
        btn_rect = pygame.Rect(760, y_offset, 220, 28)
        
        # 繪製主題預覽色塊
        pygame.draw.rect(surf, color, btn_rect, 1, border_radius=4)
        pygame.draw.circle(surf, data["layer1"], (780, y_offset + 14), 6)
        pygame.draw.circle(surf, data["layer2"], (795, y_offset + 14), 6)
        pygame.draw.circle(surf, data["layer3"], (810, y_offset + 14), 6)
        
        txt = FONT_UI.render(data["name"], True, TEXT_COLOR)
        surf.blit(txt, (830, y_offset + 6))
        
        y_offset += 36

    # 2. 選擇 LLM 模型
    lbl_model = FONT_UI.render("選擇預測模型 (OpenRouter):", True, TEXT_COLOR)
    surf.blit(lbl_model, (760, 305))
    
    model_name = MODELS[state.selected_model_idx]["name"]
    model_rect = pygame.Rect(760, 330, 220, 32)
    pygame.draw.rect(surf, BORDER_COLOR, model_rect, 1, border_radius=6)
    
    txt_model = FONT_UI.render(model_name, True, TEXT_COLOR)
    surf.blit(txt_model, (772, 338))
    
    # 繪製下拉箭頭
    pygame.draw.polygon(surf, TEXT_COLOR, [
        (960, 342), (970, 342), (965, 350)
    ])
    
    # 3. 拖曳滑桿
    slider_alpha.draw(surf)

# 繪製底部連線與金鑰區
def draw_key_section(surf, state):
    panel_rect = pygame.Rect(50, 500, 650, 160)
    draw_rounded_panel(surf, panel_rect, CARD_BG, 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    lbl = FONT_UI.render("🔑 OpenRouter API 金鑰設定", True, ACCENT_COLOR)
    surf.blit(lbl, (70, 515))
    
    # 金鑰說明與狀態
    status_icon = "🟢" if state.connection_status == "connected" else "🔴" if state.connection_status == "error" else "🟡"
    status_txt = FONT_UI.render(f"連線狀態: {status_icon} {state.connection_message}", True, TEXT_COLOR)
    surf.blit(status_txt, (70, 542))
    
    # 繪製輸入框與按鈕
    api_input.draw(surf)
    btn_import.draw(surf)
    btn_test.draw(surf)
    
    # 金鑰獲取提示
    tip = FONT_SUBTITLE.render("若本地同目錄下存有 key.txt，啟動時會自動載入並連線測試。", True, (130, 140, 150))
    surf.blit(tip, (70, 642))

# 下拉模型選擇視窗渲染
is_model_dropdown_open = False
def draw_model_dropdown(surf, state):
    if not is_model_dropdown_open:
        return
    
    dropdown_rect = pygame.Rect(760, 362, 220, len(MODELS) * 32)
    pygame.draw.rect(surf, (22, 27, 34), dropdown_rect, border_radius=6)
    pygame.draw.rect(surf, ACCENT_COLOR, dropdown_rect, 1, border_radius=6)
    
    for idx, model in enumerate(MODELS):
        item_rect = pygame.Rect(760, 362 + idx * 32, 220, 32)
        is_hover = item_rect.collidepoint(pygame.mouse.get_pos())
        bg_color = (48, 54, 61) if is_hover else (22, 27, 34)
        
        pygame.draw.rect(surf, bg_color, item_rect, border_radius=4)
        txt = FONT_UI.render(model["name"], True, TEXT_COLOR)
        surf.blit(txt, (772, 362 + idx * 32 + 8))

# 處理滑鼠點擊下拉選單與側邊欄
def handle_mouse_clicks(pos, state):
    global is_model_dropdown_open
    
    # 1. 模型選單下拉展開點擊
    model_rect = pygame.Rect(760, 330, 220, 32)
    if model_rect.collidepoint(pos):
        is_model_dropdown_open = not is_model_dropdown_open
        return
        
    # 下拉清單內項目點擊
    if is_model_dropdown_open:
        for idx in range(len(MODELS)):
            item_rect = pygame.Rect(760, 362 + idx * 32, 220, 32)
            if item_rect.collidepoint(pos):
                state.selected_model_idx = idx
                is_model_dropdown_open = False
                state.request_predictions()
                return
        is_model_dropdown_open = False
        
    # 2. 顏色主題點擊
    y_offset = 180
    for key in THEMES.keys():
        btn_rect = pygame.Rect(760, y_offset, 220, 28)
        if btn_rect.collidepoint(pos):
            state.current_theme = key
            if sound_click:
                sound_click.play()
            return
        y_offset += 36

# 歷史紀錄，用於 Left 鍵退回上一次已選定的詞
history = []

def main_loop():
    global is_model_dropdown_open
    
    running = True
    while running:
        # 背景繪製
        screen.fill(BG_COLOR)
        
        # 繪製點網格裝飾 (Wow factor!)
        for x in range(0, WIDTH, 30):
            for y in range(0, HEIGHT, 30):
                pygame.gfxdraw.pixel(screen, x, y, (30, 38, 48))
                
        # 繪製頂部 Header
        title_surf = FONT_TITLE.render("🧠 OpenRouter AI 彩虹圓環預測輸入法", True, TEXT_COLOR)
        screen.blit(title_surf, (50, 35))
        subtitle_surf = FONT_SUBTITLE.render("適用於 PC 的多層同心圓環預測輸入介面原型 (Gemini 2.5 Flash)", True, ACCENT_COLOR)
        screen.blit(subtitle_surf, (52, 75))
        
        # 1. 繪製輸入區並取得游標位置
        cursor_x, cursor_y = draw_input_area(screen, state)
        
        # 2. 繪製彩虹同心圓環
        draw_rainbow_rings(screen, state, cursor_x, cursor_y)
        
        # 3. 繪製客製化控制面板
        draw_control_panel(screen, state)
        
        # 4. 繪製底部 API 金鑰區
        draw_key_section(screen, state)
        
        # 5. 繪製下拉模型選單 (在最上層)
        draw_model_dropdown(screen, state)
        
        # 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            # 處理滑桿與金鑰輸入事件
            slider_alpha.handle_event(event)
            state.global_alpha = slider_alpha.val
            api_input.handle_event(event, not api_input.active)
            btn_import.handle_event(event)
            btn_test.handle_event(event)
            
            # 滑鼠點擊 UI 事件
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_mouse_clicks(event.pos, state)
                
            # 鍵盤輸入事件 (當 API Key 輸入框未啟用時)
            if not api_input.active:
                if event.type == pygame.TEXTINPUT:
                    # Windows 原生輸入法完成拼音注音並按下 Enter 後，文字會由此事件送入
                    state.input_text += event.text
                    state.editing_text = ""
                    state.last_input_time = time.time()
                    state.debounce_triggered = False
                    
                elif event.type == pygame.TEXTEDITING:
                    # 使用者打拼音/注音暫存於此，用於下劃線提示
                    state.editing_text = event.text
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        # 只有當沒有拼音暫存時，退格鍵才刪除已送出字元
                        if not state.editing_text:
                            state.input_text = state.input_text[:-1]
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            
                    elif event.key == pygame.K_UP:
                        # 滾動當前圓環
                        state.rotate_layer(state.focus_layer, "up")
                        
                    elif event.key == pygame.K_DOWN:
                        # 滾動當前圓環
                        state.rotate_layer(state.focus_layer, "down")
                        
                    elif event.key == pygame.K_RIGHT:
                        # 選定字詞，寫入輸入框，播放鈴聲，焦點前進外圈
                        selected_word = state.get_selected_word(state.focus_layer)
                        if selected_word and selected_word != "...":
                            if sound_bell:
                                sound_bell.play()
                                
                            # 儲存歷史記錄，以供退格退回
                            history.append((state.focus_layer, len(selected_word)))
                            
                            state.input_text += selected_word
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            
                            if state.focus_layer < 2:
                                state.focus_layer += 1
                            else:
                                # 完成一輪，重設
                                state.focus_layer = 0
                                
                    elif event.key == pygame.K_LEFT:
                        # 退回上一層，並刪除上一次加入的詞彙
                        if history:
                            prev_layer, word_len = history.pop()
                            # 移除最後加上去的字數
                            if word_len > 0:
                                state.input_text = state.input_text[:-word_len]
                            state.focus_layer = prev_layer
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            if sound_click:
                                sound_click.play()
                        else:
                            # 無歷史紀錄時，若在 layer > 0 則單純退回內圈
                            if state.focus_layer > 0:
                                state.focus_layer -= 1
                                if sound_click:
                                    sound_click.play()

        # 更新動畫插值與計時器
        state.update()
        
        # 刷新畫面 (60 FPS)
        pygame.display.flip()
        clock.tick(60)

    # 關閉輸入法
    pygame.key.stop_text_input()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_loop()
