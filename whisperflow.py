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

print("\nTranscription segments:")
for segment in result["segments"]:
    print(f"[{segment['start']:.2f}s → {segment['end']:.2f}s] {segment['text']}")

print(f"\nFull text:\n{result['text']}")
