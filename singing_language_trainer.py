"""
Singing Language Trainer
Integrates phoneme extraction, alignment, and pronunciation profiling
to help users improve their singing/pronunciation.
"""

import argparse
import sys
from pathlib import Path

# Import our modules
from phonemes import phonemize_lyrics
from user_phonemes import audio_to_phonemes
from aligner import phoneme_accuracy
from pronunciation_profile import UserPronunciationProfile


class SingingLanguageTrainer:
    """Main trainer class that coordinates all components."""
    
    def __init__(self, profile=None):
        """
        Initialize the trainer.
        
        Args:
            profile: Optional UserPronunciationProfile instance (creates new if None)
        """
        self.profile = profile if profile is not None else UserPronunciationProfile()
    
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
        # Get reference phonemes from lyrics
        print(f"Processing reference lyrics from: {lyrics_path}")
        reference_phonemes = phonemize_lyrics(
            input_file=lyrics_path,
            output_file=None,
            language=language,
            backend='espeak',
            silent=True  # Don't print to console
        )
        
        # Get user phonemes from audio
        print(f"Extracting phonemes from user audio: {audio_path}")
        user_phonemes = audio_to_phonemes(audio_path)
        
        # Calculate accuracy
        accuracy = phoneme_accuracy(reference_phonemes, user_phonemes)
        
        # Update pronunciation profile
        self.profile.update(reference_phonemes, user_phonemes)
        
        # Prepare results
        results = {
            'accuracy': accuracy,
            'reference_phonemes': reference_phonemes,
            'user_phonemes': user_phonemes,
            'weak_phonemes': self.profile.weak_phonemes(),
            'weighted_score': self.profile.weighted_score(reference_phonemes, user_phonemes)
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
    
    def print_feedback(self, results):
        """
        Print user-friendly feedback based on results.
        
        Args:
            results: Results dictionary from process_audio_and_lyrics
        """
        print("\n" + "="*60)
        print("PRONUNCIATION ANALYSIS")
        print("="*60)
        
        print(f"\nOverall Accuracy: {results['accuracy']:.2%}")
        print(f"Weighted Score: {results['weighted_score']:.2%}")
        
        if results['weak_phonemes']:
            print(f"\n⚠️  Weak Phonemes (need practice): {', '.join(results['weak_phonemes'])}")
        else:
            print("\n✓ All phonemes are within acceptable error rates!")
        
        print("\nReference Phonemes:")
        print(f"  {results['reference_phonemes']}")
        print("\nYour Phonemes:")
        print(f"  {results['user_phonemes']}")
        
        # Compare phoneme by phoneme
        ref_list = results['reference_phonemes'].split()
        user_list = results['user_phonemes'].split()
        
        if ref_list and user_list:
            print("\nPhoneme-by-Phoneme Comparison:")
            print("  (✓ = correct, ✗ = incorrect)")
            max_len = max(len(ref_list), len(user_list))
            
            for i in range(min(len(ref_list), len(user_list))):
                status = "✓" if ref_list[i] == user_list[i] else "✗"
                print(f"  [{i+1}] {status} Reference: {ref_list[i]:<10} Your: {user_list[i]}")
            
            if len(ref_list) != len(user_list):
                print(f"\n  Note: Different number of phonemes (ref: {len(ref_list)}, user: {len(user_list)})")
        
        if 'saved_files' in results:
            print(f"\nPhonemes saved to:")
            print(f"  Reference: {results['saved_files']['reference']}")
            print(f"  User: {results['saved_files']['user']}")
        
        print("\n" + "="*60)
    
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
