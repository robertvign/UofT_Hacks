"""
Lesson Generator
Creates personalized pronunciation lessons based on user's error dictionary.
Lessons focus on words/lines the user struggled with most.
"""

import os
from pathlib import Path
import json
from typing import List, Dict, Optional
import tempfile

# Try importing text-to-speech
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    from gtts import gTTS
    import pygame
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False


class LessonGenerator:
    """
    Generates personalized pronunciation lessons based on user's error dictionary.
    Lessons are completely customized to each user's unique accent profile.
    """
    
    def __init__(self, error_dictionary: Dict, language='en-us'):
        """
        Initialize lesson generator.
        
        Args:
            error_dictionary: Error dictionary from UserPronunciationProfile
            language: Language code (default: 'en-us')
        """
        self.error_dict = error_dictionary
        self.language = language
        self.lessons = []
    
    def generate_lesson(self, num_words=10, num_lines=5):
        """
        Generate a lesson focusing on words/lines user struggled with most.
        
        Args:
            num_words: Number of struggling words to include (default: 10)
            num_lines: Number of struggling lines to include (default: 5)
        
        Returns:
            Dictionary with lesson content
        """
        lesson = {
            'words': [],
            'lines': [],
            'phonemes': []
        }
        
        # Get top struggling words
        weak_words = self.error_dict.get('weak_words', [])
        if weak_words:
            lesson['words'] = weak_words[:num_words]
        
        # Get weak phonemes (for phoneme practice)
        weak_phonemes = self.error_dict.get('weak_phonemes', {})
        if weak_phonemes:
            # Sort by error rate
            sorted_phonemes = sorted(
                weak_phonemes.items(),
                key=lambda x: x[1].get('error_rate', 0),
                reverse=True
            )
            lesson['phonemes'] = [{'phoneme': p, **data} for p, data in sorted_phonemes[:10]]
        
        self.lessons.append(lesson)
        return lesson
    
    def print_lesson(self, lesson: Optional[Dict] = None):
        """
        Print lesson content to screen.
        
        Args:
            lesson: Optional lesson dict (uses last generated if None)
        """
        if lesson is None:
            if not self.lessons:
                print("No lesson generated yet. Call generate_lesson() first.")
                return
            lesson = self.lessons[-1]
        
        print("\n" + "="*70)
        print("📚 PERSONALIZED PRONUNCIATION LESSON")
        print("="*70)
        print("\nThis lesson is based on YOUR unique accent profile!")
        
        # Words section
        if lesson['words']:
            print("\n" + "-"*70)
            print(f"📝 WORDS TO PRACTICE ({len(lesson['words'])} words):")
            print("-"*70)
            for i, word_data in enumerate(lesson['words'], 1):
                error_rate = word_data.get('error_rate', 0)
                count = word_data.get('count', 0)
                print(f"\n{i}. {word_data['word']} (Error Rate: {error_rate:.1%}, Appeared {count} time(s))")
                print(f"   Expected: {word_data.get('ref_phonemes', 'N/A')}")
                print(f"   You often said: {word_data.get('common_user_phonemes', 'N/A')}")
        
        # Phonemes section
        if lesson['phonemes']:
            print("\n" + "-"*70)
            print(f"🔊 PHONEMES TO PRACTICE ({len(lesson['phonemes'])} phonemes):")
            print("-"*70)
            for i, phoneme_data in enumerate(lesson['phonemes'], 1):
                phoneme = phoneme_data.get('phoneme', '')
                error_rate = phoneme_data.get('error_rate', 0)
                substitution = phoneme_data.get('most_common_substitution', None)
                print(f"\n{i}. Phoneme: {phoneme} (Error Rate: {error_rate:.1%})")
                if substitution:
                    print(f"   You often substitute with: {substitution}")
        
        print("\n" + "="*70)
    
    def play_word_audio(self, word: str, language: Optional[str] = None, slow=False):
        """
        Play audio for a word using text-to-speech.
        
        Args:
            word: Word to play
            language: Language code (default: self.language)
            slow: Whether to speak slowly (default: False)
        """
        lang = language or self.language
        
        if GTTS_AVAILABLE:
            try:
                # Use gTTS (Google Text-to-Speech)
                lang_code = lang.split('-')[0] if '-' in lang else lang
                tts = gTTS(text=word, lang=lang_code, slow=slow)
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                    tmp_path = tmp.name
                    tts.save(tmp_path)
                
                # Play using pygame
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                
                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                
                # Clean up
                pygame.mixer.quit()
                os.unlink(tmp_path)
                
                print(f"  🔊 Played: {word}")
                return True
            except Exception as e:
                print(f"  Warning: Could not play audio for '{word}': {e}")
        
        elif TTS_AVAILABLE:
            try:
                # Use pyttsx3 (offline TTS)
                engine = pyttsx3.init()
                
                # Set language (if supported)
                voices = engine.getProperty('voices')
                for voice in voices:
                    if lang in voice.id.lower() or lang.split('-')[0] in voice.id.lower():
                        engine.setProperty('voice', voice.id)
                        break
                
                if slow:
                    rate = engine.getProperty('rate')
                    engine.setProperty('rate', rate - 50)  # Slower
                
                engine.say(word)
                engine.runAndWait()
                
                print(f"  🔊 Played: {word}")
                return True
            except Exception as e:
                print(f"  Warning: Could not play audio for '{word}': {e}")
        
        else:
            print(f"  ⚠️  No TTS available. Install: pip install gtts pygame OR pip install pyttsx3")
            return False
    
    def play_lesson(self, lesson: Optional[Dict] = None, practice_words=True, practice_phonemes=False, slow=False):
        """
        Play lesson audio - words and/or phonemes user struggled with.
        
        Args:
            lesson: Optional lesson dict (uses last generated if None)
            practice_words: Whether to practice words (default: True)
            practice_phonemes: Whether to practice phonemes (default: False)
            slow: Whether to speak slowly (default: False)
        """
        if lesson is None:
            if not self.lessons:
                print("No lesson generated yet. Call generate_lesson() first.")
                return
            lesson = self.lessons[-1]
        
        print("\n" + "="*70)
        print("🎧 PLAYING PRONUNCIATION LESSON")
        print("="*70)
        print("\nListen carefully to the correct pronunciation...\n")
        
        if practice_words and lesson['words']:
            print("📝 PRACTICING WORDS:")
            print("-"*70)
            for i, word_data in enumerate(lesson['words'], 1):
                word = word_data['word']
                print(f"\n[{i}/{len(lesson['words'])}] Practicing: {word}")
                self.play_word_audio(word, slow=slow)
                
                # Small pause between words
                import time
                time.sleep(0.5)
        
        if practice_phonemes and lesson['phonemes']:
            print("\n🔊 PRACTICING PHONEMES:")
            print("-"*70)
            # For phonemes, we'll use example words that contain them
            # This is a simplified approach - a full system would use IPA symbols
            print("  (Phoneme practice: Using example words containing these phonemes)")
            # Could implement phoneme-to-word mapping here
        
        print("\n✅ Lesson complete!")
        print("="*70)
    
    def generate_line_lesson(self, struggling_lines: List[Dict], num_lines=5):
        """
        Generate lesson for struggling lines.
        
        Args:
            struggling_lines: List of line dictionaries with 'text', 'accuracy', etc.
            num_lines: Number of lines to include (default: 5)
        
        Returns:
            Dictionary with line lesson content
        """
        line_lesson = {
            'lines': []
        }
        
        # Sort by accuracy (worst first)
        sorted_lines = sorted(struggling_lines, key=lambda x: x.get('accuracy', 0))
        line_lesson['lines'] = sorted_lines[:num_lines]
        
        return line_lesson
    
    def play_line_lesson(self, line_lesson: Dict, slow=False):
        """
        Play audio for struggling lines.
        
        Args:
            line_lesson: Line lesson dictionary
            slow: Whether to speak slowly (default: False)
        """
        if not line_lesson.get('lines'):
            print("No lines in lesson to play.")
            return
        
        print("\n" + "="*70)
        print("🎧 PLAYING LINE PRONUNCIATION LESSON")
        print("="*70)
        print("\nListen carefully to the correct pronunciation of these lines...\n")
        
        for i, line_data in enumerate(line_lesson['lines'], 1):
            line_text = line_data.get('text', '')
            accuracy = line_data.get('accuracy', 0)
            
            print(f"\n[{i}/{len(line_lesson['lines'])}] Line {line_data.get('line', i)} ({accuracy:.1%} accuracy):")
            print(f"  {line_text}")
            
            # Play the line
            self.play_word_audio(line_text, slow=slow)
            
            # Small pause between lines
            import time
            time.sleep(1.0)
        
        print("\n✅ Line lesson complete!")
        print("="*70)
    
    def save_lesson(self, lesson: Dict, output_file: str = 'pronunciation_lesson.json'):
        """Save lesson to file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(lesson, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Lesson saved to: {output_file}")
    
    def load_lesson(self, input_file: str) -> Dict:
        """Load lesson from file."""
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Lesson file not found: {input_file}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            lesson = json.load(f)
        
        self.lessons.append(lesson)
        return lesson


def create_lesson_from_results(trainer, num_words=10, num_lines=5):
    """
    Convenience function to create a lesson from trainer results.
    
    Args:
        trainer: SingingLanguageTrainer instance
        num_words: Number of words to include (default: 10)
        num_lines: Number of lines to include (default: 5)
    
    Returns:
        LessonGenerator instance
    """
    # Get error dictionary
    error_dict = trainer.get_error_dictionary()
    
    # Create lesson generator
    lesson_gen = LessonGenerator(error_dict, language='en-us')  # Could extract from trainer
    
    # Generate lesson
    lesson = lesson_gen.generate_lesson(num_words=num_words, num_lines=num_lines)
    
    return lesson_gen, lesson


def create_line_lesson_from_results(results: Dict, num_lines=5):
    """
    Create lesson for struggling lines from results.
    
    Args:
        results: Results dictionary from process_audio_and_lyrics
        num_lines: Number of lines to include (default: 5)
    
    Returns:
        LessonGenerator instance and line lesson
    """
    # Get struggling lines
    struggling_lines = [
        item for item in results.get('line_accuracies', [])
        if item.get('accuracy', 1.0) < 0.8
    ]
    
    # Create empty error dict (not needed for line lessons)
    lesson_gen = LessonGenerator({}, language='en-us')
    
    # Generate line lesson
    line_lesson = lesson_gen.generate_line_lesson(struggling_lines, num_lines=num_lines)
    
    return lesson_gen, line_lesson
