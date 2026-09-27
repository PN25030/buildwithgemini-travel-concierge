import math
import os
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio
import imageio_ffmpeg
from scipy.io import wavfile

# 1. Generate Upbeat Lo-Fi Background Music
def create_lofi_music(filename="lofi_bg_music.wav", duration=18.0, sample_rate=44100):
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    bpm = 85
    beat_sec = 60.0 / bpm
    measure_sec = beat_sec * 4

    # Upbeat lo-fi chord progression (Cmaj7 -> Am7 -> Fmaj7 -> G7)
    chords = [
        [261.63, 329.63, 392.00, 493.88],  # Cmaj7
        [220.00, 261.63, 329.63, 392.00],  # Am7
        [174.61, 220.00, 261.63, 329.63],  # Fmaj7
        [196.00, 246.94, 293.66, 349.23],  # G7
    ]

    audio = np.zeros(num_samples)

    # Chords
    for i in range(int(duration / measure_sec) + 1):
        chord = chords[i % len(chords)]
        start_idx = int(i * measure_sec * sample_rate)
        end_idx = min(int((i + 1) * measure_sec * sample_rate), num_samples)
        if start_idx >= num_samples:
            break
        t_chunk = t[start_idx:end_idx] - (i * measure_sec)
        env = np.sin(np.pi * np.clip(t_chunk / measure_sec, 0, 1)) ** 0.5
        for freq in chord:
            note = 0.14 * np.sin(2 * np.pi * freq * t_chunk) + 0.04 * np.sin(2 * np.pi * freq * 2 * t_chunk)
            audio[start_idx:end_idx] += note * env

    # Upbeat Drum pattern
    num_beats = int(duration / beat_sec)
    for b in range(num_beats):
        b_time = b * beat_sec
        b_idx = int(b_time * sample_rate)

        # Kick on beats 0 & 2.5
        if b % 4 in [0, 2]:
            k_len = int(0.12 * sample_rate)
            if b_idx + k_len < num_samples:
                t_k = np.linspace(0, 0.12, k_len)
                kick_val = 0.35 * np.sin(2 * np.pi * (120 * np.exp(-30 * t_k)) * t_k) * np.exp(-15 * t_k)
                audio[b_idx:b_idx+k_len] += kick_val

        # Snare on beats 1 & 3
        if b % 4 in [1, 3]:
            s_len = int(0.1 * sample_rate)
            if b_idx + s_len < num_samples:
                t_s = np.linspace(0, 0.1, s_len)
                snare_noise = (np.random.rand(s_len) * 2 - 1) * np.exp(-25 * t_s)
                snare_tone = 0.18 * np.sin(2 * np.pi * 180 * t_s) * np.exp(-20 * t_s)
                audio[b_idx:b_idx+s_len] += 0.22 * (snare_noise + snare_tone)

        # Hi-hat eighth notes
        for h in [0, 0.5]:
            h_idx = int((b_time + h * beat_sec) * sample_rate)
            h_len = int(0.04 * sample_rate)
            if h_idx + h_len < num_samples:
                t_h = np.linspace(0, 0.04, h_len)
                audio[h_idx:h_idx+h_len] += 0.07 * (np.random.rand(h_len) * 2 - 1) * np.exp(-60 * t_h)

    # Fade out last 1.5 seconds
    fade_len = int(1.5 * sample_rate)
    fade_env = np.ones(num_samples)
    fade_env[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    audio *= fade_env

    # Vinyl noise
    audio += (np.random.rand(num_samples) * 2 - 1) * 0.005
    audio = audio / (np.max(np.abs(audio)) + 1e-5) * 0.8
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(filename, sample_rate, audio_int16)
    return filename


# 2. Create Sample Postcard Image
def create_kyoto_postcard():
    w, h = 420, 220
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Sunset gradient background
    for y in range(h):
        r = int(255 - y * 0.3)
        g = int(150 + y * 0.3)
        b = int(180 + y * 0.2)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Sun
    draw.ellipse([280, 40, 360, 120], fill=(255, 240, 200))

    # Silhouette Pagoda
    # Main tower
    draw.rectangle([160, 90, 200, 190], fill=(40, 30, 45))
    # Roofs
    roofs = [(140, 170, 220, 180), (145, 145, 215, 155), (150, 120, 210, 130), (155, 95, 205, 105)]
    for r in roofs:
        draw.rectangle(r, fill=(30, 20, 35))
    # Spire
    draw.line([(180, 60), (180, 95)], fill=(30, 20, 35), width=3)

    # Cherry blossoms on left
    draw.ellipse([20, 30, 80, 90], fill=(255, 192, 203))
    draw.ellipse([60, 50, 110, 100], fill=(255, 182, 193))

    # Text banner
    try:
        font_card = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
        font_sub = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    except Exception:
        font_card = font_sub = ImageFont.load_default()

    draw.rectangle([0, h-45, w, h], fill=(15, 23, 42, 220))
    draw.text((15, h-38), "KYOTO, JAPAN", fill=(255, 255, 255), font=font_card)
    draw.text((15, h-18), "Historic Temples & Cherry Blossoms", fill=(203, 213, 225), font=font_sub)
    return img


# 3. Main Frame Generator
def render_demo_video():
    music_file = create_lofi_music("lofi_bg_music.wav", duration=18.0)
    postcard_img = create_kyoto_postcard()

    width, height = 1280, 720
    fps = 30
    duration = 18.0
    total_frames = int(fps * duration)

    try:
        font_title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
        font_header = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
        font_text = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
        font_bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
        font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    except Exception:
        font_title = font_header = font_text = font_bold = font_small = ImageFont.load_default()

    prompt1_full = "What are the top attractions and current live weather in Kyoto?"
    prompt2_full = "Search Firestore for destinations under $150/day and generate a travel postcard of Kyoto!"

    temp_video = "temp_raw_video.mp4"
    writer = imageio.get_writer(temp_video, fps=fps, codec="libx264", quality=8)

    print("Rendering video frames...")

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        img = Image.new("RGB", (width, height), (248, 250, 252))
        draw = ImageDraw.Draw(img)

        # Header bar
        for y in range(65):
            r = int(15 + (2 - 15) * (y / 65))
            g = int(118 + (132 - 118) * (y / 65))
            b = int(110 + (199 - 110) * (y / 65))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Brand Icon & Title
        draw.rectangle([25, 14, 63, 52], fill=(255, 255, 255, 50), outline=(255, 255, 255), width=1)
        draw.text((35, 20), "✈", fill=(255, 255, 255), font=font_title)
        draw.text((75, 18), "Travel Concierge AI", fill=(255, 255, 255), font=font_header)
        draw.text((75, 42), "Personalized AI Travel Planner & Guide", fill=(226, 232, 240), font=font_small)

        # Status badge
        draw.rectangle([width - 130, 20, width - 25, 46], fill=(255, 255, 255, 40))
        draw.ellipse([width - 120, 29, width - 110, 39], fill=(34, 197, 94))
        draw.text((width - 104, 25), "Online", fill=(255, 255, 255), font=font_small)

        # Container backdrop
        draw.rectangle([180, 85, width - 180, height - 90], fill=(255, 255, 255), outline=(226, 232, 240), width=1)

        # --- Timeline Logic ---

        # 0.0s - 1.5s: Initial Zero State Welcome Card
        if t < 1.5:
            draw.text((width // 2 - 140, 280), "Where to next?", fill=(15, 23, 42), font=font_title)
            draw.text((width // 2 - 240, 320), "Ask Travel Concierge for live weather, trip itineraries, and resort postcards.", fill=(100, 116, 139), font=font_text)

        # 1.5s - 8.5s: Prompt 1 & Response 1
        if t >= 1.5:
            # Type Prompt 1 (1.5s to 3.5s)
            p1_len = int(min(1.0, (t - 1.5) / 2.0) * len(prompt1_full))
            p1_typed = prompt1_full[:p1_len]

            # Draw User Bubble 1
            draw.rectangle([width - 620, 110, width - 210, 160], fill=(13, 148, 136))
            draw.text((width - 605, 123), p1_typed, fill=(255, 255, 255), font=font_bold)

            # Thinking state (3.5s to 4.5s)
            if 3.5 <= t < 4.5:
                draw.rectangle([210, 180, 520, 220], fill=(241, 245, 249), outline=(226, 232, 240))
                draw.text((225, 192), "✈ Fetching live weather & attractions...", fill=(15, 118, 110), font=font_text)

            # Response Bubble 1 (4.5s onwards)
            if t >= 4.5:
                draw.rectangle([210, 180, 680, 310], fill=(255, 255, 255), outline=(226, 232, 240))
                draw.text((230, 195), "📍 Kyoto, Japan", fill=(15, 118, 110), font=font_bold)
                draw.text((230, 225), "• Live Weather: 21.5°C (70.7°F) ☀️ Clear Sky", fill=(15, 23, 42), font=font_text)
                draw.text((230, 255), "• Top Landmarks: Kiyomizu-dera Temple,", fill=(15, 23, 42), font=font_text)
                draw.text((245, 280), "Fushimi Inari Shrine, Arashiyama Bamboo Grove.", fill=(15, 23, 42), font=font_text)

        # 8.5s - 18.0s: Prompt 2 & Rich A2UI Response with Image
        if t >= 8.5:
            # Type Prompt 2 (8.5s to 10.5s)
            p2_len = int(min(1.0, (t - 8.5) / 2.0) * len(prompt2_full))
            p2_typed = prompt2_full[:p2_len]

            # Draw User Bubble 2
            draw.rectangle([width - 650, 335, width - 210, 385], fill=(13, 148, 136))
            draw.text((width - 635, 348), p2_typed, fill=(255, 255, 255), font=font_bold)

            # Thinking state 2 (10.5s to 11.5s)
            if 10.5 <= t < 11.5:
                draw.rectangle([210, 400, 560, 440], fill=(241, 245, 249), outline=(226, 232, 240))
                draw.text((225, 412), "⚡ Querying Firestore & rendering card...", fill=(15, 118, 110), font=font_text)

            # Rich Response 2 (11.5s onwards)
            if t >= 11.5:
                # A2UI Card Container
                draw.rectangle([210, 400, 710, 615], fill=(255, 255, 255), outline=(13, 148, 136), width=2)
                draw.text((225, 412), "🗂️ Firestore Search Result ($120/day)", fill=(15, 118, 110), font=font_bold)
                
                # Paste Postcard Image
                img.paste(postcard_img, (225, 440))

        # Bottom Form Bar
        draw.rectangle([180, height - 85, width - 180, height - 25], fill=(255, 255, 255), outline=(226, 232, 240))
        draw.rectangle([195, height - 72, width - 330, height - 38], fill=(248, 250, 252), outline=(226, 232, 240))
        draw.text((210, height - 60), "Ask Travel Concierge anything...", fill=(148, 163, 184), font=font_text)
        draw.rectangle([width - 315, height - 72, width - 195, height - 38], fill=(13, 148, 136))
        draw.text((width - 280, height - 60), "Send ➤", fill=(255, 255, 255), font=font_bold)

        # Convert to numpy array & write frame
        frame_np = np.array(img)
        writer.append_data(frame_np)

    writer.close()
    print("Video frame rendering complete!")

    # 4. Merge Video with Lo-Fi Music using FFmpeg
    final_output = "agent_demo.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", temp_video,
        "-i", music_file,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        final_output,
    ]
    print("Merging video with upbeat lo-fi audio track...")
    subprocess.run(cmd, check=True)
    if os.path.exists(temp_video):
        os.remove(temp_video)
    print(f"Successfully generated demo video: {final_output}")
    return final_output

if __name__ == "__main__":
    render_demo_video()
