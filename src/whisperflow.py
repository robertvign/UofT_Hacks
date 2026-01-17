import os
import sys
from pathlib import Path

# Try importing whisper (openai-whisper package) and librosa
try:
    import whisper
    import librosa
except ImportError as e:
    print("Error: Required packages not installed.")
    print("Please run: pip install openai-whisper librosa")
    print(f"Missing: {e}")
    sys.exit(1)

# Check if load_model exists (verify it's the right package)
if not hasattr(whisper, 'load_model'):
    print("Error: Wrong 'whisper' package installed.")
    print("The 'whisper' module doesn't have 'load_model' attribute.")
    print("Please uninstall any old whisper package and install openai-whisper:")
    print("  pip uninstall whisper")
    print("  pip install openai-whisper")
    sys.exit(1)

# Check if file exists
audio_file = "lights_vocals.wav"
if not Path(audio_file).exists():
    print(f"Error: File '{audio_file}' not found!")
    print(f"Current directory: {os.getcwd()}")
    sys.exit(1)

print("Loading Whisper model...")
model = whisper.load_model("base")

print(f"Loading audio file: {audio_file}...")
# Load audio with librosa to avoid ffmpeg dependency
# Whisper expects mono audio at 16kHz
audio, sr = librosa.load(audio_file, sr=16000, mono=True)

print(f"Transcribing {audio_file}...")
# Pass audio as numpy array instead of file path to avoid ffmpeg
result = model.transcribe(
    audio,
    language="en",
    verbose=True
)

print("\nTranscribing audio...")
print(f"Full transcription:\n{result['text']}")

# Filter segments to keep only real lyrics with timestamps
# Remove filler sounds but preserve actual lyrics
filler_sounds = ['um', 'uh', 'er', 'ah', 'hmm']
filtered_segments = []

# Process segments to filter out filler sounds
for segment in result["segments"]:
    text = segment['text'].strip()
    if not text:
        continue
    
    # Skip segments that are only filler sounds
    words = text.split()
    if not words:
        continue
    
    # Check if segment is mostly filler sounds (more than half)
    filler_count = sum(1 for w in words if w.lower().rstrip('.,!?;:') in filler_sounds)
    if filler_count > len(words) / 2 and len(words) <= 3:
        continue  # Skip segments that are mostly filler sounds
    
    # Keep all other segments as they contain lyrics
    filtered_segments.append(segment)

# Ensure "I'm Sorry" and "Okay" are included if they appear in the original
original_lower = result['text'].lower()
filtered_texts = [seg['text'].lower().strip() for seg in filtered_segments]

# Add "I'm Sorry" if present in original but not in filtered
if ("i'm sorry" in original_lower or "im sorry" in original_lower):
    if not any("i'm sorry" in text or "im sorry" in text for text in filtered_texts):
        # Find the segment with "I'm sorry" and add it
        for segment in result["segments"]:
            seg_text = segment['text'].lower().strip()
            if "i'm sorry" in seg_text or "im sorry" in seg_text:
                filtered_segments.insert(0, segment)
                break

# Add "Okay" if present in original but not in filtered
if "okay" in original_lower or (" ok " in original_lower):
    if not any("okay" in text or (" ok " in text and len(text.split()) <= 3) for text in filtered_texts):
        # Find the segment with "Okay" and add it
        for segment in result["segments"]:
            seg_text = segment['text'].lower().strip()
            if "okay" in seg_text or (" ok " in seg_text and len(seg_text.split()) <= 3):
                # Check if it's not already in filtered_segments
                if segment not in filtered_segments:
                    filtered_segments.append(segment)
                break

# Remove duplicates while preserving order
seen = set()
unique_segments = []
for segment in filtered_segments:
    text_key = segment['text'].strip().lower()
    if text_key not in seen:
        seen.add(text_key)
        unique_segments.append(segment)

# Format with timestamps: [start → end] lyrics
lyrics_with_timestamps = []
for segment in unique_segments:
    start = segment['start']
    end = segment['end']
    text = segment['text'].strip()
    lyrics_with_timestamps.append(f"[{start:.2f}s → {end:.2f}s] {text}")

final_lyrics = '\n'.join(lyrics_with_timestamps)

# Save to text file
output_file = "transcribed_lyrics.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(final_lyrics)

print(f"\nFiltered lyrics saved to: {output_file}")
print(f"\nFiltered lyrics:\n{final_lyrics}")
