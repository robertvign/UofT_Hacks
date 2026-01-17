"""
Music Video Pipeline
Takes a song name, MP4 file, and target language, then processes it through:
1. Audio extraction from MP4
2. Audio separation (vocals/music)
3. Whisper transcription
4. Genius lyrics retrieval
5. AI comparison and timestamp alignment
6. Translation to target language
7. Final video creation with timed lyrics
"""

import sys
import os
import asyncio
import re
import shutil
import json
from pathlib import Path
from datetime import datetime

# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
DATABASE_DIR = PROJECT_ROOT / "database"

# Import required modules
try:
    from moviepy import VideoFileClip
    import whisper
    import librosa
    from backboard import BackboardClient
except ImportError as e:
    print(f"Error: Required packages not installed. {e}")
    print("Please install: pip install moviepy openai-whisper librosa backboard-sdk")
    sys.exit(1)

# Import local modules
import audio_splitter
import lyricgeneration
import time_music

# Unsplash API credentials
UNSPLASH_ACCESS_KEY = "rnFs6QP_HBtJvSdxi2ynhY9kWJKG0xJhjwQsbOgkyYY"
UNSPLASH_SECRET_KEY = "ff1-UJgZbtepXSPZ9yO0pcDlMVdgBmb6LLxUhZtf7IU"


def extract_audio_from_mp4(mp4_file, output_audio_file):
    """
    Extract audio from MP4 file.
    
    Args:
        mp4_file: Path to input MP4 file
        output_audio_file: Path to output audio file (WAV or MP3)
    
    Returns:
        str: Path to extracted audio file
    """
    print(f"\n=== Step 1: Extracting audio from {mp4_file} ===")
    video = VideoFileClip(mp4_file)
    # Remove verbose parameter as it's not supported in newer moviepy versions
    video.audio.write_audiofile(output_audio_file, logger=None)
    video.close()
    print(f"Audio extracted to: {output_audio_file}")
    return output_audio_file


def transcribe_audio(audio_file, output_file=None):
    if output_file is None:
        output_file = str(DATA_DIR / "transcribed_lyrics.txt")
    """
    Transcribe audio using Whisper and save with timestamps.
    
    Args:
        audio_file: Path to audio file (vocals)
        output_file: Path to output transcription file
    
    Returns:
        str: Path to transcription file
    """
    print(f"\n=== Step 3: Transcribing audio with Whisper ===")
    
    if not Path(audio_file).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    print("Loading Whisper model...")
    model = whisper.load_model("base")
    
    print(f"Loading audio file: {audio_file}...")
    audio, sr = librosa.load(audio_file, sr=16000, mono=True)
    
    print(f"Transcribing {audio_file}...")
    result = model.transcribe(
        audio,
        language="en",
        verbose=True
    )
    
    # Filter segments to keep only real lyrics with timestamps
    filler_sounds = ['um', 'uh', 'er', 'ah', 'hmm']
    filtered_segments = []
    
    for segment in result["segments"]:
        text = segment['text'].strip()
        if not text:
            continue
        
        words = text.split()
        if not words:
            continue
        
        filler_count = sum(1 for w in words if w.lower().rstrip('.,!?;:') in filler_sounds)
        if filler_count > len(words) / 2 and len(words) <= 3:
            continue
        
        filtered_segments.append(segment)
    
    # Format with timestamps
    lyrics_with_timestamps = []
    for segment in filtered_segments:
        start = segment['start']
        end = segment['end']
        text = segment['text'].strip()
        lyrics_with_timestamps.append(f"[{start:.2f}s → {end:.2f}s] {text}")
    
    final_lyrics = '\n'.join(lyrics_with_timestamps)
    
    # Save to text file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_lyrics)
    
    print(f"Transcription saved to: {output_file}")
    return output_file


