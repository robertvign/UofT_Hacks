import torch
import librosa
import numpy as np
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC

MODEL_NAME = "facebook/wav2vec2-large-xlsr-53-phoneme"

# Load model and processor (lazy loading to avoid loading if not needed)
processor = None
model = None


def _load_model():
    """Load the model and processor if not already loaded."""
    global processor, model
    if processor is None or model is None:
        processor = Wav2Vec2Processor.from_pretrained(MODEL_NAME)
        model = Wav2Vec2ForCTC.from_pretrained(MODEL_NAME)
        model.eval()
    return processor, model


def load_audio(audio_path, target_sr=16000, mono=True):
    """
    Load audio file using librosa.
    
    Args:
        audio_path: Path to audio file
        target_sr: Target sample rate (default: 16000 for wav2vec2)
        mono: Convert to mono (default: True)
    
    Returns:
        numpy array of audio samples
    """
    audio, sr = librosa.load(audio_path, sr=target_sr, mono=mono)
    return audio


def audio_to_phonemes(audio_path):
    """
    Convert audio file to phonemes using wav2vec2 model.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        String of phonemes (space-separated)
    """
    processor, model = _load_model()
    
    # Load audio
    audio = load_audio(audio_path)
    
    # Convert to numpy array if needed and ensure correct format
    if isinstance(audio, list):
        audio = np.array(audio)
    
    # Process audio
    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt",
        padding=True
    )
    
    # Get phoneme predictions
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    
    pred_ids = torch.argmax(logits, dim=-1)
    phonemes = processor.batch_decode(pred_ids)
    
    return phonemes[0]
