import os
import time
import librosa
import numpy as np
import soundfile as sf
from pathlib import Path
from elevenlabs.client import ElevenLabs

def dub_audio_segment(source_file_name, start_time, end_time, target_lang="fr"):
    """Splits a segment of audio and dubs it using ElevenLabs."""
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "output"

    source_file = OUTPUT_DIR / source_file_name
    temp_split_file = OUTPUT_DIR / f"temp_split_{start_time}_{end_time}.wav"
    output_filename = OUTPUT_DIR / f"dubbed_{start_time}s_to_{end_time}s_{target_lang}.mp3"

    if output_filename.exists():
        print(f"\n✅ Dubbed file already exists: {output_filename.name}")
        return output_filename

    if not source_file.exists():
        print(f"Error: {source_file} not found.")
        return None

    client = ElevenLabs(api_key="7b81876c3068cb5ebce42c38ef0bb6ce4fd3574217f9f839faf649e4838f3a4d")

    print(f"Splitting {source_file.name} from {start_time}s to {end_time}s...")
    audio, sr = librosa.load(str(source_file), sr=16000, mono=True)
    start_sample = int(start_time * sr)
    end_sample = int(end_time * sr)
    audio_segment = audio[start_sample:end_sample]
    sf.write(str(temp_split_file), audio_segment, sr)

    print(f"Starting dubbing for the split segment...")
    try:
        with open(temp_split_file, "rb") as audio_file:
            response = client.dubbing.create(
                file=(audio_file.name, audio_file, "audio/wav"),
                target_lang=target_lang,
                source_lang="en",
                num_speakers=1,
                watermark=True
            )
        
        dubbing_id = response.dubbing_id
        while True:
            metadata = client.dubbing.get(dubbing_id)
            if metadata.status in ["dubbed", "finished"]:
                break
            time.sleep(5)

        try:
            dubbed_audio_generator = client.dubbing.audio.get(dubbing_id, target_lang)
        except (AttributeError, TypeError):
            dubbed_audio_generator = client.dubbing.get_audio(dubbing_id, target_lang)

        with open(output_filename, "wb") as f:
            for chunk in dubbed_audio_generator:
                f.write(chunk)
    finally:
        print(f"Temporary segment preserved at: {temp_split_file}")

    return output_filename

def merge_5s_clip(music_file_name, dubbed_file_path, start_time, duration=5.0):
    """Creates a 5-second merged clip of music and vocals."""
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "output"
    
    music_path = OUTPUT_DIR / music_file_name
    final_output_path = OUTPUT_DIR / f"merged_clip_{start_time}s_to_{start_time + duration}s.wav"

    print(f"\n--- Creating 5-Second Merge ---")
    
    # 1. Load ONLY the 5s segment of the background music
    # offset=start_time tells it where to begin, duration=5.0 tells it where to end
    music_segment, sr = librosa.load(str(music_path), sr=44100, offset=start_time, duration=duration)
    
    # 2. Load the dubbed vocals at the same sample rate
    vocals, _ = librosa.load(str(dubbed_file_path), sr=sr)

    # 3. Ensure arrays are the exact same length (Librosa can vary by a few samples)
    min_len = min(len(music_segment), len(vocals))
    music_segment = music_segment[:min_len]
    vocals = vocals[:min_len]

    # 4. Mix: Add them together
    # Music at 70% volume, Vocals at 100% to ensure they are heard over the beat
    mixed = (music_segment * 0.7) + vocals

    # 5. Normalize to prevent distortion
    max_val = np.max(np.abs(mixed))
    if max_val > 1.0:
        mixed = mixed / max_val

    # 6. Export the short clip
    sf.write(str(final_output_path), mixed, sr)
    print(f"Successfully created 5s clip: {final_output_path}")
    return final_output_path

if __name__ == "__main__":
    VOCAL_FILE = "lights_vocals.wav"
    MUSIC_FILE = "lights_music.wav"
    START = 94.0
    END = 99.0
    DURATION = END - START
    
    # Step 1: Dub the segment
    dubbed_path = dub_audio_segment(VOCAL_FILE, START, END, "fr")
    
    # Step 2: Merge only that 5s window
    if dubbed_path:
        clip_path = merge_5s_clip(MUSIC_FILE, dubbed_path, START, DURATION)
        print(f"\nYour 5-second French mix is ready at: {clip_path}")