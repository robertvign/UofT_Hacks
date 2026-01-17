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
    video.audio.write_audiofile(output_audio_file, verbose=False, logger=None)
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
                content=f"Take {geniuslyrics} and {transcribedlyrics} and compare them. If two lines are similar enough, take the timestamp from the transcribed file and insert it in the relevant line in the genius file. Then output the genius file with the appropriate timestamps. Output only the lyrics with timestamps, one per line.",
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
    Translate lyrics to target language using AI.
    
    Args:
        input_file: Path to lyrics file with timestamps
        target_language: Target language name (e.g., "spanish", "french")
        output_file: Path to output translated file
        max_retries: Maximum number of retry attempts
    
    Returns:
        str: Path to translated file
    """
    print(f"\n=== Step 6: Translating lyrics to {target_language} ===")
    
    with open(input_file, "r", encoding="utf-8") as file:
        lyrics = file.read()
    
    # Increase timeout to 180 seconds
    client = BackboardClient(api_key="espr_-E7xd5n6PKHueWcNykyoDWDE3hewLEWyduHKDXmhKSI", timeout=180)
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            print(f"Translating to {target_language}... (Attempt {attempt + 1}/{max_retries})")
            
            assistant = await client.create_assistant(
                name="Translator Assistant"
            )
            
            thread = await client.create_thread(assistant.assistant_id)
            
            response = await client.add_message(
                thread_id=thread.thread_id,
                content=f"This is my own writing, and I need the whole file translated into {target_language}. Output only the translated lines, maintaining a similar tone. Preserve the timestamp format [start → end] if present. If you need to stop, tell me why. {lyrics}",
                llm_provider="google",
                model_name="gemini-2.5-flash",
                stream=False
            )
            
            with open(output_file, "w", encoding="utf-8") as file:
                file.write(response.content)
            
            print(f"Translated lyrics saved to: {output_file}")
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
                # If all retries failed, raise the error (translation is critical)
                print(f"\n❌ Error: Translation failed after {attempt + 1} attempts.")
                print(f"   Error: {error_msg}")
                raise


def parse_lyrics_with_timestamps(filename):
    """
    Parse lyrics file with timestamps and return list of (start, end, text) tuples.
    Handles both formats: [start → end] text and plain text.
    """
    lyrics = []
    pattern = r'\[(\d+\.?\d*)s → (\d+\.?\d*)s\] (.+)'
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(pattern, line)
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                text = match.group(3).strip()
                lyrics.append((start, end, text))
            else:
                # If no timestamp, try to extract just text
                # Skip lines that are clearly not lyrics
                if line and not line.startswith('[') and len(line) > 2:
                    # Use previous end time or estimate
                    if lyrics:
                        prev_end = lyrics[-1][1]
                        lyrics.append((prev_end, prev_end + 3.0, line))
                    else:
                        lyrics.append((0.0, 3.0, line))
    
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

