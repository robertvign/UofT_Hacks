# UofT_Hacks

Music Video Pipeline with Lyrics Translation and Background Images

## Project Structure

```
UofT_Hacks/
├── src/                    # Source code (Python modules)
│   ├── music_video.py     # Main pipeline script
│   ├── time_music.py      # Video creation with lyrics
│   ├── audio_splitter.py  # Audio separation
│   ├── lyricgeneration.py # Genius API integration
│   └── ...                # Other modules
├── data/                   # Text files (lyrics, transcripts)
│   ├── genius_lyrics.txt
│   ├── time_lyrics.txt
│   └── ...
├── output/                 # Generated files (videos, audio, images)
│   ├── final.mp4
│   ├── lights.mp3
│   └── ...
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Place your audio/video file in the `output/` directory

3. Run the main pipeline:
   ```bash
   python src/music_video.py
   ```

The pipeline will:
- Extract and separate audio
- Transcribe lyrics
- Fetch lyrics from Genius
- Translate to target language
- Download background image from Unsplash
- Create final video with subtitles

## Features

- Automatic keyword extraction from song names
- Unsplash API integration for background images
- Multi-language translation support
- Timed lyrics overlay on videos
