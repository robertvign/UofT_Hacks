"""
Audio Splitter using Demucs
Separates audio files into music (instrumental) and voice (vocals) tracks.
"""

import sys
from pathlib import Path
import numpy as np

try:
    import torch
    import librosa
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    from demucs.audio import save_audio
except ImportError as e:
    print(f"Error: Required package not installed. Please run: pip install demucs librosa")
    print(f"Missing: {e}")
    sys.exit(1)


def separate_audio(filename):
    """
    Separate audio file into vocals and instrumental tracks.
    
    Args:
        filename: Path to input audio file (string)
    
    Returns:
        tuple: (vocals_path, music_path) as strings
    """
    # Validate input file
    input_path = Path(filename)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {filename}")
    
    # Set output directory (same as input file location)
    output_dir = input_path.parent
    
    # Get base filename without extension
    base_name = input_path.stem
    
    print(f"Loading model...")
    model = get_model("htdemucs")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    print(f"Using device: {device}")
    
    print(f"Processing audio file: {filename}...")
    
    # Load audio file using librosa
    # Load as mono if model expects 1 channel, otherwise stereo
    mono = model.audio_channels == 1
    wav, sr = librosa.load(filename, sr=model.samplerate, mono=mono)
    
    # Convert to the format demucs expects (channels, samples)
    if wav.ndim == 1:
        wav = wav[None]  # Add channel dimension for mono audio: (samples,) -> (1, samples)
    
    # Ensure correct shape: (channels, samples)
    wav = torch.from_numpy(wav).float()
    
    # Normalize audio
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()
    
    # Apply model for source separation
    sources = apply_model(model, wav[None], device=device, progress=True)[0]
    sources = sources * ref.std() + ref.mean()
    
    # Demucs separates into: drums, bass, other, vocals
    # Extract vocals and combine everything else as music
    vocals = sources[3]  # vocals is the 4th component (index 3)
    music = sources[0] + sources[1] + sources[2]  # drums + bass + other = music
    
    # Save separated tracks
    vocals_path = output_dir / f"{base_name}_vocals.wav"
    music_path = output_dir / f"{base_name}_music.wav"
    
    print(f"Saving vocals to: {vocals_path}")
    save_audio(vocals, vocals_path, samplerate=model.samplerate)
    
    print(f"Saving music to: {music_path}")
    save_audio(music, music_path, samplerate=model.samplerate)
    
    print(f"\nSeparation complete!")
    print(f"  Vocals: {vocals_path}")
    print(f"  Music: {music_path}")
    
    return str(vocals_path), str(music_path)


if __name__ == "__main__":
    separate_audio("lights.mp3")
