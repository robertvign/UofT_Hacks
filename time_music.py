"""
Create a video with timed lyrics from lights_music.wav and time_lyrics.txt
"""

import re
from pathlib import Path

try:
    from moviepy import AudioFileClip, TextClip, CompositeVideoClip, ColorClip
except ImportError:
    print("Error: moviepy not installed. Please run: pip install moviepy")
    exit(1)


def parse_lyrics_file(filename):
    """
    Parse time_lyrics.txt file and extract timestamps and lyrics.
    
    Returns:
        list of tuples: [(start_time, end_time, text), ...]
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
    
    return lyrics


def create_lyrics_video(audio_file, lyrics_file, output_file):
    """
    Create a video with timed lyrics overlaid on the audio.
    """
    print(f"Loading audio file: {audio_file}...")
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    
    print(f"Parsing lyrics file: {lyrics_file}...")
    lyrics_data = parse_lyrics_file(lyrics_file)
    
    print(f"Found {len(lyrics_data)} lyric segments")
    
    # Create a black background video
    print("Creating video background...")
    video = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=duration)
    
    # Create text clips for each lyric segment
    text_clips = []
    for start, end, text in lyrics_data:
        try:
            # Create text clip using moviepy 2.2.1 API
            # Use 'label' method (doesn't require ImageMagick)
            # Set duration when creating the clip
            txt_clip = TextClip(
                text=text,
                font_size=60,
                color='white',
                method='label',
                size=(1600, None),
                text_align='center',
                duration=end - start
            )
            
            txt_clip = txt_clip.with_position(('center', 'center')).with_start(start)
            text_clips.append(txt_clip)
            print(f"Created text clip: [{start:.2f}s → {end:.2f}s] '{text[:50]}...'")
        except Exception as e:
            print(f"Warning: Could not create text clip for '{text}': {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"Compositing {len(text_clips)} text clips...")
    # Composite all clips
    final_video = CompositeVideoClip([video] + text_clips)
    
    # Set audio using moviepy 2.2.1 API
    print("Adding audio track...")
    final_video = final_video.with_audio(audio)
    
    # Write video file
    print(f"Rendering video to {output_file}...")
    print("This may take a while...")
    final_video.write_videofile(
        output_file,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4
    )
    
    # Clean up
    audio.close()
    final_video.close()
    
    print(f"Video created successfully: {output_file}")


if __name__ == "__main__":
    audio_file = "lights_music.wav"
    lyrics_file = "time_lyrics.txt"
    output_file = "lights_music_with_lyrics.mp4"
    
    # Check if files exist
    if not Path(audio_file).exists():
        print(f"Error: Audio file '{audio_file}' not found!")
        exit(1)
    
    if not Path(lyrics_file).exists():
        print(f"Error: Lyrics file '{lyrics_file}' not found!")
        exit(1)
    
    create_lyrics_video(audio_file, lyrics_file, output_file)

