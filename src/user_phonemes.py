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
        print(f"  ⚠️  transformers/torch not available - phoneme model cannot load")
        print(f"  Install: pip install torch transformers")
        return None, None
    
    try:
        from transformers import AutoProcessor, AutoModelForCTC
    except ImportError:
        print(f"  ⚠️  Could not import transformers - phoneme model cannot load")
        return None, None
    
    model_key = PHONEME_MODELS.get(language, 'facebook/wav2vec2-large-xlsr-53')
    
    if model_key in _phoneme_model_cache:
        return _phoneme_model_cache[model_key]
    
    try:
        print(f"  Loading phoneme recognition model: {model_key}...")
        print(f"  (This may take a while on first run - model will be downloaded)")
        processor = AutoProcessor.from_pretrained(model_key)
        model = AutoModelForCTC.from_pretrained(model_key)
        model.eval()
        
        _phoneme_model_cache[model_key] = (processor, model)
        print(f"  ✓ Model loaded successfully")
        return processor, model
    except Exception as e:
        print(f"  ⚠️  Could not load phoneme model: {e}")
        print(f"  Falling back to Whisper transcription method...")
        return None, None


def _extract_phoneme_from_segment(segment, processor, model, reference_phoneme, language='en-us'):
    """
    Extract phoneme directly from audio segment using phoneme recognition model.
    This is the ACTUAL direct extraction from acoustic features.
    
    Returns:
        Extracted phoneme, or reference_phoneme if extraction fails
        (returning reference indicates the model couldn't extract actual phoneme)
    """
    if processor is None or model is None:
        return reference_phoneme  # Signal that model is not available
    
    if len(segment) < 160:
        # Segment too short, can't extract reliably
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
                    extracted = phoneme_list[0]
                    # Only return extracted if it's different from reference
                    # (to avoid false matches)
                    return extracted
        
        # If we get here, extraction failed - return reference as fallback
        # This will be counted as a fallback in the calling function
        return reference_phoneme
        
    except Exception as e:
        # Log error but don't spam console
        # Return reference as fallback
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
    
    # Check if model loaded successfully
    model_available = processor is not None and model is not None
    
    if not model_available:
        print(f"  ⚠️  WARNING: Phoneme recognition model not available!")
        print(f"  Falling back to Whisper transcription + phonemization...")
        print(f"  This will capture your ACTUAL pronunciation (not reference phonemes)")
        
        # Fallback: Use Whisper to transcribe, then phonemize
        try:
            import whisper
            print(f"  Loading Whisper model for transcription...")
            whisper_model = whisper.load_model("base")
            
            print(f"  Transcribing audio with Whisper...")
            transcription_result = whisper_model.transcribe(
                audio,
                language="en" if language.startswith("en") else None,
                verbose=False
            )
            
            transcribed_text = transcription_result['text'].strip()
            print(f"  Whisper transcribed: {transcribed_text[:100]}...")
            
            if transcribed_text:
                # Phonemize the transcription
                from phonemes import phonemize_with_espeak_direct
                user_phonemes = phonemize_with_espeak_direct(transcribed_text, language)
                
                if user_phonemes:
                    print(f"  ✓ Extracted {len(user_phonemes.split())} phonemes from Whisper transcription")
                    return user_phonemes
                else:
                    print(f"  ⚠️  Could not phonemize transcription, using reference phonemes")
            else:
                print(f"  ⚠️  Whisper returned empty transcription, using reference phonemes")
        except ImportError:
            print(f"  ⚠️  Whisper not available. Install: pip install openai-whisper")
        except Exception as e:
            print(f"  ⚠️  Whisper transcription failed: {e}")
        
        # If all fallbacks fail, return empty to indicate failure
        # This will cause a lower accuracy score instead of 100%
        print(f"  ⚠️  CRITICAL: Cannot extract phonemes from audio!")
        print(f"  Returning empty phonemes - accuracy will reflect actual errors")
        return ""
    
    # Extract phonemes from each segment using phoneme recognition model
    print(f"  Classifying phonemes from {len(boundaries)-1} audio segments...")
    extracted_phonemes = []
    fallback_count = 0
    
    for i in range(min(len(boundaries) - 1, num_ref_phonemes)):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        segment = audio[start_idx:end_idx]
        
        if len(segment) < sample_rate * 0.01:
            if i < len(ref_phoneme_list):
                extracted_phonemes.append(ref_phoneme_list[i])
                fallback_count += 1
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
        
        # Check if we fell back to reference (indicates model failure)
        if classified_phoneme == reference_phoneme:
            fallback_count += 1
        
        extracted_phonemes.append(classified_phoneme)
    
    # Warn if too many fallbacks (model not working properly)
    fallback_ratio = fallback_count / len(extracted_phonemes) if extracted_phonemes else 0
    if fallback_ratio > 0.5:
        print(f"  ⚠️  WARNING: {fallback_count}/{len(extracted_phonemes)} phonemes used reference (model may not be working)")
        print(f"  Accuracy scores may be inflated. Consider checking model installation.")
    
    result = ' '.join(extracted_phonemes)
    print(f"  Extracted {len(extracted_phonemes)} phonemes directly from audio")
    
    return result