async def compare_lyrics_with_ai(genius_file, transcribed_file, output_file=None, max_retries=3):
    if output_file is None:
        output_file = str(DATA_DIR / "genius_with_timestamps.txt")
    """
    Use AI to compare Genius lyrics with transcribed lyrics and add timestamps.
    
    Args:
        genius_file: Path to Genius lyrics file
        transcribed_file: Path to transcribed lyrics file
        output_file: Path to output file with timestamps
        max_retries: Maximum number of retry attempts
    
    Returns:
        str: Path to output file
    """
    print(f"\n=== Step 5: Comparing lyrics with AI ===")
    
    # Increase timeout to 180 seconds
    client = BackboardClient(api_key="espr_-E7xd5n6PKHueWcNykyoDWDE3hewLEWyduHKDXmhKSI", timeout=180)
    
    with open(genius_file, "r", encoding="utf-8") as file:
        geniuslyrics = file.read()
    
    with open(transcribed_file, "r", encoding="utf-8") as file:
        transcribedlyrics = file.read()
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            print(f"Sending lyrics to AI for comparison... (Attempt {attempt + 1}/{max_retries})")
            
            assistant = await client.create_assistant(
                name="Lyrics Comparison Assistant"
            )
            
            thread = await client.create_thread(assistant.assistant_id)
            
            response = await client.add_message(
                thread_id=thread.thread_id,
                content=f"This is my own writing for a school project, Take {geniuslyrics} and {transcribedlyrics} and compare them. If two lines are similar enough, take the timestamp from the transcribed file and insert it in the relevant line in the genius file. Then output the genius file with the appropriate timestamps. Output only the lyrics with timestamps, one per line.",
                llm_provider="google",
                model_name="gemini-2.5-flash",
                stream=False
            )
            
            with open(output_file, "w", encoding="utf-8") as file:
                file.write(response.content)
            
            print(f"Aligned lyrics saved to: {output_file}")
            return output_file
            
        except Exception as e:
            error_msg = str(e)
            print(f"Attempt {attempt + 1} failed: {error_msg}")
            
            # If it's a timeout or 504 error and we have retries left, wait and retry
            if attempt < max_retries - 1 and ("504" in error_msg or "timeout" in error_msg.lower() or "Gateway" in error_msg):
                wait_time = (attempt + 1) * 5  # Exponential backoff: 5s, 10s, 15s
                print(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
                continue
            else:
                # If all retries failed or it's a different error, fallback to transcribed lyrics
                print(f"\n⚠️  Warning: AI comparison failed after {attempt + 1} attempts.")
                print(f"   Falling back to using transcribed lyrics with timestamps.")
                print(f"   Error: {error_msg}")
                
                # Copy transcribed file as fallback
                shutil.copy(transcribed_file, output_file)
                print(f"   Using transcribed lyrics: {output_file}")
                return output_file
    
    # Should never reach here, but just in case
    shutil.copy(transcribed_file, output_file)
    return output_file


async def translate_lyrics(input_file, target_language, output_file=None, max_retries=3):
    if output_file is None:
        output_file = str(DATA_DIR / "translated_genius_lyrics.txt")
    """
    Translate lyrics to target language using deep_translator library.
    
    Args:
        input_file: Path to lyrics file with timestamps
        target_language: Target language name (e.g., "spanish", "french", "romanian")
        output_file: Path to output translated file
        max_retries: Maximum number of retry attempts (for individual lines)
    
    Returns:
        str: Path to translated file
    """
    print(f"\n=== Step 6: Translating lyrics to {target_language} ===")
    
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        raise ImportError("deep_translator not installed. Please install it: pip install deep-translator")
    
    # Map common language names to language codes
    language_map = {
        'english': 'en',
        'spanish': 'es',
        'french': 'fr',
        'german': 'de',
        'italian': 'it',
        'portuguese': 'pt',
        'russian': 'ru',
        'chinese': 'zh',
        'japanese': 'ja',
        'korean': 'ko',
        'arabic': 'ar',
        'hindi': 'hi',
        'romanian': 'ro',
        'polish': 'pl',
        'dutch': 'nl',
        'greek': 'el',
        'turkish': 'tr',
        'swedish': 'sv',
        'norwegian': 'no',
        'danish': 'da',
        'finnish': 'fi',
        'czech': 'cs',
        'hungarian': 'hu',
        'ukrainian': 'uk',
        'vietnamese': 'vi',
        'thai': 'th',
        'indonesian': 'id',
        'malay': 'ms',
        'tagalog': 'tl',
        'hebrew': 'he',
        'cherokee': 'chr',  # Note: may not be supported by all translators
    }
    
    # Normalize target language
    target_lang_lower = target_language.lower().strip()
    target_code = language_map.get(target_lang_lower, target_lang_lower[:2] if len(target_lang_lower) >= 2 else 'en')
    
    # If it's already a 2-letter code, use it directly
    if len(target_lang_lower) == 2:
        target_code = target_lang_lower
    
    print(f"Translating from English to {target_language} (code: {target_code})...")
    
    # Parse the input file to extract timestamps and text
    lines_with_timestamps = []
    pattern_full = r'\[(\d+\.?\d*)s → (\d+\.?\d*)s\] (.+)'
    pattern_start_only = r'\[(\d+\.?\d*)s\] (.+)'
    
    with open(input_file, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            
            # Try full format [start → end] text
            match_full = re.match(pattern_full, line)
            if match_full:
                start = match_full.group(1)
                end = match_full.group(2)
                text = match_full.group(3).strip()
                lines_with_timestamps.append((start, end, text, True))  # True = has end time
                continue
            
            # Try start-only format [start] text
            match_start = re.match(pattern_start_only, line)
            if match_start:
                start = match_start.group(1)
                text = match_start.group(2).strip()
                lines_with_timestamps.append((start, None, text, False))  # False = no end time
                continue
            
            # Plain text without timestamp
            lines_with_timestamps.append((None, None, line, False))
    
    # Initialize translator
    translator = GoogleTranslator(source='en', target=target_code)
    
    # Translate each line
    translated_lines = []
    for i, (start, end, text, has_end) in enumerate(lines_with_timestamps):
        if not text or not text.strip():
            # Empty line, preserve it
            if start:
                if has_end and end:
                    translated_lines.append(f"[{start}s → {end}s] ")
                else:
                    translated_lines.append(f"[{start}s] ")
            else:
                translated_lines.append("")
            continue
        
        # Translate the text
        translated_text = None
        for attempt in range(max_retries):
            try:
                translated_text = translator.translate(text)
                break
            except Exception as e:
                error_msg = str(e)
                print(f"  Translation attempt {attempt + 1} failed for line {i+1}: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait 1 second before retry
                else:
                    # If all retries failed, use original text
                    print(f"  Warning: Using original text for line {i+1}")
                    translated_text = text
        
        if translated_text is None:
            translated_text = text  # Fallback to original
        
        # Reconstruct the line with timestamp
        if start:
            if has_end and end:
                translated_lines.append(f"[{start}s → {end}s] {translated_text}")
            else:
                translated_lines.append(f"[{start}s] {translated_text}")
        else:
            translated_lines.append(translated_text)
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Translated {i + 1}/{len(lines_with_timestamps)} lines...")
    
    # Write translated lyrics to output file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write("\n".join(translated_lines))
    
    print(f"Translated {len(lines_with_timestamps)} lines")
    print(f"Translated lyrics saved to: {output_file}")
    return output_file


def parse_lyrics_with_timestamps(filename):
    """
    Parse lyrics file with timestamps and return list of (start, end, text) tuples.
    Handles multiple formats:
    - [start → end] text
    - [start] text (end time calculated from next line)
    - plain text (estimated timestamps)
    """
    lyrics = []
    
    # Pattern 1: [start → end] text
    pattern_full = r'\[(\d+\.?\d*)s → (\d+\.?\d*)s\] (.+)'
    # Pattern 2: [start] text
    pattern_start_only = r'\[(\d+\.?\d*)s\] (.+)'
    
    # First pass: read all lines and parse timestamps
    lines_with_times = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Try full format first
            match_full = re.match(pattern_full, line)
            if match_full:
                start = float(match_full.group(1))
                end = float(match_full.group(2))
                text = match_full.group(3).strip()
                lines_with_times.append((start, end, text))
                continue
            
            # Try start-only format
            match_start = re.match(pattern_start_only, line)
            if match_start:
                start = float(match_start.group(1))
                text = match_start.group(2).strip()
                lines_with_times.append((start, None, text))  # end will be calculated
                continue
            
            # No timestamp - plain text
            if line and not line.startswith('[') and len(line) > 2:
                lines_with_times.append((None, None, line))
    
    # Second pass: calculate end times for lines that only have start times
    for i, (start, end, text) in enumerate(lines_with_times):
        if end is None:
            # Calculate end time from next line's start time
            if i + 1 < len(lines_with_times):
                next_start = lines_with_times[i + 1][0]
                if next_start is not None:
                    end = next_start
                else:
                    # Next line has no timestamp, estimate 3 seconds
                    end = start + 3.0 if start is not None else 3.0
            else:
                # Last line, estimate 3 seconds duration
                end = start + 3.0 if start is not None else 3.0
        
        if start is None:
            # No start time, estimate from previous line
            if i > 0:
                prev_end = lyrics[-1][1] if lyrics else 0.0
                start = prev_end
                end = start + 3.0
            else:
                start = 0.0
                end = 3.0
        
        lyrics.append((start, end, text))
    
    return lyrics


def create_timed_lyrics_file(translated_file, output_file=None):
    if output_file is None:
        output_file = str(DATA_DIR / "time_lyrics.txt")
    """
    Create a properly formatted time_lyrics.txt file from translated lyrics.
    
    Args:
        translated_file: Path to translated lyrics file
        output_file: Path to output time_lyrics.txt file
    
    Returns:
        str: Path to output file
    """
    print(f"\n=== Step 7: Creating timed lyrics file ===")
    
    lyrics = parse_lyrics_with_timestamps(translated_file)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for start, end, text in lyrics:
            f.write(f"[{start:.2f}s → {end:.2f}s] {text}\n")
    
    print(f"Timed lyrics saved to: {output_file}")
    return output_file


def save_video_metadata(video_path, song_name, target_language, original_file=None):
    """
    Save metadata about a processed video to the database.
    
    Args:
        video_path: Path to the final video file
        song_name: Name of the song
        target_language: Target language for translation
        original_file: Original input file path (optional)
    """
    DATABASE_DIR.mkdir(exist_ok=True)
    
    metadata_file = DATABASE_DIR / "videos_metadata.json"
    
    # Load existing metadata
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
        except:
            metadata_list = []
    else:
        metadata_list = []
    
    # Get video file info
    video_path_obj = Path(video_path)
    file_size = video_path_obj.stat().st_size if video_path_obj.exists() else 0
    file_size_mb = file_size / (1024 * 1024)
    
    # Create metadata entry
    metadata_entry = {
        "id": len(metadata_list) + 1,
        "song_name": song_name,
        "translation_language": target_language,
        "video_filename": video_path_obj.name,
        "video_path": str(video_path),
        "original_file": original_file if original_file else None,
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size_mb, 2),
        "created_at": datetime.now().isoformat(),
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "created_time": datetime.now().strftime("%H:%M:%S")
    }
    
    # Add to list
    metadata_list.append(metadata_entry)
    
    # Save updated metadata
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)
    
    # Also save as human-readable text file
    text_metadata_file = DATABASE_DIR / "videos_metadata.txt"
    with open(text_metadata_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Video ID: {metadata_entry['id']}\n")
        f.write(f"Song Name: {song_name}\n")
        f.write(f"Translation Language: {target_language}\n")
        f.write(f"Video Filename: {video_path_obj.name}\n")
        f.write(f"Video Path: {video_path}\n")
        if original_file:
            f.write(f"Original File: {original_file}\n")
        f.write(f"File Size: {file_size_mb:.2f} MB ({file_size} bytes)\n")
        f.write(f"Created: {metadata_entry['created_at']}\n")
        f.write(f"{'='*60}\n")
    
    print(f"\nMetadata saved to: {metadata_file}")
    return metadata_entry


async def process_music_video(song_name, mp4_file, target_language, save_to_database=True):
    """
    Main pipeline to process music video.
    
    Args:
        song_name: Name of the song (for Genius API lookup)
        mp4_file: Path to input MP4 file
        target_language: Target language for translation
        save_to_database: Whether to save to database folder (default: True)
    """
    print(f"\n{'='*60}")
    print(f"Music Video Pipeline")
    print(f"Song: {song_name}")
    print(f"Input: {mp4_file}")
    print(f"Target Language: {target_language}")
    print(f"{'='*60}\n")
    
    # Step 1: Extract audio from MP4 or use audio file directly
    input_path = Path(mp4_file)
    audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
    
    if input_path.suffix.lower() in audio_extensions:
        # Already an audio file, use it directly
        print(f"\n=== Step 1: Using audio file directly ===")
        extracted_audio = str(input_path)
        print(f"Using audio file: {extracted_audio}")
    else:
        # Extract audio from video file
        base_name = input_path.stem
        extracted_audio = f"{base_name}_extracted.wav"
        extract_audio_from_mp4(mp4_file, extracted_audio)
    
    # Step 2: Separate audio into vocals and music
    print(f"\n=== Step 2: Separating audio ===")
    vocals_path, music_path = audio_splitter.separate_audio(extracted_audio)
    
    # Step 3: Transcribe vocals with Whisper
    transcribed_file = transcribe_audio(vocals_path)
    
    # Step 4: Get lyrics from Genius
    print(f"\n=== Step 4: Fetching lyrics from Genius ===")
    # Extract artist and song from song_name (assuming format "Artist - Song" or just "Song")
    if " - " in song_name:
        parts = song_name.split(" - ", 1)
        artist = parts[0].strip()
        song = parts[1].strip()
    else:
        # Try to extract from song_name or use a default
        artist = ""
        song = song_name
    
    try:
        url = lyricgeneration.get_song_url(song, artist) if artist else lyricgeneration.get_song_url(song, "")
        lyrics = lyricgeneration.get_lyrics(url)
        genius_file = str(DATA_DIR / "genius_lyrics.txt")
        lyricgeneration.save_lyrics_to_file(lyrics, genius_file)
        print(f"Genius lyrics saved to: {genius_file}")
    except Exception as e:
        print(f"Warning: Could not fetch Genius lyrics: {e}")
        print("Continuing with transcribed lyrics only...")
        genius_file = None
    
    # Step 5: Compare lyrics with AI (if Genius lyrics available)
    if genius_file and Path(genius_file).exists():
        aligned_file = await compare_lyrics_with_ai(genius_file, transcribed_file)
    else:
        print("\n=== Step 5: Using transcribed lyrics only ===")
        aligned_file = transcribed_file
    
    # Step 6: Translate to target language
    translated_file = await translate_lyrics(aligned_file, target_language)
    
    # Step 7: Create timed lyrics file
    time_lyrics_file = create_timed_lyrics_file(translated_file)
    
    # Step 8: Get background image from Unsplash
    print(f"\n=== Step 8: Fetching background image from Unsplash ===")
    keyword = time_music.extract_keyword_from_song(song_name, genius_file if genius_file and Path(genius_file).exists() else None)
    background_image = time_music.download_unsplash_image(keyword, UNSPLASH_ACCESS_KEY, str(OUTPUT_DIR / "background_image.jpg"))
    
    # Step 9: Create final video
    print(f"\n=== Step 9: Creating final video ===")
    
    # Determine output location
    if save_to_database:
        DATABASE_DIR.mkdir(exist_ok=True)
        # Create unique filename based on song name and language
        safe_song_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_song_name = safe_song_name.replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"{safe_song_name}_{target_language}_{timestamp}.mp4"
        final_output = str(DATABASE_DIR / video_filename)
    else:
        final_output = str(OUTPUT_DIR / "final.mp4")
    
    time_music.create_lyrics_video(music_path, time_lyrics_file, final_output, background_image=background_image)
    
    # Save metadata if saving to database
    if save_to_database:
        save_video_metadata(final_output, song_name, target_language, mp4_file)
    
    print(f"\n{'='*60}")
    print(f"Pipeline complete!")
    print(f"Final video: {final_output}")
    print(f"{'='*60}\n")
    
    return final_output


def main():
    # Hardcoded values
    song_name = "The Weekend - Blinded by the Lights"
    mp4_file = str(OUTPUT_DIR / "lights.mp3")  # Input file should be in output directory
    target_language = "spanish"
    
    # Validate file exists
    if not Path(mp4_file).exists():
        print(f"Error: File not found: {mp4_file}")
        print(f"Please place your audio/video file in the {OUTPUT_DIR} directory")
        sys.exit(1)
    
    # Run the pipeline
    asyncio.run(process_music_video(song_name, mp4_file, target_language))


if __name__ == "__main__":
    main()

