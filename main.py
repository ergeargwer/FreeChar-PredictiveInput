import pygame
import pygame.gfxdraw
import math
import sys
import os
import time

# 嘗試載入 api_client，若因編碼衝突可確保正常引入
try:
    from api_client import OpenRouterClient
except ImportError:
    class OpenRouterClient:
        def __init__(self):
            self.api_key = ''
            self.base_url = ''
        def set_api_key(self, key): pass

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
    sound_click.set_volume(0.4)
    sound_bell.set_volume(0.7)
except Exception as e:
    print(f"音效載入失敗: {e}")
    sound_click = None
    sound_bell = None

# 尋找中文字型
def get_font(size, bold=False):
    font_names = ['microsoftjhenghei', 'jhenghei', 'msgothic', 'simsun', 'dengxian', 'arial']
    for name in font_names:
        path = pygame.font.match_font(name)
        if path:
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

# 發光文字渲染函式
def draw_text_with_glow(surf, text, font, pos, color, alpha):
    glow_alpha = int(alpha * 0.35)
    if glow_alpha > 0:
        glow_color = color[:3] + (glow_alpha,)
        glow_surf = font.render(text, True, glow_color)
        glow_rect = glow_surf.get_rect(center=pos)
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            surf.blit(glow_surf, (glow_rect.x + dx, glow_rect.y + dy))
            
    main_color = (255, 255, 255)
    main_surf = font.render(text, True, main_color)
    main_surf.set_alpha(alpha)
    main_rect = main_surf.get_rect(center=pos)
    surf.blit(main_surf, main_rect)

# 顏色定義
BG_COLOR = (13, 17, 23)        # 深灰藍
CARD_BG = (22, 27, 34, 180)     # 半透明卡片背景
TEXT_COLOR = (240, 246, 252)    # 亮白
BORDER_COLOR = (48, 54, 61)     # 灰框
ACCENT_COLOR = (88, 166, 255)   # 藍色焦點

# 奢華彩虹同心圓漸層配色
THEMES = {
    "rainbow": {
        "name": "彩虹漸層",
        "layer1": {"start": (157, 0, 255), "end": (0, 255, 213)},   # 內圈：飽和紫青
        "layer2": {"start": (0, 85, 255), "end": (0, 255, 102)},     # 中圈：藍綠
        "layer3": {"start": (255, 128, 223), "end": (255, 224, 102)} # 外圈：淺粉金
    },
    "blue": {
        "name": "海洋藍色",
        "layer1": {"start": (0, 210, 255), "end": (0, 80, 255)},
        "layer2": {"start": (0, 150, 255), "end": (0, 50, 200)},
        "layer3": {"start": (100, 200, 255), "end": (0, 100, 255)}
    },
    "yellow": {
        "name": "黃金亮橙",
        "layer1": {"start": (255, 234, 0), "end": (213, 0, 0)},
        "layer2": {"start": (255, 145, 0), "end": (255, 60, 0)},
        "layer3": {"start": (255, 200, 100), "end": (200, 100, 0)}
    }
}

