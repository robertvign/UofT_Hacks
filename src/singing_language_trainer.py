"""
Singing Language Trainer
Integrates phoneme extraction, alignment, and pronunciation profiling
to help users improve their singing/pronunciation.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

# Import our modules
try:
    # Try absolute imports first (if running from src/)
    from phonemes import phonemize_lyrics
    from user_phonemes import audio_to_phonemes
    from aligner import phoneme_accuracy
    from pronunciation_profile import UserPronunciationProfile
except ImportError:
    # Fallback to relative imports
    from .phonemes import phonemize_lyrics
    from .user_phonemes import audio_to_phonemes
    from .aligner import phoneme_accuracy
    from .pronunciation_profile import UserPronunciationProfile


class SingingLanguageTrainer:
    """Main trainer class that coordinates all components."""
    
    def __init__(self, profile=None, profile_file=None):
        """
        Initialize the trainer.
        
        Args:
            profile: Optional UserPronunciationProfile instance (creates new if None)
            profile_file: Optional path to save/load profile (for persistence)
        """
        if profile is not None:
            self.profile = profile
        else:
            self.profile = UserPronunciationProfile(profile_file=profile_file)
            if profile_file and Path(profile_file).exists():
                self.profile.load(profile_file)
    
    def process_audio_and_lyrics(self, audio_path, lyrics_path, language='en-us', 
                                 save_phonemes=False, output_dir=None):
        """
        Process user audio against reference lyrics.
        
        Args:
            audio_path: Path to user's audio file
            lyrics_path: Path to reference lyrics text file
            language: Language code for phonemization (default: 'en-us')
            save_phonemes: Whether to save phoneme outputs to files
            output_dir: Directory to save outputs (default: same as audio)
        
        Returns:
            dict with results including accuracy, phonemes, profile update
        """
        # Read lyrics file to get original lines
        with open(lyrics_path, 'r', encoding='utf-8') as f:
            lyrics_lines = [line.strip() for line in f.readlines() if line.strip()]
        
        # Get reference phonemes from lyrics (full text)
        print(f"Processing reference lyrics from: {lyrics_path}")
        reference_phonemes = phonemize_lyrics(
            input_file=lyrics_path,
            output_file=None,
            language=language,
            backend='espeak',
            silent=True  # Don't print to console
        )
        
        # Get reference phonemes per line
        ref_phoneme_lines = []
        for line in lyrics_lines:
            # Create temp file for this line
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                tmp.write(line)
                tmp_path = tmp.name
            
            try:
                line_phonemes = phonemize_lyrics(
                    input_file=tmp_path,
                    output_file=None,
                    language=language,
                    backend='espeak',
                    silent=True
                )
                ref_phoneme_lines.append(line_phonemes.strip() if line_phonemes else "")
            finally:
                Path(tmp_path).unlink()
        
        # Get user phonemes from audio using FORCED ALIGNMENT
        # This extracts phonemes DIRECTLY from audio (no text transcription)
        print(f"Extracting phonemes DIRECTLY from user audio: {audio_path}")
        print(f"  Using forced alignment to capture your ACTUAL pronunciation...")
        
        # Read the full lyrics text for forced alignment
        with open(lyrics_path, 'r', encoding='utf-8') as f:
            full_lyrics_text = f.read().strip()
        
        # Extract phonemes directly from audio using forced alignment
        user_phonemes = audio_to_phonemes(
            audio_path, 
            reference_text=full_lyrics_text,  # Required for forced alignment
            language=language
        )
        
        # Calculate overall accuracy
        accuracy = phoneme_accuracy(reference_phonemes, user_phonemes)
        
        # For line-by-line comparison, we'll do a simple split approach
        # Since audio is continuous, we approximate line boundaries
        user_phoneme_list = user_phonemes.split()
        total_ref_phonemes = len(reference_phonemes.split())
        
        # Extract word-level errors for each line
        word_errors_by_line = []
        for i, line_text in enumerate(lyrics_lines):
            line_words = line_text.split()
            if i < len(ref_phoneme_lines):
                ref_line_phonemes = ref_phoneme_lines[i]
                # Get user phonemes for this line
                ref_line_list = ref_line_phonemes.split()
                if ref_line_list and total_ref_phonemes > 0:
                    phonemes_per_ref = len(user_phoneme_list) / total_ref_phonemes
                    num_user_phonemes = int(len(ref_line_list) * phonemes_per_ref)
                    start_idx = int(sum(len(ref_phoneme_lines[j].split()) for j in range(i)) * phonemes_per_ref)
                    user_line_list = user_phoneme_list[start_idx:start_idx+num_user_phonemes] if start_idx < len(user_phoneme_list) else []
                    user_line_phonemes = ' '.join(user_line_list)
                else:
                    user_line_phonemes = ""
                
                # Update profile with word-level tracking
                self.profile.update(ref_line_phonemes, user_line_phonemes, words=line_words, line_text=line_text)
                
                # Analyze word-level errors for this line
                word_errors = self._analyze_word_errors(line_words, ref_line_phonemes, user_line_phonemes)
                word_errors_by_line.append({
                    'line': i+1,
                    'text': line_text,
                    'word_errors': word_errors
                })
        
        # Update pronunciation profile (phoneme-level)
        self.profile.update(reference_phonemes, user_phonemes)
        
        # Approximate line-by-line by dividing phonemes proportionally
        line_accuracies = []
        
        if total_ref_phonemes > 0:
            phonemes_per_ref = len(user_phoneme_list) / total_ref_phonemes
            current_idx = 0
            
            for i, ref_line_phonemes in enumerate(ref_phoneme_lines):
                ref_line_list = ref_line_phonemes.split()
                if not ref_line_list:
                    line_accuracies.append({'line': i+1, 'text': lyrics_lines[i], 'accuracy': 1.0})
                    continue
                
                # Approximate how many user phonemes correspond to this line
                num_user_phonemes = int(len(ref_line_list) * phonemes_per_ref)
                user_line_list = user_phoneme_list[current_idx:current_idx+num_user_phonemes] if current_idx < len(user_phoneme_list) else []
                current_idx += num_user_phonemes
                
                # Compare this line
                ref_line_str = ' '.join(ref_line_list)
                user_line_str = ' '.join(user_line_list) if user_line_list else ""
                line_acc = phoneme_accuracy(ref_line_str, user_line_str)
                
                line_accuracies.append({
                    'line': i+1,
                    'text': lyrics_lines[i],
                    'accuracy': line_acc,
                    'ref_phonemes': ref_line_str,
                    'user_phonemes': user_line_str
                })
        
        # Prepare results
        results = {
            'accuracy': accuracy,
            'reference_phonemes': reference_phonemes,
            'user_phonemes': user_phonemes,
            'weak_phonemes': self.profile.weak_phonemes(),
            'weighted_score': self.profile.weighted_score(reference_phonemes, user_phonemes),
            'line_accuracies': line_accuracies,
            'lyrics_lines': lyrics_lines,
            'word_errors_by_line': word_errors_by_line
        }
        
        # Save phonemes if requested
        if save_phonemes:
            output_dir = output_dir or Path(audio_path).parent
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            ref_file = output_dir / f"{Path(lyrics_path).stem}_reference_phonemes.txt"
            user_file = output_dir / f"{Path(audio_path).stem}_user_phonemes.txt"
            
            ref_file.write_text(reference_phonemes)
            user_file.write_text(user_phonemes)
            
            results['saved_files'] = {
                'reference': str(ref_file),
                'user': str(user_file)
            }
        
        return results
    
    def _analyze_word_errors(self, words, ref_phonemes, user_phonemes):
        """
        Analyze which words in a line have pronunciation errors.
        
        Args:
            words: List of words in the line
            ref_phonemes: Reference phonemes for the line
            user_phonemes: User phonemes for the line
        
        Returns:
            List of word error dictionaries
        """
        ref_phoneme_list = ref_phonemes.split()
        user_phoneme_list = user_phonemes.split()
        
        if not words or not ref_phoneme_list:
            return []
        
        word_errors = []
        phonemes_per_word = len(ref_phoneme_list) / len(words) if words else 0
        
        for i, word in enumerate(words):
            # Get phonemes for this word
            start_idx = int(i * phonemes_per_word)
            end_idx = int((i + 1) * phonemes_per_word) if i < len(words) - 1 else len(ref_phoneme_list)
            
            ref_word_phonemes = ' '.join(ref_phoneme_list[start_idx:end_idx])
            user_word_phonemes = ' '.join(user_phoneme_list[start_idx:end_idx]) if start_idx < len(user_phoneme_list) else ""
            
            # Calculate accuracy for this word
            try:
                from aligner import phoneme_accuracy
            except ImportError:
                from .aligner import phoneme_accuracy
            word_accuracy = phoneme_accuracy(ref_word_phonemes, user_word_phonemes)
            
            word_errors.append({
                'word': word,
                'accuracy': word_accuracy,
                'ref_phonemes': ref_word_phonemes,
                'user_phonemes': user_word_phonemes,
                'has_error': ref_word_phonemes != user_word_phonemes
            })
        
        return word_errors
    
    def print_feedback(self, results):
        """
        Enhanced feedback function that prints:
        1. User's overall accuracy
        2. Lines/words they struggled with (including %)
        3. Successful words/lines (including %)
        
        Args:
            results: Results dictionary from process_audio_and_lyrics
        """
        print("\n" + "="*70)
        print("PRONUNCIATION ANALYSIS")
        print("="*70)
        
        # Overall accuracy
        print(f"\nOVERALL ACCURACY: {results['accuracy']:.2%}")
        print(f"Weighted Score: {results['weighted_score']:.2%}")
        
        # Word-level analysis
        print("\n" + "="*70)
        print("WORD-LEVEL ANALYSIS")
        print("="*70)
        
        struggling_words = []
        successful_words = []
        
        if 'word_errors_by_line' in results:
            for line_data in results['word_errors_by_line']:
                for word_error in line_data['word_errors']:
                    if word_error['has_error']:
                        struggling_words.append({
                            'word': word_error['word'],
                            'accuracy': word_error['accuracy'],
                            'line': line_data['line'],
                            'line_text': line_data['text'],
                            'ref_phonemes': word_error['ref_phonemes'],
                            'user_phonemes': word_error['user_phonemes']
                        })
                    else:
                        successful_words.append({
                            'word': word_error['word'],
                            'accuracy': word_error['accuracy'],
                            'line': line_data['line']
                        })
        
        # Show struggling words
        if struggling_words:
            print("\nWORDS YOU STRUGGLED WITH (low accuracy):")
            print("-" * 70)
            # Sort by accuracy (worst first)
            struggling_words.sort(key=lambda x: x['accuracy'])
            
            for word_data in struggling_words[:20]:  # Top 20 worst
                accuracy_bar = "█" * int(word_data['accuracy'] * 15) + "░" * (15 - int(word_data['accuracy'] * 15))
                print(f"\n  • {word_data['word']}: {word_data['accuracy']:.1%} {accuracy_bar}")
                print(f"    Line {word_data['line']}: {word_data['line_text']}")
                print(f"    Expected: {word_data['ref_phonemes'][:50]}")
                print(f"    You said: {word_data['user_phonemes'][:50]}")
        else:
            print("\nNo struggling words found!")
        
        # Show successful words
        if successful_words:
            print(f"\nWORDS YOU PRONOUNCED CORRECTLY:")
            print("-" * 70)
            # Group by word
            from collections import defaultdict
            word_success = defaultdict(list)
            for word_data in successful_words:
                word_success[word_data['word']].append(word_data)
            
            # Show successful words
            for word, occurrences in list(word_success.items())[:15]:  # Top 15
                avg_accuracy = sum(w['accuracy'] for w in occurrences) / len(occurrences)
                print(f"  ✓ {word}: {avg_accuracy:.1%} (appears {len(occurrences)} time(s))")
        
        # Line-level analysis
        print("\n" + "="*70)
        print("LINE-BY-LINE ANALYSIS")
        print("="*70)
        
        if 'line_accuracies' in results and results['line_accuracies']:
            sorted_lines = sorted(results['line_accuracies'], key=lambda x: x['accuracy'])
            
            struggling_lines = [item for item in sorted_lines if item['accuracy'] < 0.8]
            successful_lines = [item for item in sorted_lines if item['accuracy'] >= 0.8]
            
            print(f"\nLINES YOU STRUGGLED WITH ({len(struggling_lines)} lines, < 80% accuracy):")
            print("-" * 70)
            for item in struggling_lines:
                accuracy_bar = "█" * int(item['accuracy'] * 20) + "░" * (20 - int(item['accuracy'] * 20))
                print(f"\n  Line {item['line']}: {item['accuracy']:.1%} {accuracy_bar}")
                print(f"    {item['text']}")
            
            print(f"\nLINES YOU DID WELL ON ({len(successful_lines)} lines, ≥ 80% accuracy):")
            print("-" * 70)
            for item in successful_lines[:10]:  # Show top 10
                accuracy_bar = "█" * int(item['accuracy'] * 20) + "░" * (20 - int(item['accuracy'] * 20))
                print(f"  Line {item['line']}: {item['accuracy']:.1%} {accuracy_bar} - {item['text']}")
        
        # Weak phonemes summary
        if results['weak_phonemes']:
            print(f"\nWeak Phonemes (need practice): {', '.join(results['weak_phonemes'][:15])}")
        
        print("\n" + "="*70)
    
    def get_error_dictionary(self):
        """
        Extract error dictionary for relearning algorithm.
        Returns dictionary of user mistakes that accumulates over time.
        
        Returns:
            Dictionary with error patterns including:
            - weak_phonemes: Phonemes user struggles with
            - weak_words: Words user struggles with (sorted by error rate)
            - phoneme_substitutions: Which phonemes user substitutes
        """
        return self.profile.get_error_dictionary()
    
    def save_profile(self, profile_file='user_pronunciation_profile.json'):
        """Save pronunciation profile to file."""
        self.profile.profile_file = profile_file
        self.profile.save(profile_file)
        print(f"✓ Pronunciation profile saved to: {profile_file}")
    
    def load_profile(self, profile_file='user_pronunciation_profile.json'):
        """Load pronunciation profile from file."""
        if Path(profile_file).exists():
            self.profile.load(profile_file)
            print(f"✓ Pronunciation profile loaded from: {profile_file}")
        else:
            print(f"  No existing profile found, starting fresh profile")
    
    def generate_lesson(self, num_words=10, num_lines=5, slow=False, play=True):
        """
        Generate and play a personalized lesson based on user's error dictionary.
        
        Args:
            num_words: Number of struggling words to include (default: 10)
            num_lines: Number of struggling lines to include (default: 5)
            slow: Whether to speak slowly (default: False)
            play: Whether to play audio (default: True)
        
        Returns:
            Lesson generator and lesson dictionary
        """
        try:
            from lesson_generator import LessonGenerator, create_lesson_from_results
        except ImportError:
            from .lesson_generator import LessonGenerator, create_lesson_from_results
        
        # Create lesson from error dictionary
        lesson_gen, lesson = create_lesson_from_results(self, num_words=num_words, num_lines=num_lines)
        
        # Print lesson
        lesson_gen.print_lesson(lesson)
        
        # Play lesson if requested
        if play:
            try:
                lesson_gen.play_lesson(lesson, practice_words=True, practice_phonemes=False, slow=slow)
            except Exception as e:
                print(f"\nCould not play lesson audio: {e}")
                print("  Install TTS: pip install gtts pygame OR pip install pyttsx3")
        
        return lesson_gen, lesson
    
    def generate_line_lesson(self, results: Dict, num_lines=5, slow=False, play=True):
        """
        Generate and play a lesson for struggling lines.
        
        Args:
            results: Results dictionary from process_audio_and_lyrics
            num_lines: Number of lines to include (default: 5)
            slow: Whether to speak slowly (default: False)
            play: Whether to play audio (default: True)
        
        Returns:
            Lesson generator and line lesson dictionary
        """
        try:
            from lesson_generator import create_line_lesson_from_results
        except ImportError:
            from .lesson_generator import create_line_lesson_from_results
        
        # Create line lesson
        lesson_gen, line_lesson = create_line_lesson_from_results(results, num_lines=num_lines)
        
        # Print lesson
        print("\n" + "="*70)
        print("LINE PRONUNCIATION LESSON")
        print("="*70)
        print(f"\nThis lesson focuses on {len(line_lesson['lines'])} lines you struggled with:\n")
        
        for i, line_data in enumerate(line_lesson['lines'], 1):
            accuracy = line_data.get('accuracy', 0)
            print(f"{i}. Line {line_data.get('line', i)} ({accuracy:.1%} accuracy):")
            print(f"   {line_data.get('text', '')}")
        
        # Play lesson if requested
        if play:
            try:
                lesson_gen.play_line_lesson(line_lesson, slow=slow)
            except Exception as e:
                print(f"\nCould not play lesson audio: {e}")
                print("  Install TTS: pip install gtts pygame OR pip install pyttsx3")
        
        return lesson_gen, line_lesson
    
    def get_profile_summary(self):
        """Get a summary of the user's pronunciation profile."""
        weak = self.profile.weak_phonemes()
        total_phonemes = len(self.profile.total_counts)
        
        summary = {
            'total_phonemes_tracked': total_phonemes,
            'weak_phonemes': weak,
            'weak_phoneme_count': len(weak),
            'error_rates': {}
        }
        
        for phoneme in self.profile.total_counts:
            if self.profile.total_counts[phoneme] > 0:
                error_rate = self.profile.error_counts[phoneme] / self.profile.total_counts[phoneme]
                summary['error_rates'][phoneme] = error_rate
        
        return summary


