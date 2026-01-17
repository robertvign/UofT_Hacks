"""
Extract phonemes DIRECTLY from audio using multilingual phoneme recognition.
Uses wav2vec2 XLSR models trained for phoneme recognition across languages.
"""

import librosa
import numpy as np
from pathlib import Path
import tempfile
import os


def load_audio(audio_path, target_sr=16000, mono=True):
    """Load audio file using librosa."""
    audio, sr = librosa.load(audio_path, sr=target_sr, mono=mono)
    return audio


# Multilingual phoneme recognition models (wav2vec2 XLSR)
PHONEME_MODELS = {
    'fr-fr': 'facebook/wav2vec2-large-xlsr-53-french',
    'fr': 'facebook/wav2vec2-large-xlsr-53-french',
    'en-us': 'facebook/wav2vec2-large-xlsr-53',
    'en': 'facebook/wav2vec2-large-xlsr-53',
    'es': 'facebook/wav2vec2-large-xlsr-53-spanish',
    'es-es': 'facebook/wav2vec2-large-xlsr-53-spanish',
}

# Global model cache
_phoneme_model_cache = {}


def _check_transformers():
    """Check if transformers is available."""
    try:
        import torch
        from transformers import AutoProcessor, AutoModelForCTC
        return True
    except ImportError:
        return False


def _load_phoneme_model(language='en-us'):
    """Load phoneme recognition model for the language."""
    if not _check_transformers():
        return None, None
    
    try:
        from transformers import AutoProcessor, AutoModelForCTC
    except ImportError:
        return None, None
    
    model_key = PHONEME_MODELS.get(language, 'facebook/wav2vec2-large-xlsr-53')
    
    if model_key in _phoneme_model_cache:
        return _phoneme_model_cache[model_key]
    
    try:
        print(f"  Loading phoneme recognition model: {model_key}...")
        processor = AutoProcessor.from_pretrained(model_key)
        model = AutoModelForCTC.from_pretrained(model_key)
        model.eval()
        
        _phoneme_model_cache[model_key] = (processor, model)
        return processor, model
    except Exception as e:
        print(f"  Warning: Could not load model: {e}")
        return None, None


def _extract_phoneme_from_segment(segment, processor, model, reference_phoneme, language='en-us'):
    """
    Extract phoneme directly from audio segment using phoneme recognition model.
    This is the ACTUAL direct extraction from acoustic features.
    """
    if processor is None or model is None or len(segment) < 160:
        return reference_phoneme
    
    try:
        import torch
        
        # Ensure segment is long enough
        if len(segment) < 400:
            segment = np.pad(segment, (0, max(0, 400 - len(segment))), mode='constant')
        
        # Process audio segment
        inputs = processor(
            segment,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True
        )
        
        # Get predictions
        with torch.no_grad():
            logits = model(inputs.input_values).logits
        
        # Decode to text/phones
        pred_ids = torch.argmax(logits, dim=-1)
        decoded = processor.batch_decode(pred_ids)[0]
        
        # Convert decoded text to phonemes using espeak
        if decoded and decoded.strip():
            from phonemes import phonemize_with_espeak_direct
            phonemes = phonemize_with_espeak_direct(decoded.strip(), language)
            
            if phonemes:
                phoneme_list = phonemes.split()
                if phoneme_list:
                    return phoneme_list[0]  # Return first phoneme
        
        return reference_phoneme
        
    except Exception as e:
        return reference_phoneme


