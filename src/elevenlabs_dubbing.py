import os
import time
import librosa
import numpy as np
import soundfile as sf
import re
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

def create_preview(vocals_file_path, music_file_path, lyrics_file_path, target_lang="fr", output_dir=None, duration=10.0):
    """
    Creates a 10-second preview of translated lyrics over background music.
    
    Args:
        vocals_file_path: Path to the vocals audio file (WAV)
        music_file_path: Path to the background music file (WAV)
        lyrics_file_path: Path to the lyrics file with timestamps
        target_lang: Target language code (default: "fr")
        output_dir: Output directory (default: database directory)
        duration: Preview duration in seconds (default: 10.0)
    
    Returns:
        str: Path to the preview audio file, or None if failed
    """
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    
    if output_dir is None:
        output_dir = PROJECT_ROOT / "database"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    # Parse lyrics to find first timestamp
    import re
    pattern_full = r'\[(\d+\.?\d*)s → (\d+\.?\d*)s\] (.+)'
    pattern_start_only = r'\[(\d+\.?\d*)s\] (.+)'
    
    first_timestamp = None
    with open(lyrics_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Try full format [start → end] text
            match_full = re.match(pattern_full, line)
            if match_full:
                first_timestamp = float(match_full.group(1))
                break
            
            # Try start-only format [start] text
            match_start = re.match(pattern_start_only, line)
            if match_start:
                first_timestamp = float(match_start.group(1))
                break
    
    if first_timestamp is None:
        print("Warning: Could not find first timestamp in lyrics file. Using 0.0")
        first_timestamp = 0.0
    
    # Calculate start and end times
    start_time = first_timestamp
    end_time = start_time + duration
    
    print(f"\n=== Creating Preview ===")
    print(f"First lyric timestamp: {first_timestamp}s")
    print(f"Preview range: {start_time}s to {end_time}s")
    
    # Step 1: Dub the vocals segment
    vocals_path = Path(vocals_file_path)
    if not vocals_path.exists():
        print(f"Error: Vocals file not found: {vocals_path}")
        return None
    
    # Create temporary vocals segment
    temp_vocals_segment = output_dir / f"temp_preview_vocals_{start_time}_{end_time}.wav"
    audio, sr = librosa.load(str(vocals_path), sr=16000, mono=True)
    start_sample = int(start_time * sr)
    end_sample = int(end_time * sr)
    audio_segment = audio[start_sample:end_sample]
    sf.write(str(temp_vocals_segment), audio_segment, sr)
    
    # Dub using ElevenLabs
    client = ElevenLabs(api_key="7b81876c3068cb5ebce42c38ef0bb6ce4fd3574217f9f839faf649e4838f3a4d")
    
    print(f"Dubbing vocals segment...")
    try:
        with open(temp_vocals_segment, "rb") as audio_file:
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
        
        dubbed_file = output_dir / f"temp_dubbed_preview_{start_time}_{end_time}.mp3"
        with open(dubbed_file, "wb") as f:
            for chunk in dubbed_audio_generator:
                f.write(chunk)
    except Exception as e:
        print(f"Error during dubbing: {e}")
        return None
    finally:
        # Clean up temp vocals segment
        if temp_vocals_segment.exists():
            try:
                temp_vocals_segment.unlink()
            except:
                pass
    
    # Step 2: Merge with background music
    music_path = Path(music_file_path)
    if not music_path.exists():
        print(f"Error: Music file not found: {music_path}")
        return None
    
    # Load music segment
    music_segment, sr = librosa.load(str(music_path), sr=44100, offset=start_time, duration=duration)
    
    # Load dubbed vocals at same sample rate
    vocals, _ = librosa.load(str(dubbed_file), sr=sr)
    
    # Ensure arrays are same length
    min_len = min(len(music_segment), len(vocals))
    music_segment = music_segment[:min_len]
    vocals = vocals[:min_len]
    
    # Mix: Music at 70%, Vocals at 100%
    mixed = (music_segment * 0.7) + vocals
    
    # Normalize
    max_val = np.max(np.abs(mixed))
    if max_val > 1.0:
        mixed = mixed / max_val
    
    # Save preview as WAV (sf.write doesn't support MP3 directly)
    preview_filename = f"preview_{start_time}s_to_{end_time}s_{target_lang}.wav"
    preview_path = output_dir / preview_filename
    sf.write(str(preview_path), mixed, sr)
    
    # Clean up temp dubbed file
    if dubbed_file.exists():
        try:
            dubbed_file.unlink()
        except:
            pass
    
    print(f"Preview created: {preview_path}")
    return str(preview_path)

def dub_and_transcribe_full_vocals(vocals_file_path, target_lang="fr", output_dir=None, lyrics_file_with_timestamps=None, song_name=None):
    """
    Dubs the full vocals track using ElevenLabs and transcribes the dubbed audio
    to get translated lyrics with timestamps for video display.
    
    Args:
        vocals_file_path: Path to the vocals audio file (WAV)
        target_lang: Target language code (default: "fr")
        output_dir: Output directory (default: database directory)
        lyrics_file_with_timestamps: Optional original lyrics file to preserve timestamps
        song_name: Optional song name for filename
    
    Returns:
        str: Path to the translated lyrics file with timestamps, or None if failed
    """
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    
    if output_dir is None:
        output_dir = PROJECT_ROOT / "database"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    vocals_path = Path(vocals_file_path)
    if not vocals_path.exists():
        print(f"Error: Vocals file not found: {vocals_path}")
        return None
    
    print(f"\n=== Dubbing Full Vocals with ElevenLabs ===")
    print(f"Dubbing {vocals_path.name} to {target_lang}...")
    
    # Step 1: Dub the full vocals using ElevenLabs
    client = ElevenLabs(api_key="7b81876c3068cb5ebce42c38ef0bb6ce4fd3574217f9f839faf649e4838f3a4d")
    
    try:
        with open(vocals_path, "rb") as audio_file:
            response = client.dubbing.create(
                file=(audio_file.name, audio_file, "audio/wav"),
                target_lang=target_lang,
                source_lang="en",
                num_speakers=1,
                watermark=True
            )
        
        dubbing_id = response.dubbing_id
        print(f"Dubbing ID: {dubbing_id}")
        print("Waiting for dubbing to complete...")
        
        while True:
            metadata = client.dubbing.get(dubbing_id)
            if metadata.status in ["dubbed", "finished"]:
                break
            print(f"Status: {metadata.status}, waiting...")
            time.sleep(5)
        
        print("Dubbing complete! Downloading dubbed audio...")
        
        try:
            dubbed_audio_generator = client.dubbing.audio.get(dubbing_id, target_lang)
        except (AttributeError, TypeError):
            dubbed_audio_generator = client.dubbing.get_audio(dubbing_id, target_lang)
        
        dubbed_file = output_dir / f"temp_full_dubbed_{target_lang}.mp3"
        with open(dubbed_file, "wb") as f:
            for chunk in dubbed_audio_generator:
                f.write(chunk)
        
        print(f"Dubbed audio saved: {dubbed_file}")
        
    except Exception as e:
        print(f"Error during dubbing: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Step 2: Transcribe the dubbed audio using ElevenLabs Scribe
    print(f"\n=== Transcribing Dubbed Audio ===")
    print(f"Transcribing {dubbed_file.name} to get translated lyrics...")
    
    try:
        # Use ElevenLabs Scribe to transcribe the dubbed audio
        with open(dubbed_file, "rb") as audio_input:
            transcription = client.speech_to_text.convert(
                file=audio_input,
                model_id="scribe_v1",
            )
        
        # Process transcription to create lyrics with timestamps
        ignore_list = {'oh', 'um', 'uh', 'er', 'ah', 'hmm', 'yeah', 'mhm'}
        
        sentences = []
        current_sentence_words = []
        start_time = None
        
        for word_data in transcription.words:
            # Remove parentheses content like (music)
            raw_text = re.sub(r'\(.*?\)', '', word_data.text).strip()
            
            # Clean for ignore list
            clean_word = raw_text.lower().rstrip('.,!?;:')
            
            if not clean_word or clean_word in ignore_list:
                continue
                
            if start_time is None:
                start_time = word_data.start
                
            current_sentence_words.append(raw_text)
            end_time = word_data.end
            
            # Detect sentence breaks (punctuation)
            if any(punct in raw_text for punct in ['.', '!', '?']):
                full_sentence = " ".join(" ".join(current_sentence_words).split())
                
                if full_sentence:
                    sentences.append(f"[{start_time:.2f}s → {end_time:.2f}s] {full_sentence}")
                
                current_sentence_words = []
                start_time = None
        
        # Handle remaining words
        if current_sentence_words:
            full_sentence = " ".join(" ".join(current_sentence_words).split())
            if full_sentence:
                sentences.append(f"[{start_time:.2f}s → {end_time:.2f}s] {full_sentence}")
        
        # Save translated lyrics with timestamps
        # Use song name and timestamp for unique filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if song_name:
            safe_song_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_song_name = safe_song_name.replace(' ', '_')
            translated_lyrics_file = output_dir / f"translated_lyrics_{safe_song_name}_{target_lang}_{timestamp}.txt"
        else:
            translated_lyrics_file = output_dir / f"translated_lyrics_elevenlabs_{target_lang}_{timestamp}.txt"
        with open(translated_lyrics_file, "w", encoding="utf-8") as f:
            f.write("\n".join(sentences))
        
        print(f"Translated lyrics saved: {translated_lyrics_file}")
        print(f"Total lines: {len(sentences)}")
        
        # Clean up temp dubbed file
        if dubbed_file.exists():
            try:
                dubbed_file.unlink()
            except:
                pass
        
        return str(translated_lyrics_file)
        
    except Exception as e:
        print(f"Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return None

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