def main():
    """Command-line interface for the singing language trainer."""
    parser = argparse.ArgumentParser(
        description='Singing Language Trainer - Analyze pronunciation using phonemes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python singing_language_trainer.py user_audio.wav lyrics.txt
  python singing_language_trainer.py user_audio.wav lyrics.txt --language fr-fr
  python singing_language_trainer.py user_audio.wav lyrics.txt --save-phonemes
        """
    )
    
    parser.add_argument(
        'audio_path',
        help='Path to user audio file'
    )
    
    parser.add_argument(
        'lyrics_path',
        help='Path to reference lyrics text file'
    )
    
    parser.add_argument(
        '-l', '--language',
        default='en-us',
        help='Language code for phonemization (default: en-us)'
    )
    
    parser.add_argument(
        '-s', '--save-phonemes',
        action='store_true',
        help='Save phoneme outputs to text files'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        help='Directory to save outputs (default: same as audio file)'
    )
    
    parser.add_argument(
        '--profile-summary',
        action='store_true',
        help='Show pronunciation profile summary'
    )
    
    args = parser.parse_args()
    
    # Validate input files
    if not Path(args.audio_path).exists():
        print(f"Error: Audio file not found: {args.audio_path}")
        sys.exit(1)
    
    if not Path(args.lyrics_path).exists():
        print(f"Error: Lyrics file not found: {args.lyrics_path}")
        sys.exit(1)
    
    # Create trainer and process
    trainer = SingingLanguageTrainer()
    
    try:
        results = trainer.process_audio_and_lyrics(
            audio_path=args.audio_path,
            lyrics_path=args.lyrics_path,
            language=args.language,
            save_phonemes=args.save_phonemes,
            output_dir=args.output_dir
        )
        
        # Print feedback
        trainer.print_feedback(results)
        
        # Print profile summary if requested
        if args.profile_summary:
            summary = trainer.get_profile_summary()
            print("\n" + "="*60)
            print("PRONUNCIATION PROFILE SUMMARY")
            print("="*60)
            print(f"\nTotal phonemes tracked: {summary['total_phonemes_tracked']}")
            print(f"Weak phonemes: {summary['weak_phoneme_count']}")
            if summary['weak_phonemes']:
                print(f"  {', '.join(summary['weak_phonemes'])}")
        
    except Exception as e:
        print(f"Error during processing: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
