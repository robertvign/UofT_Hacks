import os
import time
import re
from pathlib import Path
from elevenlabs.client import ElevenLabs

# --- PATH SETUP ---
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
# This ensures it aligns with your pipeline's DATA_DIR
DATA_DIR = PROJECT_ROOT / "data"

def transcribe_audio(audio_file, output_file=None):
    """
    Transcribe audio using ElevenLabs Scribe and save with timestamps.
    Matches the function signature used in the Music Video Pipeline.
    """
    if output_file is None:
        # Matches your pipeline's default location
        output_file = str(DATA_DIR / "transcribed_lyrics.txt")
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Step 3: Transcribing audio with ElevenLabs Scribe ===")
    
    if not Path(audio_file).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    # 1. Initialize Client
    client = ElevenLabs(api_key="3b733eee1638020b18512a51e5346319b8ceb2453b964e9869baf93db035d8e2")

    print(f"Sending {Path(audio_file).name} to ElevenLabs...")
    
    with open(audio_file, "rb") as audio_input:
        transcription = client.speech_to_text.convert(
            file=audio_input,
            model_id="scribe_v1",
        )

    # 2. FILTERS AND CLEANING
    ignore_list = {'oh', 'um', 'uh', 'er', 'ah', 'hmm', 'yeah', 'mhm'}
    
    sentences = []
    current_sentence_words = []
    start_time = None

    for word_data in transcription.words:
        # A. Remove parentheses content like (music)
        raw_text = re.sub(r'\(.*?\)', '', word_data.text).strip()
        
        # B. Clean for ignore list
        clean_word = raw_text.lower().rstrip('.,!?;:')
        
        if not clean_word or clean_word in ignore_list:
            continue
            
        if start_time is None:
            start_time = word_data.start
            
        current_sentence_words.append(raw_text)
        end_time = word_data.end

        # C. Detect sentence breaks (punctuation)
        if any(punct in raw_text for punct in ['.', '!', '?']):
            # Collapse random spaces into exactly one
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

    # 3. Save output
    final_lyrics = "\n".join(sentences)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_lyrics)

    print(f"Cleanup complete: Parentheses removed, fillers ignored, spaces collapsed.")
    print(f"Transcription saved to: {output_file}")
    
    return output_file

if __name__ == "__main__":
    # Test block to ensure it works standalone within your project structure
    TEST_VOCALS = PROJECT_ROOT / "output" / "lights_vocals.wav"
    if TEST_VOCALS.exists():
        transcribe_audio(str(TEST_VOCALS))