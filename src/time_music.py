"""
Create a video with timed lyrics from lights_music.wav and time_lyrics.txt
"""

import re
import requests
from pathlib import Path
from PIL import Image

try:
    from moviepy import AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip
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


def extract_keyword_from_song(song_name, lyrics_file=None):
    """
    Extract a keyword from the song name or lyrics for image search.
    
    Args:
        song_name: Name of the song (e.g., "The Weekend - Blinded by the Lights")
        lyrics_file: Optional path to lyrics file for keyword extraction
    
    Returns:
        str: A keyword for image search
    """
    # Extract main keyword from song name
    # Remove common words and get the most meaningful word
    common_words = {'the', 'by', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
    
    # Split song name and get the main words
    if " - " in song_name:
        song_part = song_name.split(" - ", 1)[1]  # Get the song title part
    else:
        song_part = song_name
    
    # Extract meaningful words
    words = song_part.lower().split()
    keywords = [w.strip('.,!?;:()[]') for w in words if w.strip('.,!?;:()[]') not in common_words and len(w.strip('.,!?;:()[]')) > 3]
    
    if keywords:
        return keywords[0]  # Return the first meaningful keyword
    
    # Fallback: try to get a word from lyrics if available
    if lyrics_file and Path(lyrics_file).exists():
        try:
            with open(lyrics_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Get first meaningful word from lyrics
                words = content.lower().split()
                for word in words:
                    clean_word = word.strip('.,!?;:()[]')
                    if clean_word not in common_words and len(clean_word) > 4:
                        return clean_word
        except:
            pass
    
    # Final fallback
    return "music"


def download_unsplash_image(keyword, access_key, output_path="background_image.jpg"):
    """
    Search Unsplash for an image using a keyword and download it.
    
    Args:
        keyword: Search keyword
        access_key: Unsplash API access key
        output_path: Path to save the downloaded image
    
    Returns:
        str: Path to downloaded image, or None if failed
    """
    print(f"Searching Unsplash for keyword: '{keyword}'...")
    
    try:
        # Search for photos
        search_url = "https://api.unsplash.com/search/photos"
        headers = {
            "Authorization": f"Client-ID {access_key}"
        }
        params = {
            "query": keyword,
            "per_page": 1,
            "orientation": "landscape"
        }
        
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("results") or len(data["results"]) == 0:
            print(f"No images found for keyword '{keyword}'")
            return None
        
        # Get the first result
        image_url = data["results"][0]["urls"]["regular"]  # Use 'regular' size for good quality
        
        # Download the image
        print(f"Downloading image from Unsplash...")
        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()
        
        # Save the image
        with open(output_path, 'wb') as f:
            f.write(img_response.content)
        
        print(f"Background image saved to: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error downloading image from Unsplash: {e}")
        return None


def create_lyrics_video(audio_file, lyrics_file, output_file, background_image=None):
    """
    Create a video with timed lyrics overlaid on the audio.
    
    Args:
        audio_file: Path to audio file
        lyrics_file: Path to lyrics file with timestamps
        output_file: Path to output video file
        background_image: Optional path to background image file
    """
    print(f"Loading audio file: {audio_file}...")
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    
    print(f"Parsing lyrics file: {lyrics_file}...")
    lyrics_data = parse_lyrics_file(lyrics_file)
    
    print(f"Found {len(lyrics_data)} lyric segments")
    
    # Create background video
    print("Creating video background...")
    if background_image and Path(background_image).exists():
        # Use the provided background image
        print(f"Using background image: {background_image}")
        # Resize image to 1920x1080 using PIL for better compatibility
        try:
            img = Image.open(background_image)
            img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
            # Save resized image to output directory
            project_root = Path(__file__).parent.parent
            resized_path = str(project_root / "output" / "background_resized.jpg")
            img.save(resized_path)
            video = ImageClip(resized_path, duration=duration)
        except Exception as e:
            print(f"Warning: Could not resize image, using original: {e}")
            video = ImageClip(background_image, duration=duration)
            # Try to resize using moviepy's resize method
            try:
                video = video.resize(newsize=(1920, 1080))
            except:
                pass
    else:
        # Fallback to black background
        print("Using black background (no image provided)")
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

