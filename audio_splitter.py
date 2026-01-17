"""
Audio Splitter using Demucs
Separates audio files into music (instrumental) and voice (vocals) tracks.
"""

import sys
from pathlib import Path

try:
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    from demucs.audio import AudioFile, save_audio
except ImportError:
    print("Error: demucs is not installed. Please run: pip install demucs")
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
    
    # Load audio file
    wav = AudioFile(filename).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels
    )
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

