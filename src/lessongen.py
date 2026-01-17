"""
Conversational Lesson Generator
Uses Backboard to generate personalized conversational lessons based on error words
from user profile. Prompts user to practice pronunciation by speaking responses.
"""

import os
import json
import asyncio
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional
from backboard import BackboardClient

# Try importing audio recording libraries
try:
    import pyaudio
    import wave
    RECORDING_AVAILABLE = True
except ImportError:
    RECORDING_AVAILABLE = False
    print("⚠️  Audio recording not available. Install: pip install pyaudio")

# Try importing audio conversion library
try:
    from pydub import AudioSegment
    MP3_CONVERSION_AVAILABLE = True
except ImportError:
    MP3_CONVERSION_AVAILABLE = False
    # Don't print warning here, only when user tries to convert


class LessonGenerator:
    """
    Generates conversational lessons based on user's error words.
    Uses Backboard to create natural question-response pairs.
    """
    
    def __init__(self, profile_path: str = "user_profile.json"):
        """
        Initialize lesson generator with user profile.
        
        Args:
            profile_path: Path to user_profile.json file
        """
        self.profile_path = Path(profile_path)
        self.error_words = []
        self.conversations = []
        
        # Load error words from profile
        self._load_error_words()
    
    def _load_error_words(self):
        """Load words with errors from user profile."""
        if not self.profile_path.exists():
            raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        
        with open(self.profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
        
        # Extract words with errors (error_rate > 0)
        word_errors = profile.get('word_errors', {})
        self.error_words = [
            {
                'word': word,
                'error_rate': data.get('error_rate', 0),
                'count': data.get('count', 0),
                'ref_phonemes': data.get('ref_phonemes', '')
            }
            for word, data in word_errors.items()
            if data.get('error_rate', 0) > 0
        ]
        
        # Sort by error rate (highest first)
        self.error_words.sort(key=lambda x: x['error_rate'], reverse=True)
    
    def get_top_error_words(self, num: int = 3) -> List[Dict]:
        """
        Get top N error words to practice.
        
        Args:
            num: Number of words to return
            
        Returns:
            List of word dictionaries
        """
        return self.error_words[:num]
    
    async def generate_conversations(
        self,
        client: BackboardClient,
        assistant_id: str,
        num_conversations: int = 3
    ) -> List[Dict]:
        """
        Generate conversational Q&A pairs using Backboard.
        Responses will include error words for practice.
        
        Args:
            client: BackboardClient instance
            assistant_id: Backboard assistant ID
            num_conversations: Number of conversations to generate
            
        Returns:
            List of conversation dictionaries with 'question' and 'response'
        """
        # Get top error words
        top_words = self.get_top_error_words(num_conversations)
        
        if not top_words:
            print("No error words found in profile. Cannot generate lessons.")
            return []
        
        conversations = []
        
        for word_data in top_words:
            target_word = word_data['word']
            error_rate = word_data['error_rate']
            
            # Generate question and response using Backboard
            # First, generate the question
            question_prompt = f"""You are a friendly pronunciation coach.

Generate ONE short, natural conversational question that encourages someone to use the word "{target_word}" in their answer.

Rules:
- Question only (no explanations)
- Casual, everyday language
- Must naturally lead to using "{target_word}" in the response
- Keep it simple and conversational"""

            # Then generate the response that includes the target word
            response_prompt = f"""You are helping someone practice pronunciation.

Generate a natural conversational response that MUST include the word "{target_word}".

The response should:
- Be 1-2 sentences
- Sound natural and conversational
- Naturally include "{target_word}"
- Answer a question someone might ask about {target_word}"""

            try:
                # Create a thread for generating the question
                question_thread = await client.create_thread(assistant_id)
                
                # Generate question
                question_response = await client.add_message(
                    thread_id=question_thread.thread_id,
                    content=question_prompt,
                    llm_provider="google",
                    model_name="gemini-2.5-flash",
                    stream=False
                )
                question_text = question_response.content.strip()
                # Clean up question (remove quotes, etc.)
                question_text = question_text.strip(' "\'').strip()
                if not question_text or not question_text.endswith('?'):
                    # Fallback if question generation fails
                    question_text = f"Can you tell me about {target_word}?"
                
                # Create a new thread for generating the response
                response_thread = await client.create_thread(assistant_id)
                response_obj = await client.add_message(
                    thread_id=response_thread.thread_id,
                    content=response_prompt,
                    llm_provider="google",
                    model_name="gemini-2.5-flash",
                    stream=False
                )
                response_text = response_obj.content.strip()
                # Clean up response
                response_text = response_text.strip(' "\'').strip()
                
                # Ensure target word is in response
                if target_word.lower() not in response_text.lower():
                    response_text = f"Here's an example with {target_word}: {response_text}"
                
                conversations.append({
                    "question": question_text,
                    "response": response_text,
                    "target_word": target_word,
                    "error_rate": error_rate,
                    "count": word_data['count']
                })
                
                print(f"✓ Generated conversation for word: {target_word}")
                
            except Exception as e:
                print(f"✗ Error generating conversation for '{target_word}': {e}")
                # Create a fallback conversation
                conversations.append({
                    "question": f"Can you use the word '{target_word}' in a sentence?",
                    "response": f"Here's an example with '{target_word}' in it.",
                    "target_word": target_word,
                    "error_rate": error_rate,
                    "count": word_data['count']
                })
        
        self.conversations = conversations
        return conversations
    
    def print_lesson(self):
        """Print the generated lesson to console."""
        if not self.conversations:
            print("No conversations generated yet. Call generate_conversations() first.")
            return
        
        print("\n" + "="*70)
        print("💬 CONVERSATIONAL PRONUNCIATION LESSON")
        print("="*70)
        print(f"\nPracticing {len(self.conversations)} words you struggled with:\n")
        
        for i, conv in enumerate(self.conversations, 1):
            print(f"{i}. Target Word: {conv['target_word']} (Error Rate: {conv['error_rate']:.1%})")
            print(f"   Q: {conv['question']}")
            print(f"   A: {conv['response']}")
            print()
        
        print("="*70)
    
    def record_audio(self, duration: float = None, output_file: str = None, convert_to_mp3: bool = False) -> Optional[str]:
        """
        Record audio from microphone.
        
        Args:
            duration: Recording duration in seconds (None = record until stopped)
            output_file: Path to save recording (None = auto-generate temp file)
            convert_to_mp3: Whether to convert to MP3 format (default: False)
            
        Returns:
            Path to recorded audio file, or None if recording failed
        """
        if not RECORDING_AVAILABLE:
            print("⚠️  Audio recording not available. Install: pip install pyaudio")
            return None
        
        # Audio settings
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        # Generate output filename if not provided
        if output_file is None:
            import tempfile
            suffix = '.mp3' if convert_to_mp3 else '.wav'
            output_file = tempfile.mktemp(suffix=suffix, prefix='practice_')
        
        # If converting to MP3, record to temporary WAV first
        temp_wav = None
        if convert_to_mp3:
            import tempfile
            temp_wav = tempfile.mktemp(suffix='.wav', prefix='practice_temp_')
            actual_output = temp_wav
        else:
            actual_output = output_file
        
        audio = pyaudio.PyAudio()
        frames = []
        recording = True
        stream = None
        
        def record_audio_thread():
            nonlocal frames, recording, stream
            try:
                stream = audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                print("🎤 Recording... (speak now)")
                start_time = time.time()
                
                while recording:
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        frames.append(data)
                    except Exception as e:
                        if recording:  # Only print error if we're still supposed to be recording
                            print(f"⚠️  Recording error: {e}")
                        break
                    
                    if duration and (time.time() - start_time) >= duration:
                        break
            except Exception as e:
                print(f"⚠️  Error in recording thread: {e}")
            finally:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
        
        try:
            # Start recording in a separate thread
            record_thread = threading.Thread(target=record_audio_thread, daemon=True)
            record_thread.start()
            
            # Small delay to let recording start
            time.sleep(0.1)
            
            # Wait for user to stop or duration to elapse
            if duration:
                time.sleep(duration)
                recording = False
            else:
                input("\nPress ENTER to stop recording...")
                recording = False
            
            # Wait for recording thread to finish
            record_thread.join(timeout=3)
            
            if not frames:
                print("⚠️  No audio recorded")
                try:
                    audio.terminate()
                except:
                    pass
                return None
            
            # Get sample size before terminating
            sample_width = audio.get_sample_size(FORMAT)
            
            # Clean up audio
            try:
                audio.terminate()
            except:
                pass
            
            # Save recording to file
            wf = wave.open(output_file, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            print(f"✓ Recording saved to: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"✗ Error recording audio: {e}")
            recording = False
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
                audio.terminate()
            except:
                pass
            return None
    
    def prompt_user_practice(self, conv_index: int = None, save_recordings: bool = False, save_as_mp3: bool = False):
        """
        Prompt user to speak a response from the lesson.
        
        Args:
            conv_index: Index of conversation to practice (default: None, loops through all)
            save_recordings: Whether to save audio recordings (default: False)
            save_as_mp3: Whether to save as MP3 format (default: False, saves as WAV)
        """
        if not self.conversations:
            print("No conversations generated. Call generate_conversations() first.")
            return
        
        if conv_index is not None:
            conversations_to_practice = [self.conversations[conv_index]]
        else:
            conversations_to_practice = self.conversations
        
        print("\n" + "="*70)
        print("🎤 PRACTICE TIME - Speak the responses!")
        print("="*70)
        
        if not RECORDING_AVAILABLE:
            print("\n⚠️  Audio recording not available.")
            print("   Install pyaudio: pip install pyaudio")
            print("   (On Windows, you may need: pip install pipwin && pipwin install pyaudio)")
            print("   Continuing without recording...\n")
        
        recordings = []
        
        for i, conv in enumerate(conversations_to_practice, 1):
            print(f"\n[{i}/{len(conversations_to_practice)}]")
            print(f"Question: {conv['question']}")
            print(f"\nTarget word to practice: '{conv['target_word']}'")
            print(f"Response (try to say this naturally):")
            print(f"  {conv['response']}")
            
            user_input = input("\nPress ENTER when you're ready to practice, or type 'skip' to continue...")
            if user_input.lower() == 'skip':
                print("⏭️  Skipped this conversation")
                continue
            
            # Record audio
            if RECORDING_AVAILABLE:
                recording_path = self.record_audio(duration=None, convert_to_mp3=save_as_mp3)  # Record until user stops
                if recording_path:
                    recordings.append({
                        'conversation': conv,
                        'recording_path': recording_path
                    })
                    print("✓ Practice complete for this conversation!")
                else:
                    print("⚠️  Recording failed, but continuing...")
            else:
                print("\n🎤 Speak now! (Recording not available)")
                input("Press ENTER when you've finished speaking...")
                print("✓ Practice complete for this conversation!")
        
        print("\n" + "="*70)
        print("✅ Lesson complete! Great job practicing!")
        
        if recordings and save_recordings:
            print(f"\n📁 Recordings saved ({len(recordings)} files):")
            for rec in recordings:
                print(f"   - {rec['recording_path']}")
        elif recordings:
            print(f"\n💡 Tip: Set save_recordings=True to keep your practice recordings")
        
        print("="*70)


def get_backboard_credentials(raise_on_missing: bool = True):
    """
    Get Backboard credentials from environment variables.
    Works for both local development and web deployment.
    
    Args:
        raise_on_missing: Whether to raise an error if credentials are missing (default: True)
        
    Returns:
        tuple: (api_key, assistant_id) or (None, None) if not found and raise_on_missing=False
        
    Raises:
        ValueError: If credentials are missing or invalid and raise_on_missing=True
    """
    api_key = os.getenv("BACKBOARD_API_KEY")
    assistant_id = os.getenv("BACKBOARD_ASSISTANT_ID")
    
    # Validate assistant_id format (should be a UUID, typically 32 chars without dashes or 36 with)
    if assistant_id:
        # Remove any whitespace
        assistant_id = assistant_id.strip()
        # Check if it looks like a valid UUID (32 chars without dashes, or 36 with dashes)
        if len(assistant_id) not in [32, 36]:
            error_msg = (
                f"BACKBOARD_ASSISTANT_ID appears to be invalid. "
                f"Expected a UUID (32 or 36 characters), but got {len(assistant_id)} characters. "
                f"Value: '{assistant_id[:20]}...' (truncated)"
            )
            if raise_on_missing:
                raise ValueError(error_msg)
            else:
                return None, None
    
    if not api_key or not assistant_id:
        # Only show debug info in development (when running as script)
        if __name__ == "__main__":
            print("\n⚠️  Environment variable check:")
            print(f"  BACKBOARD_API_KEY: {'✅ Set' if api_key else '❌ Not set'}")
            if api_key:
                print(f"    Value: {api_key[:10]}... (truncated)")
            
            print(f"  BACKBOARD_ASSISTANT_ID: {'✅ Set' if assistant_id else '❌ Not set'}")
            if assistant_id:
                print(f"    Value: '{assistant_id}' (length: {len(assistant_id)})")
                if len(assistant_id) not in [32, 36]:
                    print(f"    ⚠️  WARNING: Expected UUID format (32 or 36 chars), got {len(assistant_id)} chars")
            
            # Show all backboard-related env vars for debugging
            backboard_vars = {k: v[:20] + "..." if len(v) > 20 else v 
                             for k, v in os.environ.items() 
                             if 'backboard' in k.lower() or 'board' in k.lower() or 'assistant' in k.lower()}
            if backboard_vars:
                print(f"\n  Found related environment variables:")
                for k, v in backboard_vars.items():
                    print(f"    {k}: {v}")
            
            print("\n  To set in PowerShell (local), use:")
            print('    $env:BACKBOARD_API_KEY = "your_api_key"')
            print('    $env:BACKBOARD_ASSISTANT_ID = "your_assistant_id"')
            print("  Note: assistant_id should be a UUID (32 or 36 characters)")
            print("\n  For web deployment, set environment variables in your hosting platform:")
            print("    - Heroku: heroku config:set BACKBOARD_API_KEY=your_key")
            print("    - AWS: Use AWS Systems Manager Parameter Store or Secrets Manager")
            print("    - Docker: Use -e flags or .env file")
            print("    - Other: Set in your platform's environment variable settings")
        
        if raise_on_missing:
            if not api_key:
                raise ValueError("BACKBOARD_API_KEY environment variable not set")
            if not assistant_id:
                raise ValueError("BACKBOARD_ASSISTANT_ID environment variable not set")
        else:
            return None, None
    
    return api_key, assistant_id


async def main():
    """Main function to run the lesson generator."""
    # Get credentials from environment variables
    api_key, assistant_id = get_backboard_credentials()
    
    # Initialize client
    client = BackboardClient(api_key=api_key)
    
    # Create lesson generator
    print("Loading user profile...")
    lesson_gen = LessonGenerator("user_profile.json")
    
    print(f"Found {len(lesson_gen.error_words)} words with errors")
    print(f"Top words: {[w['word'] for w in lesson_gen.get_top_error_words(3)]}")
    
    # Generate conversations
    print("\nGenerating conversations with Backboard...")
    conversations = await lesson_gen.generate_conversations(
        client=client,
        assistant_id=assistant_id,
        num_conversations=3
    )
    
    # Print lesson
    lesson_gen.print_lesson()
    
    # Prompt user to practice
    user_input = input("\nReady to practice? (y/n): ")
    if user_input.lower() == 'y':
        save_recs = input("Save recordings? (y/n, default: n): ").lower() == 'y'
        save_mp3 = False
        if save_recs:
            save_mp3 = input("Save as MP3? (y/n, default: n): ").lower() == 'y'
            if save_mp3 and not MP3_CONVERSION_AVAILABLE:
                print("\n⚠️  MP3 conversion requires pydub and ffmpeg")
                print("   Install: pip install pydub")
                print("   Download ffmpeg: https://ffmpeg.org/download.html")
                print("   Saving as WAV instead...\n")
                save_mp3 = False
        lesson_gen.prompt_user_practice(save_recordings=save_recs, save_as_mp3=save_mp3)


if __name__ == "__main__":
    asyncio.run(main())