MODELS = [
    {"name": "Gemini 2.5 Flash", "id": "google/gemini-2.5-flash"},
    {"name": "DeepSeek V3", "id": "deepseek/deepseek-chat"},
    {"name": "Llama 3.1 8B (免費)", "id": "meta-llama/llama-3.1-8b-instruct:free"},
    {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"}
]

class AppState:
    def __init__(self):
        self.api_client = OpenRouterClient()
        self.input_text = "今天天氣"
        self.editing_text = ""
        
        self.current_theme = "rainbow"
        self.global_alpha = 0.9
        self.selected_model_idx = 0
        self.focus_layer = 0
        
        # 3 層圓環半徑
        self.radii = [60, 105, 150]
        self.layers = {
            0: {"target_angle": 270.0, "current_angle": 270.0, "words": []},
            1: {"target_angle": 270.0, "current_angle": 270.0, "words": []},
            2: {"target_angle": 270.0, "current_angle": 270.0, "words": []}
        }
        
        # 初始化 45 個微弱發光的極光粒子，圍繞著圓軌道環繞
        import random
        self.particles = []
        for _ in range(45):
            layer = random.choice([0, 1, 2])
            r = self.radii[layer] + random.randint(-8, 8)
            self.particles.append({
                "angle": random.uniform(0, 360),
                "dist": r,
                "layer": layer,
                "speed": random.uniform(0.15, 0.55),
                "size": random.uniform(1.2, 2.8),
                "pulse_speed": random.uniform(2.0, 5.0),
                "pulse_offset": random.uniform(0.0, math.pi * 2)
            })

        self.fill_default_predictions()
        
        self.connection_status = "idle"
        self.connection_message = "請點擊匯入或輸入 API Key"
        if self.api_client.api_key:
            self.connection_status = "testing"
            self.connection_message = "自動測試連線中..."
            self.test_api_connection(self.api_client.api_key)

        self.last_input_time = time.time()
        self.debounce_triggered = False
        
        pygame.key.start_text_input()
        self.request_predictions()

    def fill_default_predictions(self):
        # 每一層 4 個候選項，包含詞語與機率
        self.layers[0]["words"] = [
            {"word": "很好", "prob": 0.9},
            {"word": "不錯", "prob": 0.75},
            {"word": "一般", "prob": 0.5},
            {"word": "糟糕", "prob": 0.3}
        ]
        self.layers[1]["words"] = [
            {"word": "適合", "prob": 0.8},
            {"word": "出去", "prob": 0.65},
            {"word": "睡覺", "prob": 0.5},
            {"word": "打球", "prob": 0.3}
        ]
        self.layers[2]["words"] = [
            {"word": "散步", "prob": 0.8},
            {"word": "玩耍", "prob": 0.6},
            {"word": "旅遊", "prob": 0.4},
            {"word": "看書", "prob": 0.2}
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
                self.layers[0]["words"] = predictions.get("layer1", [])
                self.layers[1]["words"] = predictions.get("layer2", [])
                self.layers[2]["words"] = predictions.get("layer3", [])
                for i in range(3):
                    self.layers[i]["target_angle"] = 270.0
                    self.layers[i]["current_angle"] = 270.0
                self.focus_layer = 0
            elif error_msg:
                print(f"預測錯誤: {error_msg}")

        self.api_client.predict_async(full_text, model, callback)

    def update(self):
        for i in range(3):
            diff = self.layers[i]["target_angle"] - self.layers[i]["current_angle"]
            diff = (diff + 180) % 360 - 180
            
            if abs(diff) > 1.5:
                prev_angle = self.layers[i]["current_angle"]
                self.layers[i]["current_angle"] += diff * 0.16
                
                words_count = len(self.layers[i]["words"])
                step = 360.0 / words_count if words_count else 120.0
                if int(prev_angle / step) != int(self.layers[i]["current_angle"] / step):
                    if sound_click:
                        sound_click.play()
            else:
                self.layers[i]["current_angle"] = self.layers[i]["target_angle"]

        # 更新粒子軌道角度
        for p in self.particles:
            p["angle"] = (p["angle"] + p["speed"]) % 360

        if not self.debounce_triggered and (time.time() - self.last_input_time > 0.45):
            self.request_predictions()
            self.debounce_triggered = True

    def rotate_layer(self, layer_idx, direction):
        words_count = len(self.layers[layer_idx]["words"])
        step = 360.0 / words_count if words_count else 120.0
        if direction == "up":
            self.layers[layer_idx]["target_angle"] += step
        elif direction == "down":
            self.layers[layer_idx]["target_angle"] -= step

    def get_selected_word(self, layer_idx):
        layer = self.layers[layer_idx]
        words = layer["words"]
        if not words:
            return ""
            
        current_angle = layer["target_angle"] % 360
        words_count = len(words)
        step = 360.0 / words_count if words_count else 120.0
        best_idx = 0
        min_diff = 999.0
        for idx in range(words_count):
            init_angle = idx * step
            word_angle = (init_angle + layer["current_angle"]) % 360
            diff = abs((word_angle - 270 + 180) % 360 - 180)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        return words[best_idx]["word"] if best_idx < len(words) else ""

state = AppState()

class Slider:
    def __init__(self, x, y, w, h, label, min_val, max_val, current_val):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.val = current_val
        self.is_dragging = False

    def draw(self, surf):
        lbl_surf = FONT_UI.render(f"{self.label}: {int(self.val*100) if self.max_val <= 1.0 else int(self.val)}%", True, TEXT_COLOR)
        surf.blit(lbl_surf, (self.rect.x, self.rect.y - 20))
        
        pygame.draw.rect(surf, BORDER_COLOR, self.rect, border_radius=3)
        
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + int(ratio * self.rect.w)
        handle_rect = pygame.Rect(handle_x - 6, self.rect.y - 4, 12, self.rect.h + 8)
        
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

class InputBox:
    def __init__(self, x, y, w, h, text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.active = False

    def draw(self, surf):
        color = ACCENT_COLOR if self.active else BORDER_COLOR
        pygame.draw.rect(surf, color, self.rect, 2, border_radius=6)
        
        display_text = "*" * len(self.text) if self.text else "請在此點擊輸入 API Key..."
        color_text = TEXT_COLOR if self.text else (120, 120, 120)
        
        txt_surf = FONT_UI.render(display_text, True, color_text)
        surf.blit(txt_surf, (self.rect.x + 10, self.rect.y + (self.rect.h - txt_surf.get_height())//2))

    def handle_event(self, event, active_ime):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.active = self.rect.collidepoint(event.pos)
                if self.active:
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

slider_alpha = Slider(760, 480, 200, 8, "整體介面透明度", 0.2, 1.0, state.global_alpha)
api_input = InputBox(50, 600, 500, 36, state.api_client.api_key)

def import_key_file():
    state.api_client.load_key_from_file()
    if state.api_client.api_key:
        api_input.text = state.api_client.api_key
        state.test_api_connection(state.api_client.api_key)

def test_api():
    if api_input.text:
        state.test_api_connection(api_input.text)
        try:
            with open("key.txt", "w", encoding="utf-8") as f:
                f.write(f"openrouter\n{api_input.text}\n")
        except Exception as e:
            print(f"寫入 key.txt 失敗: {e}")

btn_import = Button(560, 600, 110, 36, "匯入 key.txt", import_key_file)
btn_test = Button(680, 600, 100, 36, "測試與儲存", test_api, color=(46, 125, 50))

def draw_rounded_panel(surf, rect, color, radius=10):
    shape_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(shape_surf, color, shape_surf.get_rect(), border_radius=radius)
    surf.blit(shape_surf, rect.topleft)

def draw_input_area(surf, state):
    panel_rect = pygame.Rect(50, 100, 500, 120)
    draw_rounded_panel(surf, panel_rect, (22, 27, 34, int(200 * state.global_alpha)), 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    lbl = FONT_UI.render("[IME] 鍵盤輸入區 (切換 Windows 中文輸入法直接打字)", True, ACCENT_COLOR)
    surf.blit(lbl, (65, 110))
    
    render_text = state.input_text
    edit_text = state.editing_text
    
    txt_surf = FONT_TEXT.render(render_text, True, TEXT_COLOR)
    surf.blit(txt_surf, (70, 150))
    
    x_offset = 70 + txt_surf.get_width()
    if edit_text:
        edit_surf = FONT_TEXT.render(edit_text, True, (136, 192, 250))
        surf.blit(edit_surf, (x_offset, 150))
        pygame.draw.line(surf, ACCENT_COLOR, (x_offset, 180), (x_offset + edit_surf.get_width(), 180), 2)
        x_offset += edit_surf.get_width()
        
    if int(time.time() * 2) % 2 == 0:
        pygame.draw.line(surf, ACCENT_COLOR, (x_offset + 2, 148), (x_offset + 2, 178), 2)
        
    hint_surf = FONT_SUBTITLE.render("方向鍵: 滾動選詞 | 右鍵 [→]: 選定字詞 | 左鍵 [←]: 回退字詞", True, (120, 130, 140))
    surf.blit(hint_surf, (70, 192))
    
    return x_offset, 150

# 繪製彩虹同心圓字圈
def draw_rainbow_rings(surf, state, cursor_x, cursor_y):
    center_x = min(800, max(680, cursor_x + 180))
    center_y = 220
    radii = state.radii
    theme = THEMES[state.current_theme]
    
    for layer_idx in range(2, -1, -1):
        radius = radii[layer_idx]
        layer_data = state.layers[layer_idx]
        words = layer_data["words"]
        
        layer_base_factor = [1.0, 0.75, 0.55][layer_idx]
        is_focused = (state.focus_layer == layer_idx)
        
        layer_color_data = theme[f"layer{layer_idx+1}"]
        start_c = layer_color_data["start"]
        end_c = layer_color_data["end"]
        base_color = start_c
        
        # 內中外主圓環厚度：12px, 9px, 6px
        main_width = [12, 9, 6][layer_idx]
        
        # 1. 繪製多層底圈（增加厚度感與極光霓虹效果）
        for k in range(5):
            glow_radius = radius + (k - 2) * 3
            glow_alpha = int((50 - k * 8) * layer_base_factor * state.global_alpha)
            glow_alpha = max(5, min(255, glow_alpha))
            glow_color = base_color + (glow_alpha,)
            
            glow_width = main_width if k == 2 else max(1, main_width - 4)
            if is_focused:
                glow_width += 2 if k == 2 else 1
                
            shape_surf = pygame.Surface((glow_radius * 2 + 10, glow_radius * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(shape_surf, glow_color, (glow_radius + 5, glow_radius + 5), glow_radius, glow_width)
            surf.blit(shape_surf, (center_x - glow_radius - 5, center_y - glow_radius - 5))
        
        # 2. 繪製玻璃反光與折射高光弧線 (在主圓環的正上方 60 到 120 度)
        high_alpha = int(140 * layer_base_factor * state.global_alpha)
        high_color = (255, 255, 255, high_alpha)
        high_surf = pygame.Surface((radius * 2 + 20, radius * 2 + 20), pygame.SRCALPHA)
        pygame.draw.arc(high_surf, high_color, (10, 10, radius*2, radius*2), math.radians(60), math.radians(120), max(1, main_width // 4))
        surf.blit(high_surf, (center_x - radius - 10, center_y - radius - 10))

        # 3. 繪製粒子環繞
        for p in state.particles:
            if p["layer"] == layer_idx:
                p_angle = math.radians(p["angle"])
                px = center_x + int(p["dist"] * math.cos(p_angle))
                py = center_y + int(p["dist"] * math.sin(p_angle))
                
                pulse = (math.sin(time.time() * p["pulse_speed"] + p["pulse_offset"]) + 1) / 2
                p_alpha = int(120 * pulse * state.global_alpha)
                p_color = base_color + (p_alpha,)
                
                p_surf = pygame.Surface((int(p["size"] * 4), int(p["size"] * 4)), pygame.SRCALPHA)
                pygame.draw.circle(p_surf, p_color, (int(p["size"]*2), int(p["size"]*2)), int(p["size"]))
                pygame.draw.circle(p_surf, base_color + (int(p_alpha * 0.3),), (int(p["size"]*2), int(p["size"]*2)), int(p["size"]*2), 1)
                surf.blit(p_surf, (px - int(p["size"]*2), py - int(p["size"]*2)))
        
        # 4. 繪製圓環上的預測字詞
        font = [FONT_RING_0, FONT_RING_1, FONT_RING_2][layer_idx]
        
        for idx in range(len(words)):
            item = words[idx]
            word = item["word"]
            prob = item["prob"]
            
            init_angle = idx * (360.0 / len(words)) if len(words) else 90.0
            total_angle = (init_angle + layer_data["current_angle"]) % 360
            rad = math.radians(total_angle)
            
            word_x = center_x + int(radius * math.cos(rad))
            word_y = center_y + int(radius * math.sin(rad))
            
            # 根據角度動態計算漸層顏色
            t_grad = total_angle / 360.0
            r_val = int(start_c[0] + (end_c[0] - start_c[0]) * t_grad)
            g_val = int(start_c[1] + (end_c[1] - start_c[1]) * t_grad)
            b_val = int(start_c[2] + (end_c[2] - start_c[2]) * t_grad)
            current_word_color = (r_val, g_val, b_val)
            
            alpha_prob = int(255 * prob * layer_base_factor * state.global_alpha)
            alpha_prob = max(35, min(255, alpha_prob))
            
            angle_diff = abs((total_angle - 270 + 180) % 360 - 180)
            is_pointing = (angle_diff < 15.0) and is_focused
            
            word_w, word_h = font.size(word)
            pad_w, pad_h = 16, 10
            bg_w = word_w + pad_w
            bg_h = word_h + pad_h
            
            card = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
            bg_alpha = int(140 * prob * state.global_alpha)
            
            if is_pointing:
                bg_alpha = min(255, bg_alpha + 70)
                pygame.draw.rect(card, (255, 215, 0, bg_alpha), card.get_rect(), border_radius=6)
                pygame.draw.rect(card, current_word_color + (bg_alpha,), card.get_rect().inflate(-2, -2), border_radius=5)
            else:
                pygame.draw.rect(card, (22, 27, 34, bg_alpha), card.get_rect(), border_radius=6)
                pygame.draw.rect(card, current_word_color + (alpha_prob,), card.get_rect(), 2, border_radius=6)
                
            draw_text_with_glow(card, word, font, (bg_w // 2, bg_h // 2), current_word_color, alpha_prob)
            surf.blit(card, (word_x - bg_w//2, word_y - bg_h//2))
            
            if is_focused:
                pygame.draw.polygon(surf, ACCENT_COLOR, [
                    (center_x - 6, center_y - radius - 15),
                    (center_x + 6, center_y - radius - 15),
                    (center_x, center_y - radius - 5)
                ])

def draw_control_panel(surf, state):
    panel_rect = pygame.Rect(740, 100, 260, 360)
    draw_rounded_panel(surf, panel_rect, CARD_BG, 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    lbl = FONT_UI.render("[Setting] 預測客製化設定", True, ACCENT_COLOR)
    surf.blit(lbl, (760, 115))
    
    lbl_theme = FONT_UI.render("字圈主題色:", True, TEXT_COLOR)
    surf.blit(lbl_theme, (760, 150))
    
    y_offset = 180
    for key, data in THEMES.items():
        is_selected = (state.current_theme == key)
        color = ACCENT_COLOR if is_selected else BORDER_COLOR
        btn_rect = pygame.Rect(760, y_offset, 220, 28)
        
        pygame.draw.rect(surf, color, btn_rect, 1, border_radius=4)
        pygame.draw.circle(surf, data["layer1"]["start"], (780, y_offset + 14), 6)
        pygame.draw.circle(surf, data["layer2"]["start"], (795, y_offset + 14), 6)
        pygame.draw.circle(surf, data["layer3"]["start"], (810, y_offset + 14), 6)
        
        txt = FONT_UI.render(data["name"], True, TEXT_COLOR)
        surf.blit(txt, (830, y_offset + 6))
        
        y_offset += 36

    lbl_model = FONT_UI.render("選擇預測模型 (OpenRouter):", True, TEXT_COLOR)
    surf.blit(lbl_model, (760, 305))
    
    model_name = MODELS[state.selected_model_idx]["name"]
    model_rect = pygame.Rect(760, 330, 220, 32)
    pygame.draw.rect(surf, BORDER_COLOR, model_rect, 1, border_radius=6)
    
    txt_model = FONT_UI.render(model_name, True, TEXT_COLOR)
    surf.blit(txt_model, (772, 338))
    
    pygame.draw.polygon(surf, TEXT_COLOR, [
        (960, 342), (970, 342), (965, 350)
    ])
    
    slider_alpha.draw(surf)

def draw_key_section(surf, state):
    panel_rect = pygame.Rect(50, 500, 650, 160)
    draw_rounded_panel(surf, panel_rect, CARD_BG, 10)
    pygame.draw.rect(surf, BORDER_COLOR, panel_rect, 1, border_radius=10)
    
    lbl = FONT_UI.render("[Key] OpenRouter API 金鑰設定", True, ACCENT_COLOR)
    surf.blit(lbl, (70, 515))
    
    status_icon = "[Connected]" if state.connection_status == "connected" else "[Error]" if state.connection_status == "error" else "[Testing]"
    status_txt = FONT_UI.render(f"連線狀態: {status_icon} {state.connection_message}", True, TEXT_COLOR)
    surf.blit(status_txt, (70, 542))
    
    api_input.draw(surf)
    btn_import.draw(surf)
    btn_test.draw(surf)
    
    tip = FONT_SUBTITLE.render("若本地同目錄下存有 key.txt，啟動時會自動載入並連線測試。", True, (130, 140, 150))
    surf.blit(tip, (70, 642))

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

def handle_mouse_clicks(pos, state):
    global is_model_dropdown_open
    
    model_rect = pygame.Rect(760, 330, 220, 32)
    if model_rect.collidepoint(pos):
        is_model_dropdown_open = not is_model_dropdown_open
        return
        
    if is_model_dropdown_open:
        for idx in range(len(MODELS)):
            item_rect = pygame.Rect(760, 362 + idx * 32, 220, 32)
            if item_rect.collidepoint(pos):
                state.selected_model_idx = idx
                is_model_dropdown_open = False
                state.request_predictions()
                return
        is_model_dropdown_open = False
        
    y_offset = 180
    for key in THEMES.keys():
        btn_rect = pygame.Rect(760, y_offset, 220, 28)
        if btn_rect.collidepoint(pos):
            state.current_theme = key
            if sound_click:
                sound_click.play()
            return
        y_offset += 36

history = []

def main_loop():
    global is_model_dropdown_open
    
    running = True
    while running:
        screen.fill(BG_COLOR)
        
        for x in range(0, WIDTH, 30):
            for y in range(0, HEIGHT, 30):
                pygame.gfxdraw.pixel(screen, x, y, (30, 38, 48))
                
        title_surf = FONT_TITLE.render("[*] OpenRouter AI 彩虹圓環預測輸入法", True, TEXT_COLOR)
        screen.blit(title_surf, (50, 35))
        subtitle_surf = FONT_SUBTITLE.render("適用於 PC 的多層同心圓環預測輸入介面原型 (Gemini 2.5 Flash)", True, ACCENT_COLOR)
        screen.blit(subtitle_surf, (52, 75))
        
        cursor_x, cursor_y = draw_input_area(screen, state)
        
        draw_rainbow_rings(screen, state, cursor_x, cursor_y)
        
        draw_control_panel(screen, state)
        
        draw_key_section(screen, state)
        
        draw_model_dropdown(screen, state)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            slider_alpha.handle_event(event)
            state.global_alpha = slider_alpha.val
            api_input.handle_event(event, not api_input.active)
            btn_import.handle_event(event)
            btn_test.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_mouse_clicks(event.pos, state)
                
            if not api_input.active:
                if event.type == pygame.TEXTINPUT:
                    state.input_text += event.text
                    state.editing_text = ""
                    state.last_input_time = time.time()
                    state.debounce_triggered = False
                    
                elif event.type == pygame.TEXTEDITING:
                    state.editing_text = event.text
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        if not state.editing_text:
                            state.input_text = state.input_text[:-1]
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            
                    elif event.key == pygame.K_UP:
                        state.rotate_layer(state.focus_layer, "up")
                        
                    elif event.key == pygame.K_DOWN:
                        state.rotate_layer(state.focus_layer, "down")
                        
                    elif event.key == pygame.K_RIGHT:
                        selected_word = state.get_selected_word(state.focus_layer)
                        if selected_word and selected_word != "...":
                            if sound_bell:
                                sound_bell.play()
                                
                            history.append((state.focus_layer, len(selected_word)))
                            state.input_text += selected_word
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            
                            if state.focus_layer < 2:
                                state.focus_layer += 1
                            else:
                                state.focus_layer = 0
                                
                    elif event.key == pygame.K_LEFT:
                        if history:
                            prev_layer, word_len = history.pop()
                            if word_len > 0:
                                state.input_text = state.input_text[:-word_len]
                            state.focus_layer = prev_layer
                            state.last_input_time = time.time()
                            state.debounce_triggered = False
                            if sound_click:
                                sound_click.play()
                        else:
                            if state.focus_layer > 0:
                                state.focus_layer -= 1
                                if sound_click:
                                    sound_click.play()

        state.update()
        pygame.display.flip()
        clock.tick(60)

    pygame.key.stop_text_input()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_loop()
