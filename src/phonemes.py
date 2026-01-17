import os
import sys
import subprocess
from pathlib import Path

# Set PATH early to help phonemizer find espeak
# Check for espeak in common Homebrew locations
espeak_paths = ['/opt/homebrew/bin/espeak', '/usr/local/bin/espeak']
for espeak_path in espeak_paths:
    if Path(espeak_path).exists():
        espeak_dir = str(Path(espeak_path).parent)
        current_path = os.environ.get('PATH', '')
        if espeak_dir not in current_path:
            os.environ['PATH'] = f"{espeak_dir}:{current_path}"
        break

from phonemizer import phonemize
from phonemizer.backend import EspeakBackend, FestivalBackend
try:
    from phonemizer.backend import SegmentsBackend
    SEGMENTS_AVAILABLE = True
except ImportError:
    SEGMENTS_AVAILABLE = False
import argparse


def find_espeak_path():
    """Try to find espeak binary in common locations, especially Homebrew on macOS."""
    # Common Homebrew paths
    homebrew_paths = [
        '/opt/homebrew/bin/espeak',
        '/usr/local/bin/espeak',
        Path.home() / '.homebrew' / 'bin' / 'espeak',
    ]
    
    # Check if espeak is in PATH
    try:
        result = subprocess.run(['which', 'espeak'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    
    # Check common Homebrew locations
    for path in homebrew_paths:
        if Path(path).exists():
            return str(path)
    
    return None


def ensure_espeak_in_path():
    """Ensure espeak's directory is in PATH if espeak is found but not in PATH."""
    espeak_path = find_espeak_path()
    if espeak_path:
        espeak_dir = str(Path(espeak_path).parent)
        current_path = os.environ.get('PATH', '')
        if espeak_dir not in current_path:
            os.environ['PATH'] = f"{espeak_dir}:{current_path}"


def test_backend(backend_name, language='en-us'):
    """
    Test if a backend actually works by trying to phonemize a test string.
    Returns True if it works, False otherwise.
    """
    # Skip segments as it requires language profiles that may not be available
    if backend_name == 'segments':
        # Segments needs specific language profiles, so we'll skip it for now
        return False
    
    # If espeak, ensure it's in PATH
    if backend_name == 'espeak':
        ensure_espeak_in_path()
    
    try:
        # Try with a simple test language first (en-us works for most backends)
        test_language = 'en-us'
        test_result = phonemize(
            'test',
            language=test_language,
            backend=backend_name,
            preserve_punctuation=False,
            with_stress=False
        )
        # If we get a result, the backend works
        return bool(test_result)
    except Exception as e:
        # Suppress the error for now, but we'll try other backends
        return False


def get_available_backend(preferred_backend='espeak', language='en-us'):
    """
    Try to find an available backend for phonemization by actually testing it.
    Returns the backend name if available, None otherwise.
    """
    # Ensure espeak is in PATH before testing (if it exists)
    if preferred_backend == 'espeak':
        ensure_espeak_in_path()
    
    # Order: preferred backend, then festival (skip segments as it needs profiles)
    backends_to_try = [preferred_backend]
    if preferred_backend != 'festival':
        backends_to_try.append('festival')
    
    for backend_name in backends_to_try:
        if test_backend(backend_name, language):
            return backend_name
    
    return None


def phonemize_with_espeak_direct(text, language='en-us'):
    """
    Call espeak directly via subprocess to get phonemes.
    This bypasses phonemizer library's detection issues.
    """
    espeak_path = find_espeak_path()
    if not espeak_path:
        return None
    
    try:
        # Convert language code (fr-fr -> fr, en-us -> en)
        lang_code = language.split('-')[0] if '-' in language else language
        
        # Use espeak -x flag for phoneme output
        result = subprocess.run(
            [espeak_path, '-x', '-q', '-v', lang_code, text],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Clean up the output (remove extra whitespace)
            phonemes = result.stdout.strip()
            return phonemes
        return None
    except Exception:
        return None


def phonemize_lyrics(input_file, output_file=None, language='en-us', backend='espeak', silent=False):
    """
    Converts song lyrics from a text file to phonemes.
    
    Args:
        input_file: Path to the input text file containing lyrics
        output_file: Optional path to save the phoneme output (if None, prints to console unless silent=True)
        language: Language code for phonemization (default: 'en-us')
        backend: Backend to use for phonemization (default: 'espeak')
        silent: If True, don't print to console (default: False)
    """
    try:
        # Read the input file first
        with open(input_file, 'r', encoding='utf-8') as f:
            lyrics = f.read().strip()
        
        if not lyrics:
            print(f"Error: Input file '{input_file}' is empty.")
            return
        
        # Split into lines for processing
        lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        
        if not lines:
            print(f"Error: No lyrics found in '{input_file}'.")
            return
        
        # If espeak backend, try direct espeak first (most reliable)
        if backend == 'espeak':
            espeak_path = find_espeak_path()
            if espeak_path:
                # Use direct espeak call
                phoneme_lines = []
                for line in lines:
                    phonemes = phonemize_with_espeak_direct(line, language)
                    if phonemes:
                        phoneme_lines.append(phonemes)
                    else:
                        # Fallback to phonemizer if direct call fails
                        phonemes = phonemize(
                            line,
                            language=language,
                            backend=backend,
                            preserve_punctuation=False,
                            with_stress=False
                        )
                        phoneme_lines.append(phonemes)
            else:
                # Try phonemizer library as fallback
                available_backend = get_available_backend(backend, language)
                if available_backend is None:
                    print("Error: espeak not found and no other backend available.")
                    print("Please install espeak: brew install espeak (on macOS)")
                    sys.exit(1)
                backend = available_backend
                
                phoneme_lines = []
                for line in lines:
                    phonemes = phonemize(
                        line,
                        language=language,
                        backend=backend,
                        preserve_punctuation=False,
                        with_stress=False
                    )
                    phoneme_lines.append(phonemes)
        else:
            # For other backends, use phonemizer library
            available_backend = get_available_backend(backend, language)
            if available_backend is None:
                print(f"Error: Backend '{backend}' not available.")
                sys.exit(1)
            
            phoneme_lines = []
            for line in lines:
                phonemes = phonemize(
                    line,
                    language=language,
                    backend=available_backend,
                    preserve_punctuation=False,
                    with_stress=False
                )
                phoneme_lines.append(phonemes)
        
        # Join all phoneme lines
        phoneme_output = '\n'.join(phoneme_lines)
        
        # Output results
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(phoneme_output)
            if not silent:
                print(f"Phonemes saved to '{output_file}'")
        elif not silent:
            print("Phonemes:")
            print(phoneme_output)
            print()
        
        return phoneme_output
        
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    except RuntimeError as e:
        error_msg = str(e)
        if 'not installed' in error_msg.lower() or 'not available' in error_msg.lower():
            print(f"Error: {error_msg}")
            print("\nPlease install the required backend:")
            if 'espeak' in error_msg.lower():
                print("  macOS: brew install espeak")
                print("  Linux: sudo apt-get install espeak (or equivalent)")
            elif 'festival' in error_msg.lower():
                print("  macOS: brew install festival")
                print("  Linux: sudo apt-get install festival (or equivalent)")
        else:
            print(f"Error during phonemization: {error_msg}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during phonemization: {str(e)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Convert song lyrics from a text file to phonemes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python phonemes.py                    # Uses lyrics.txt by default
  python phonemes.py lyrics.txt         # Use a specific file
  python phonemes.py -o output.txt      # Save to file (uses lyrics.txt)
  python phonemes.py --language fr-fr   # French phonemes (uses lyrics.txt)
        """
    )
    
    parser.add_argument(
        'input_file',
        nargs='?',
        default='lyrics.txt',
        help='Path to the input text file containing lyrics (default: lyrics.txt)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        help='Path to save the phoneme output (optional, defaults to console)'
    )
    
    parser.add_argument(
        '-l', '--language',
        default='en-us',
        help='Language code for phonemization (default: en-us)'
    )
    
    parser.add_argument(
        '-b', '--backend',
        default='espeak',
        choices=['espeak', 'festival', 'segments'],
        help='Backend to use for phonemization (default: espeak). '
             'Note: "segments" requires no external binaries but has limited language support.'
    )
    
    args = parser.parse_args()
    
    phonemize_lyrics(
        input_file=args.input_file,
        output_file=args.output_file,
        language=args.language,
        backend=args.backend
    )


if __name__ == '__main__':
    main()
