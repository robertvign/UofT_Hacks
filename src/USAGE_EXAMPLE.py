"""
Usage Example: Complete workflow with enhanced feedback, error dictionary, and lessons
"""

from singing_language_trainer import SingingLanguageTrainer
from pathlib import Path

# Initialize trainer with persistent profile
# This will load existing profile if it exists, or create a new one
trainer = SingingLanguageTrainer(profile_file='user_pronunciation_profile.json')

# Process audio and lyrics
print("Processing your singing...")
results = trainer.process_audio_and_lyrics(
    audio_path='stay_user_singing.mp3',
    lyrics_path='stay.txt',
    language='fr-fr'
)

# 1. Enhanced feedback - prints accuracy, struggling words/lines, successful ones
print("\n" + "="*70)
print("ENHANCED FEEDBACK")
print("="*70)
trainer.print_feedback(results)

# 2. Extract error dictionary - for relearning algorithm
print("\n" + "="*70)
print("ERROR DICTIONARY EXTRACTION")
print("="*70)
error_dict = trainer.get_error_dictionary()

print(f"\n📚 Your Error Dictionary:")
print(f"  • Weak words: {len(error_dict.get('weak_words', []))}")
print(f"  • Weak phonemes: {len(error_dict.get('weak_phonemes', {}))}")
print(f"  • Phoneme substitutions tracked: {len(error_dict.get('phoneme_substitutions', {}))}")

# Show top struggling words
if error_dict.get('weak_words'):
    print("\n  Top 5 Struggling Words:")
    for i, word_data in enumerate(error_dict['weak_words'][:5], 1):
        print(f"    {i}. {word_data['word']} (Error Rate: {word_data['error_rate']:.1%})")

# 3. Generate and play personalized lesson
print("\n" + "="*70)
print("PERSONALIZED LESSON GENERATION")
print("="*70)

# Generate lesson based on error dictionary
lesson_gen, lesson = trainer.generate_lesson(
    num_words=10,  # Top 10 struggling words
    num_lines=5,   # Top 5 struggling lines
    slow=False,    # Normal speed
    play=False     # Set to True to play audio (requires TTS)
)

# Print lesson content
lesson_gen.print_lesson(lesson)

# Optionally play the lesson
# Uncomment to play audio (requires: pip install gtts pygame)
# lesson_gen.play_lesson(lesson, practice_words=True, slow=False)

# Generate line lesson
line_lesson_gen, line_lesson = trainer.generate_line_lesson(
    results,
    num_lines=5,
    slow=False,
    play=False
)

# Save profile for persistence (accumulates over time)
trainer.save_profile('user_pronunciation_profile.json')
print(f"\n✅ Profile saved! This will accumulate as you sing more songs.")
print(f"   Next time you run this, it will load your existing profile and continue learning.")
