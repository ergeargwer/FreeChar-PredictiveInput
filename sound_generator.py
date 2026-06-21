import math
import struct
import wave
import random

def generate_wav(filename, duration, sample_rate, wave_func):
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as w:
        w.setnchannels(1)  # 殘道：單聲道
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = i / sample_rate
            value = wave_func(t, duration)
            value = max(-1.0, min(1.0, value))
            sample = int(value * 32767)
            w.writeframes(struct.pack('<h', sample))

def gear_click_func(t, duration):
    # 齒輪卡嗒聲：600Hz 衰減正弦波加微量白雜訊
    freq = 600
    decay = math.exp(-t * 120)  # 極快衰減，營造短促的卡嗒感
    noise = (random.random() - 0.5) * 0.15
    return (math.sin(2 * math.pi * freq * t) + noise) * decay * 0.5

def bell_ring_func(t, duration):
    # 響鈴聲：多重高頻正弦波疊加，中速指數衰減
    f1 = 1200
    f2 = 1750
    f3 = 2200
    decay = math.exp(-t * 8)  # 中等衰減
    val = (
        0.5 * math.sin(2 * math.pi * f1 * t) +
        0.3 * math.sin(2 * math.pi * f2 * t) +
        0.2 * math.sin(2 * math.pi * f3 * t)
    )
    return val * decay * 0.6

def generate_sounds():
    sample_rate = 44100
    generate_wav('gear_click.wav', 0.05, sample_rate, gear_click_func)
    generate_wav('bell_ring.wav', 0.5, sample_rate, bell_ring_func)
    print("音效檔案 (gear_click.wav, bell_ring.wav) 生成成功。")

if __name__ == '__main__':
    generate_sounds()