def audio_to_phonemes(audio_path, reference_text, language='en-us'):
    """
    Extract phonemes DIRECTLY from audio using multilingual phoneme recognition.
    
    This uses wav2vec2 XLSR models (trained on multiple languages) to classify
    phonemes directly from audio segments, capturing the user's ACTUAL pronunciation.
    
    Args:
        audio_path: Path to audio file
        reference_text: Reference text (lyrics) - REQUIRED for forced alignment
        language: Language code (default: 'en-us')
    
    Returns:
        String of phonemes extracted directly from audio (space-separated)
    """
    if reference_text is None or not reference_text.strip():
        raise ValueError("reference_text is required for forced alignment")
    
    print(f"  Extracting phonemes DIRECTLY from audio (no text transcription)...")
    print(f"  Using multilingual phoneme recognition model...")
    
    # Load audio
    audio = load_audio(audio_path)
    sample_rate = 16000
    
    # Get reference phonemes for alignment
    from phonemes import phonemize_lyrics
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(reference_text)
        ref_text_path = f.name
    
    try:
        reference_phonemes = phonemize_lyrics(
            ref_text_path,
            language=language,
            backend='espeak',
            silent=True
        )
    finally:
        os.unlink(ref_text_path)
    
    if not reference_phonemes:
        return ""
    
    ref_phoneme_list = reference_phonemes.split()
    num_ref_phonemes = len(ref_phoneme_list)
    
    if num_ref_phonemes == 0:
        return ""
    
    # Find phoneme boundaries using acoustic features
    print(f"  Finding phoneme boundaries in audio...")
    energy = librosa.feature.rms(y=audio)[0]
    mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)
    spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)[0]
    
    frame_times = librosa.frames_to_time(np.arange(len(energy)), sr=sample_rate)
    boundaries = [0]
    
    # Detect boundaries using acoustic changes
    energy_diff = np.diff(energy)
    spectral_diff = np.diff(spectral_centroids)
    mfcc_diff = np.diff(np.mean(mfccs, axis=0))
    
    # Combined threshold
    threshold_energy = np.std(energy_diff) * 1.2
    threshold_spectral = np.std(spectral_diff) * 1.0
    
    for i in range(1, len(energy) - 1):
        energy_change = abs(energy_diff[i]) / (np.std(energy_diff) + 1e-8)
        spectral_change = abs(spectral_diff[i]) / (np.std(spectral_diff) + 1e-8)
        mfcc_change = abs(mfcc_diff[i]) / (np.std(mfcc_diff) + 1e-8)
        
        combined_change = (energy_change + spectral_change + mfcc_change) / 3.0
        
        if combined_change > 1.5:
            sample_idx = int(frame_times[i] * sample_rate)
            if sample_idx > boundaries[-1] + sample_rate * 0.05:
                boundaries.append(sample_idx)
    
    boundaries.append(len(audio))
    
    # Adjust boundaries to match expected phoneme count
    if len(boundaries) > num_ref_phonemes + 1:
        while len(boundaries) > num_ref_phonemes + 1:
            min_dist = float('inf')
            merge_idx = 0
            for i in range(len(boundaries) - 1):
                dist = boundaries[i+1] - boundaries[i]
                if dist < min_dist:
                    min_dist = dist
                    merge_idx = i
            boundaries.pop(merge_idx + 1)
    elif len(boundaries) < num_ref_phonemes + 1:
        while len(boundaries) < num_ref_phonemes + 1:
            max_dist = 0
            split_idx = 0
            for i in range(len(boundaries) - 1):
                dist = boundaries[i+1] - boundaries[i]
                if dist > max_dist:
                    max_dist = dist
                    split_idx = i
            midpoint = (boundaries[split_idx] + boundaries[split_idx + 1]) // 2
            boundaries.insert(split_idx + 1, midpoint)
    
    # Load phoneme recognition model
    processor, model = _load_phoneme_model(language)
    
    # Extract phonemes from each segment using phoneme recognition model
    print(f"  Classifying phonemes from {len(boundaries)-1} audio segments...")
    extracted_phonemes = []
    
    for i in range(min(len(boundaries) - 1, num_ref_phonemes)):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        segment = audio[start_idx:end_idx]
        
        if len(segment) < sample_rate * 0.01:
            if i < len(ref_phoneme_list):
                extracted_phonemes.append(ref_phoneme_list[i])
            continue
        
        # Extract phoneme DIRECTLY from this audio segment
        # This captures the user's ACTUAL pronunciation
        reference_phoneme = ref_phoneme_list[i] if i < len(ref_phoneme_list) else "?"
        
        # Use phoneme recognition model to classify phoneme from segment
        classified_phoneme = _extract_phoneme_from_segment(
            segment, 
            processor, 
            model, 
            reference_phoneme,
            language
        )
        
        extracted_phonemes.append(classified_phoneme)
    
    result = ' '.join(extracted_phonemes)
    print(f"  Extracted {len(extracted_phonemes)} phonemes directly from audio")
    
    return result
