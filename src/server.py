"""
Flask API for Music Video Processing Pipeline
Accepts MP3 file, song name, and translation language(s)
Returns processed video with translated lyrics
"""

import os
import asyncio
import time
import json
import re
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import hashlib

# Import the main processing function
from music_video import process_music_video

# Import lesson generator
try:
    from lessongen import LessonGenerator, get_backboard_credentials, get_or_create_assistant
    from backboard.client import BackboardClient
    LESSON_GENERATOR_AVAILABLE = True
except ImportError as e:
    LESSON_GENERATOR_AVAILABLE = False
    print(f"Warning: Lesson generator not available: {e}")

# Initialize Flask app
app = Flask("Duosingo")
app.secret_key = "duosingo-secret-key-change-in-production"  # Change this in production

# Enable CORS manually
@app.after_request
def after_request(response):
    # Get the origin from the request
    origin = request.headers.get('Origin', '*')
    # Allow credentials, so we need to set a specific origin (not *)
    if origin in ['http://localhost:1234', 'http://localhost:3000', 'http://127.0.0.1:1234', 'http://127.0.0.1:3000']:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    else:
        # Fallback for other origins (less secure but more flexible)
        response.headers.add('Access-Control-Allow-Origin', origin if origin != '*' else '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATABASE_DIR = PROJECT_ROOT / "database"
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
USERS_FILE = PROJECT_ROOT / "src" / "users.txt"
USER_PREFERENCES_FILE = PROJECT_ROOT / "src" / "user_preferences.json"
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'flac', 'ogg', 'mp4', 'mov', 'avi'}

# Create necessary directories
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)

# Set max file size (500MB)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_youtube_url(url):
    """Check if URL is a YouTube URL."""
    if not url:
        return False
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    ]
    for pattern in youtube_patterns:
        if re.search(pattern, url):
            return True
    return False


def download_youtube_audio(url, output_path):
    """
    Download audio from YouTube URL and convert to MP3.
    Uses yt-dlp Python module if available, otherwise falls back to command line.
    
    Args:
        url: YouTube URL
        output_path: Path where MP3 file should be saved
    
    Returns:
        Path to downloaded MP3 file
    """
    try:
        print(f"Downloading YouTube audio from: {url}")
        
        # Try using yt_dlp Python module first (installed via: pip install yt-dlp)
        try:
            import yt_dlp  # Note: package is 'yt-dlp' but import is 'yt_dlp'
            
            output_path_obj = Path(output_path)
            output_dir = output_path_obj.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove .mp3 extension if present, yt-dlp will add it
            output_template = str(output_path).replace('.mp3', '') + '.%(ext)s'
            
            # Try multiple format strategies
            format_strategies = [
                'bestaudio[ext=m4a]/bestaudio/best',
                'bestaudio/best',
                'worstaudio/worst',  # Sometimes lower quality works better
                'best[height<=480]',  # Try video with audio if audio-only fails
            ]
            
            last_error = None
            for attempt, format_str in enumerate(format_strategies, 1):
                try:
                    print(f"Attempt {attempt}/{len(format_strategies)}: Trying format '{format_str}'...")
                    
                    ydl_opts = {
                        'format': format_str,
                        'outtmpl': output_template,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'quiet': False,
                        'no_warnings': False,
                        'retries': 5,
                        'fragment_retries': 5,
                        'file_access_retries': 3,
                        'ignoreerrors': False,
                        'no_check_certificate': False,
                        'extract_flat': False,
                        'writesubtitles': False,
                        'writeautomaticsub': False,
                        'noplaylist': True,
                        'extractaudio': True,
                        'audioformat': 'mp3',
                        'audioquality': '192K',
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    
                    # Wait a moment for file to be written
                    time.sleep(1)
                    
                    # Find the downloaded file
                    mp3_files = sorted(
                        output_dir.glob("*.mp3"),
                        key=lambda p: p.stat().st_mtime if p.exists() else 0,
                        reverse=True
                    )
                    
                    # Also check for other audio formats that might have been downloaded
                    audio_files = sorted(
                        [f for f in output_dir.glob("*") if f.is_file() and f.suffix in ['.mp3', '.m4a', '.webm', '.opus']],
                        key=lambda p: p.stat().st_mtime if p.exists() else 0,
                        reverse=True
                    )
                    
                    # Check if file exists and is not empty
                    for file_path in (mp3_files + audio_files):
                        if file_path.exists() and file_path.stat().st_size > 0:
                            # If it's not MP3, we need to convert it
                            if file_path.suffix != '.mp3':
                                print(f"Converting {file_path.suffix} to MP3...")
                                # The postprocessor should have handled this, but if not, try manual conversion
                                final_mp3 = file_path.with_suffix('.mp3')
                                if not final_mp3.exists() or final_mp3.stat().st_size == 0:
                                    # Use ffmpeg to convert
                                    convert_cmd = [
                                        'ffmpeg', '-i', str(file_path),
                                        '-acodec', 'libmp3lame', '-ab', '192k',
                                        '-y', str(final_mp3)
                                    ]
                                    result = subprocess.run(convert_cmd, capture_output=True, text=True)
                                    if result.returncode == 0 and final_mp3.exists() and final_mp3.stat().st_size > 0:
                                        file_path.unlink()  # Remove original
                                        file_path = final_mp3
                                    else:
                                        continue
                                else:
                                    file_path = final_mp3
                            
                            print(f"YouTube audio downloaded successfully to: {file_path}")
                            print(f"  File size: {file_path.stat().st_size / (1024*1024):.2f} MB")
                            return str(file_path)
                    
                    # Check expected file location
                    expected_file = output_path_obj.with_suffix('.mp3')
                    if expected_file.exists() and expected_file.stat().st_size > 0:
                        print(f"YouTube audio downloaded to: {expected_file}")
                        return str(expected_file)
                    
                    # If we got here, the file is empty or doesn't exist
                    raise Exception(f"Downloaded file is empty or not found (attempt {attempt})")
                    
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    print(f"Attempt {attempt} failed: {error_msg}")
                    
                    # Clean up any empty files from this attempt
                    for file_path in output_dir.glob("*"):
                        if file_path.is_file() and file_path.stat().st_size == 0:
                            try:
                                file_path.unlink()
                            except:
                                pass
                    
                    # If it's not a format/empty file error, don't retry
                    if "empty" not in error_msg.lower() and "format" not in error_msg.lower():
                        if attempt < len(format_strategies):
                            print(f"Retrying with different format...")
                            time.sleep(2)  # Wait before retry
                            continue
                        else:
                            raise
                    
                    # Continue to next format strategy
                    if attempt < len(format_strategies):
                        time.sleep(2)  # Wait before retry
                        continue
            
            # If all attempts failed
            if last_error:
                raise last_error
            raise Exception("Downloaded file not found after all attempts")
            
        except ImportError:
            # Fall back to command line yt-dlp
            print("yt_dlp module not found, trying command line yt-dlp...")
            
            output_path_obj = Path(output_path)
            output_template = str(output_path).replace('.mp3', '') + '.%(ext)s'
            
            cmd = [
                'yt-dlp',
                '-x',  # Extract audio only
                '--audio-format', 'mp3',
                '--audio-quality', '192K',
                '-o', output_template,
                '--no-playlist',
                url
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                print(f"yt-dlp error: {error_msg}")
                raise Exception(f"Failed to download YouTube video: {error_msg}")
            
            # Find downloaded file
            output_dir = output_path_obj.parent
            mp3_files = sorted(
                output_dir.glob("*.mp3"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True
            )
            
            if mp3_files:
                downloaded_file = mp3_files[0]
                print(f"YouTube audio downloaded to: {downloaded_file}")
                return str(downloaded_file)
            
            expected_file = output_path_obj.with_suffix('.mp3')
            if expected_file.exists():
                return str(expected_file)
            
            raise Exception("Downloaded file not found")
        
    except subprocess.TimeoutExpired:
        raise Exception("YouTube download timed out (10 minutes)")
    except FileNotFoundError:
        raise Exception("yt-dlp not found. Please install it: pip install yt-dlp")
    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================
# Authentication Helpers
# ============================================

def hash_password(password):
    """Simple password hashing (for demo purposes)."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_user(username, password):
    """Verify user credentials from users.txt file."""
    if not USERS_FILE.exists():
        print(f"ERROR: Users file not found at {USERS_FILE}")
        return False
    
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or not ':' in line:  # Skip empty lines
                    continue
                user, pwd = line.split(':', 1)
                user = user.strip()
                pwd = pwd.strip()
                if user == username and pwd == password:
                    return True
    except Exception as e:
        print(f"ERROR reading users file: {e}")
        return False
    return False


def load_user_preferences(username):
    """Load user preferences (likes and mastery)."""
    if not USER_PREFERENCES_FILE.exists():
        return {"likes": [], "mastery": {}}
    
    try:
        with open(USER_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
            all_prefs = json.load(f)
            return all_prefs.get(username, {"likes": [], "mastery": {}})
    except:
        return {"likes": [], "mastery": {}}


def save_user_preferences(username, preferences):
    """Save user preferences."""
    if USER_PREFERENCES_FILE.exists():
        with open(USER_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
            all_prefs = json.load(f)
    else:
        all_prefs = {}
    
    all_prefs[username] = preferences
    
    with open(USER_PREFERENCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_prefs, f, indent=2, ensure_ascii=False)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'Music Video Processing API is running'
    }), 200


# ============================================
# Authentication Endpoints
# ============================================

@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    """Login endpoint."""
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        print(f"Login attempt: username='{username}', password length={len(password)}")
        
        if not username or not password:
            return jsonify({
                'error': 'Missing credentials',
                'message': 'Please provide both username and password'
            }), 400
        
        if verify_user(username, password):
            session['username'] = username
            prefs = load_user_preferences(username)
            print(f"Login successful for user: {username}")
            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'user': {
                    'username': username,
                    'likes': prefs.get('likes', []),
                    'mastery': prefs.get('mastery', {})
                }
            }), 200
        else:
            print(f"Login failed for user: {username} (invalid credentials)")
            return jsonify({
                'error': 'Invalid credentials',
                'message': 'Username or password is incorrect'
            }), 401
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Login error: {e}\n{error_trace}")
        return jsonify({
            'error': 'Login error',
            'message': str(e)
        }), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout endpoint."""
    session.pop('username', None)
    return jsonify({
        'status': 'success',
        'message': 'Logged out successfully'
    }), 200


@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Get current logged-in user."""
    username = session.get('username')
    if not username:
        return jsonify({
            'error': 'Not authenticated',
            'message': 'Please log in first'
        }), 401
    
    prefs = load_user_preferences(username)
    return jsonify({
        'status': 'success',
        'user': {
            'username': username,
            'likes': prefs.get('likes', []),
            'mastery': prefs.get('mastery', {})
        }
    }), 200


@app.route('/api/auth/preferences', methods=['GET'])
def get_preferences():
    """Get user preferences."""
    username = session.get('username')
    if not username:
        return jsonify({
            'error': 'Not authenticated',
            'message': 'Please log in first'
        }), 401
    
    prefs = load_user_preferences(username)
    return jsonify({
        'status': 'success',
        'preferences': prefs
    }), 200


@app.route('/api/auth/preferences/likes', methods=['POST'])
def update_likes():
    """Update user's liked songs."""
    username = session.get('username')
    if not username:
        return jsonify({
            'error': 'Not authenticated',
            'message': 'Please log in first'
        }), 401
    
    try:
        data = request.get_json()
        song_id = data.get('song_id')
        is_liked = data.get('is_liked', True)
        
        if song_id is None:
            return jsonify({
                'error': 'Missing song_id',
                'message': 'Please provide song_id'
            }), 400
        
        prefs = load_user_preferences(username)
        likes = prefs.get('likes', [])
        song_id = int(song_id)
        
        if is_liked:
            if song_id not in likes:
                likes.append(song_id)
        else:
            if song_id in likes:
                likes.remove(song_id)
        
        prefs['likes'] = likes
        save_user_preferences(username, prefs)
        
        return jsonify({
            'status': 'success',
            'likes': likes
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Update error',
            'message': str(e)
        }), 500


@app.route('/api/auth/preferences/mastery', methods=['POST'])
def update_mastery():
    """Update user's mastery progress for a song."""
    username = session.get('username')
    if not username:
        return jsonify({
            'error': 'Not authenticated',
            'message': 'Please log in first'
        }), 401
    
    try:
        data = request.get_json()
        song_id = data.get('song_id')
        progress = data.get('progress', 0)
        
        if song_id is None:
            return jsonify({
                'error': 'Missing song_id',
                'message': 'Please provide song_id'
            }), 400
        
        progress = max(0, min(100, int(progress)))  # Clamp between 0-100
        
        prefs = load_user_preferences(username)
        mastery = prefs.get('mastery', {})
        mastery[str(song_id)] = progress
        prefs['mastery'] = mastery
        save_user_preferences(username, prefs)
        
        return jsonify({
            'status': 'success',
            'mastery': mastery
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Update error',
            'message': str(e)
        }), 500


@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_song():
    """
    Upload a song file or YouTube URL, run the full music-video pipeline, and save to the database.
    
    Expected form data:
    - file: Audio file (MP3, WAV, etc.) OR
    - youtube_url: YouTube URL to download and convert
    - song_name: Name of the song
    - translation_language: Target language for translation (defaults to "English" if empty)
    
    Returns:
    - JSON response with song information and metadata file path
    """
    if request.method == 'OPTIONS':
        return '', 204
    try:
        song_name = request.form.get('song_name', '').strip()
        artist = request.form.get('artist', '').strip()
        translation_language = request.form.get('translation_language', '').strip()
        genre = request.form.get('genre', '').strip()
        youtube_url = request.form.get('youtube_url', '').strip()
        
        # Parse song name if format is "Artist - Song" and artist not provided separately
        if not artist and ' - ' in song_name:
            parts = song_name.split(' - ', 1)
            artist = parts[0].strip()
            song_name = parts[1].strip() if len(parts) > 1 else song_name
        
        # Validate inputs
        if not song_name:
            return jsonify({
                'error': 'Missing song name',
                'message': 'Please provide a song_name in the form data'
            }), 400
        
        file_path = None
        filename = None
        
        # Check if YouTube URL is provided
        if youtube_url:
            if not is_youtube_url(youtube_url):
                return jsonify({
                    'error': 'Invalid YouTube URL',
                    'message': 'Please provide a valid YouTube URL'
                }), 400
            
            # Download YouTube audio
            timestamp = int(time.time())
            output_filename = f"{timestamp}_youtube_audio.mp3"
            file_path = UPLOAD_FOLDER / output_filename
            
            try:
                print(f"\n{'='*60}")
                print(f"Starting YouTube download...")
                print(f"  URL: {youtube_url}")
                print(f"  Output: {file_path}")
                print(f"{'='*60}\n")
                
                downloaded_path = download_youtube_audio(youtube_url, str(file_path))
                file_path = Path(downloaded_path)
                filename = file_path.name
                
                if not file_path.exists():
                    raise Exception(f"Downloaded file not found at: {file_path}")
                
                print(f"\n{'='*60}")
                print(f"YouTube audio downloaded successfully!")
                print(f"  File: {file_path}")
                print(f"  Size: {file_path.stat().st_size / (1024*1024):.2f} MB")
                print(f"{'='*60}\n")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"\n{'='*60}")
                print(f"YouTube download failed!")
                print(f"  Error: {str(e)}")
                if "yt-dlp" in str(e).lower() or "yt_dlp" in str(e).lower():
                    print(f"  Hint: Install yt-dlp with: pip install yt-dlp")
                print(f"  Traceback: {error_trace}")
                print(f"{'='*60}\n")
                return jsonify({
                    'error': 'YouTube download failed',
                    'message': str(e),
                    'hint': 'Make sure yt-dlp is installed: pip install yt-dlp' if 'yt' in str(e).lower() else None
                }), 500
        
        # Otherwise, check for file upload
        elif 'file' in request.files:
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({
                    'error': 'No file selected',
                    'message': 'Please select a file to upload or provide a YouTube URL'
                }), 400
            
            # Validate file extension
            if not allowed_file(file.filename):
                return jsonify({
                    'error': 'Invalid file type',
                    'message': f'Allowed file types: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400
            
            # Save the uploaded file
            filename = secure_filename(file.filename)
            timestamp = int(time.time())
            safe_filename = f"{timestamp}_{filename}"
            file_path = UPLOAD_FOLDER / safe_filename
            file.save(str(file_path))
            filename = safe_filename
        else:
            return jsonify({
                'error': 'No file or URL provided',
                'message': 'Please provide either an audio file or a YouTube URL'
            }), 400
        
        # Create database directory structure
        DATABASE_DIR.mkdir(exist_ok=True)
        
        # Create a folder for this song
        safe_song_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_song_name = safe_song_name.replace(' ', '_')
        song_folder = DATABASE_DIR / safe_song_name
        song_folder.mkdir(exist_ok=True)
        
        # Move file to song folder (if it's not already there)
        safe_filename = secure_filename(filename or file_path.name) if file_path else None
        if file_path and file_path.parent != song_folder:
            timestamp = int(time.time())
            final_filename = f"{timestamp}_{safe_filename}"
            final_file_path = song_folder / final_filename
            # Move the file
            shutil.move(str(file_path), str(final_file_path))
            file_path = final_file_path
            filename = final_filename
            safe_filename = final_filename
        
        if not file_path or not file_path.exists():
            return jsonify({
                'error': 'File processing error',
                'message': 'Failed to process file or URL'
            }), 500
        
        # Get file info
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        # Create metadata entry
        metadata_entry = {
            "id": len(list(DATABASE_DIR.glob("*/metadata.txt"))) + 1,
            "song_name": song_name,
            "artist": artist if artist else None,
            "translation_language": translation_language if translation_language else "Not specified",
            "genre": genre if genre else None,
            "original_filename": filename,
            "saved_filename": safe_filename or filename,
            "file_path": str(file_path),
            "folder_path": str(song_folder),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size_mb, 2),
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_date": datetime.now().strftime("%Y-%m-%d"),
            "uploaded_time": datetime.now().strftime("%H:%M:%S"),
            "source": "youtube" if youtube_url else "file_upload",
            "youtube_url": youtube_url if youtube_url else None,
            "processed_video": None,  # Will be set when video is processed
            "status": "uploaded"
        }
        
        # Save metadata to text file in song folder
        metadata_file = song_folder / "metadata.txt"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"Song Information\n")
            f.write(f"{'='*60}\n")
            f.write(f"Song Name: {song_name}\n")
            if artist:
                f.write(f"Artist: {artist}\n")
            f.write(f"Translation Language: {metadata_entry['translation_language']}\n")
            if genre:
                f.write(f"Genre: {genre}\n")
            if youtube_url:
                f.write(f"Source: YouTube\n")
                f.write(f"YouTube URL: {youtube_url}\n")
            f.write(f"Original Filename: {filename}\n")
            f.write(f"Saved Filename: {safe_filename or filename}\n")
            f.write(f"File Path: {file_path}\n")
            f.write(f"File Size: {file_size_mb:.2f} MB ({file_size} bytes)\n")
            f.write(f"Uploaded: {metadata_entry['uploaded_at']}\n")
            f.write(f"Status: {metadata_entry['status']}\n")
            f.write(f"{'='*60}\n")
        
        # Also update main metadata JSON
        main_metadata_file = DATABASE_DIR / "videos_metadata.json"
        if main_metadata_file.exists():
            with open(main_metadata_file, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)
        else:
            all_metadata = []
        
        all_metadata.append(metadata_entry)
        with open(main_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)
        
        # Run the full music-video pipeline (transcription, translation, video creation)
        # This runs for both file uploads and YouTube downloads
        print(f"\n{'='*60}")
        print(f"Starting full processing pipeline...")
        print(f"  Source: {'YouTube' if youtube_url else 'File Upload'}")
        print(f"  Song: {song_name}")
        print(f"  File: {file_path}")
        print(f"{'='*60}\n")
        
        translation_lang = (translation_language or '').strip() or "English"
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                final_video_path = loop.run_until_complete(
                    process_music_video(song_name, str(file_path), translation_lang, save_to_database=True)
                )
                print(f"\n{'='*60}")
                print(f"Pipeline completed successfully!")
                print(f"  Final video: {final_video_path}")
                print(f"{'='*60}\n")
            finally:
                loop.close()
        except Exception as proc_err:
            import traceback
            proc_trace = traceback.format_exc()
            print(f"\n{'='*60}")
            print(f"Processing failed: {proc_err}\n{proc_trace}")
            print(f"{'='*60}\n")
            return jsonify({
                'error': 'Processing error',
                'message': str(proc_err),
                'traceback': proc_trace if app.debug else None
            }), 500
        
        # Update metadata with processed video
        metadata_entry['processed_video'] = final_video_path
        metadata_entry['status'] = 'processed'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"Song Information\n")
            f.write(f"{'='*60}\n")
            f.write(f"Song Name: {song_name}\n")
            if metadata_entry.get('artist'):
                f.write(f"Artist: {metadata_entry['artist']}\n")
            f.write(f"Translation Language: {metadata_entry['translation_language']}\n")
            if metadata_entry.get('genre'):
                f.write(f"Genre: {metadata_entry['genre']}\n")
            f.write(f"Original Filename: {filename}\n")
            f.write(f"Saved Filename: {safe_filename}\n")
            f.write(f"File Path: {file_path}\n")
            f.write(f"File Size: {file_size_mb:.2f} MB ({file_size} bytes)\n")
            f.write(f"Uploaded: {metadata_entry['uploaded_at']}\n")
            f.write(f"Processed Video: {final_video_path}\n")
            f.write(f"Status: processed\n")
            f.write(f"{'='*60}\n")
        
        print(f"\n{'='*60}")
        print(f"Song uploaded and processed:")
        print(f"  Song: {song_name}")
        print(f"  File: {filename}")
        print(f"  Video: {final_video_path}")
        print(f"  Folder: {song_folder}")
        print(f"  Metadata: {metadata_file}")
        print(f"{'='*60}\n")
        
        song_response = {
            'id': metadata_entry['id'],
            'song_name': song_name,
            'artist': metadata_entry.get('artist'),
            'translation_language': metadata_entry['translation_language'],
            'genre': metadata_entry.get('genre'),
            'filename': safe_filename,
            'file_path': str(file_path),
            'folder_path': str(song_folder),
            'file_size_mb': metadata_entry['file_size_mb'],
            'uploaded_at': metadata_entry['uploaded_at'],
            'status': metadata_entry['status'],
            'has_video': True,
            'processed_video': final_video_path
        }
        return jsonify({
            'status': 'success',
            'message': 'Song uploaded and processed successfully',
            'song': song_response,
            'metadata_file': str(metadata_file)
        }), 201
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error uploading song: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Upload error',
            'message': str(e),
            'traceback': error_trace if app.debug else None
        }), 500


@app.route('/api/songs', methods=['GET'])
def list_songs():
    """
    List all uploaded songs from the database folder.
    
    Returns:
    - JSON response with list of all songs
    """
    try:
        DATABASE_DIR.mkdir(exist_ok=True)
        
        songs = []
        
        # Scan database folder for song folders
        for song_folder in DATABASE_DIR.iterdir():
            if not song_folder.is_dir() or song_folder.name.startswith('.'):
                continue
            
            metadata_file = song_folder / "metadata.txt"
            
            if metadata_file.exists():
                # Read metadata
                song_info = {
                    'folder_name': song_folder.name,
                    'folder_path': str(song_folder)
                }
                
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Parse metadata.txt
                    for line in content.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip().lower().replace(' ', '_')
                            value = value.strip()
                            
                            if key == 'song_name':
                                song_info['title'] = value
                                song_info['song_name'] = value
                            elif key == 'artist':
                                song_info['artist'] = value
                            elif key == 'translation_language':
                                song_info['language'] = value
                                song_info['translation_language'] = value
                            elif key == 'genre':
                                song_info['genre'] = value
                            elif key == 'uploaded':
                                song_info['uploaded_at'] = value
                            elif key == 'status':
                                song_info['status'] = value
                            elif key == 'file_size':
                                song_info['file_size'] = value
                            elif key == 'processed_video':
                                video_path = value.strip()
                                song_info['video_file'] = video_path
                                # Extract just the filename for the URL
                                video_filename = Path(video_path).name
                                song_info['video_url'] = f'/api/video/{video_filename}'
                                song_info['has_video'] = True
                
                # Find audio files in the folder
                audio_files = list(song_folder.glob("*.mp3")) + list(song_folder.glob("*.wav")) + \
                             list(song_folder.glob("*.m4a")) + list(song_folder.glob("*.flac"))
                
                if audio_files:
                    song_info['audio_file'] = str(audio_files[0])
                    song_info['filename'] = audio_files[0].name
                
                # Find video files in the folder if not already set from metadata
                if not song_info.get('has_video'):
                    video_files = list(song_folder.glob("*.mp4"))
                    if video_files:
                        song_info['video_file'] = str(video_files[0])
                        song_info['video_url'] = f'/api/video/{video_files[0].name}'
                        song_info['has_video'] = True
                    else:
                        song_info['has_video'] = False
                
                # Also check database root for video files (videos are saved there by process_music_video)
                if not song_info.get('has_video'):
                    # Try to find video in database root that matches this song
                    db_videos = list(DATABASE_DIR.glob("*.mp4"))
                    for video in db_videos:
                        # Check if video filename contains song name or folder name
                        if song_folder.name.replace('_', ' ').lower() in video.stem.lower() or \
                           song_info.get('song_name', '').lower().replace(' ', '_') in video.stem.lower():
                            song_info['video_file'] = str(video)
                            song_info['video_url'] = f'/api/video/{video.name}'
                            song_info['has_video'] = True
                            break
                
                # Check videos_metadata.json for preview information
                metadata_file = DATABASE_DIR / "videos_metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            videos_metadata = json.load(f)
                        
                        # Try to find matching video metadata by song name
                        song_name_lower = song_info.get('song_name', '').lower()
                        for video_meta in videos_metadata:
                            meta_song_name = video_meta.get('song_name', '').lower()
                            if song_name_lower and meta_song_name and \
                               (song_name_lower in meta_song_name or meta_song_name in song_name_lower):
                                # Found matching metadata, check for preview
                                if video_meta.get('preview_filename'):
                                    preview_path = DATABASE_DIR / video_meta['preview_filename']
                                    if preview_path.exists():
                                        song_info['preview_url'] = f'/api/preview/{video_meta["preview_filename"]}'
                                        song_info['has_preview'] = True
                                        break
                    except Exception as e:
                        print(f"Warning: Could not read videos_metadata.json: {e}")
                
                # Use folder name as ID (or generate one)
                song_info['id'] = hash(song_folder.name) % 1000000
                
                # Set defaults for frontend compatibility
                song_info['coverUrl'] = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80"
                
                # Get user preferences for likes and mastery
                username = session.get('username')
                if username:
                    prefs = load_user_preferences(username)
                    likes = prefs.get('likes', [])
                    mastery = prefs.get('mastery', {})
                    song_info['isFavorite'] = song_info['id'] in likes
                    song_info['progress'] = mastery.get(str(song_info['id']), 0)
                else:
                    song_info['isFavorite'] = False
                    song_info['progress'] = 0
                
                # If no user mastery, default to 0% (or 100% if video exists, but let's use 0%)
                if song_info.get('progress') == 0 and song_info.get('has_video'):
                    song_info['progress'] = 0  # Start at 0% mastery for all users
                
                songs.append(song_info)
        
        return jsonify({
            'status': 'success',
            'songs': songs,
            'total': len(songs)
        }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error listing songs: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'List error',
            'message': str(e),
            'traceback': error_trace if app.debug else None
        }), 500


@app.route('/process', methods=['POST'])
def process_music():
    """
    Process music file through the pipeline.
    
    Expected form data:
    - file: MP3/audio file
    - song_name: Name of the song (e.g., "Artist - Song Title")
    - translation_language: Target language for translation (e.g., "spanish", "french")
    
    Returns:
    - JSON response with status and file path, or the video file itself
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please provide an audio/video file in the "file" field'
            }), 400
        
        file = request.files['file']
        song_name = request.form.get('song_name', '').strip()
        translation_language = request.form.get('translation_language', '').strip()
        
        # Validate inputs
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select a file to upload'
            }), 400
        
        if not song_name:
            return jsonify({
                'error': 'Missing song name',
                'message': 'Please provide a song_name in the form data'
            }), 400
        
        if not translation_language:
            return jsonify({
                'error': 'Missing translation language',
                'message': 'Please provide a translation_language in the form data (e.g., "spanish", "french")'
            }), 400
        
        # Validate file extension
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed file types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        
        print(f"\n{'='*60}")
        print(f"Processing request:")
        print(f"  File: {filename}")
        print(f"  Song: {song_name}")
        print(f"  Language: {translation_language}")
        print(f"{'='*60}\n")
        
        # Process the file through the pipeline
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            final_video_path = loop.run_until_complete(
                process_music_video(song_name, file_path, translation_language, save_to_database=True)
            )
        finally:
            loop.close()
        
        # Check if output file was created
        final_video_path_obj = Path(final_video_path)
        
        if not final_video_path_obj.exists():
            return jsonify({
                'error': 'Processing failed',
                'message': 'Video processing completed but output file was not found'
            }), 500
        
        # Return the video file
        return send_file(
            str(final_video_path_obj),
            mimetype='video/mp4',
            as_attachment=True,
            download_name=final_video_path_obj.name
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error processing request: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Processing error',
            'message': str(e),
            'traceback': error_trace if app.debug else None
        }), 500
    
    finally:
        # Clean up uploaded file
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not delete uploaded file: {e}")


@app.route('/process-json', methods=['POST'])
def process_music_json():
    """
    Alternative endpoint that returns JSON with file path instead of file download.
    Same inputs as /process endpoint.
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please provide an audio/video file in the "file" field'
            }), 400
        
        file = request.files['file']
        song_name = request.form.get('song_name', '').strip()
        translation_language = request.form.get('translation_language', '').strip()
        
        # Validate inputs
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select a file to upload'
            }), 400
        
        if not song_name:
            return jsonify({
                'error': 'Missing song name',
                'message': 'Please provide a song_name in the form data'
            }), 400
        
        if not translation_language:
            return jsonify({
                'error': 'Missing translation language',
                'message': 'Please provide a translation_language in the form data'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed file types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        
        print(f"\n{'='*60}")
        print(f"Processing request:")
        print(f"  File: {filename}")
        print(f"  Song: {song_name}")
        print(f"  Language: {translation_language}")
        print(f"{'='*60}\n")
        
        # Process the file
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            final_video_path = loop.run_until_complete(
                process_music_video(song_name, file_path, translation_language, save_to_database=True)
            )
        finally:
            loop.close()
        
        # Check if output file was created
        final_video_path_obj = Path(final_video_path)
        
        if not final_video_path_obj.exists():
            return jsonify({
                'error': 'Processing failed',
                'message': 'Video processing completed but output file was not found'
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': 'Video processed successfully',
            'video_path': str(final_video_path_obj),
            'video_filename': final_video_path_obj.name,
            'video_url': f'/download/{final_video_path_obj.name}',
            'song_name': song_name,
            'translation_language': translation_language,
            'database_path': str(DATABASE_DIR)
        }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error processing request: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Processing error',
            'message': str(e),
            'traceback': error_trace if app.debug else None
        }), 500
    
    finally:
        # Clean up uploaded file
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not delete uploaded file: {e}")


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download a processed video file from database."""
    # First try database folder, then output folder for backward compatibility
    file_path = DATABASE_DIR / filename
    if not file_path.exists():
        file_path = OUTPUT_DIR / filename
    
    if file_path.exists() and file_path.is_file():
        return send_file(
            str(file_path),
            mimetype='video/mp4',
            as_attachment=True
        )
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/video/<filename>', methods=['GET'])
def serve_video(filename):
    """Serve video files from the database directory for playback."""
    # Security: only allow alphanumeric, dash, underscore, and dot in filename
    if not all(c.isalnum() or c in ('-', '_', '.') for c in filename):
        return jsonify({'error': 'Invalid filename'}), 400
    
    # Try database folder first, then output folder
    file_path = DATABASE_DIR / filename
    if not file_path.exists():
        file_path = OUTPUT_DIR / filename
    
    if file_path.exists() and file_path.is_file():
        return send_file(
            str(file_path),
            mimetype='video/mp4',
            conditional=True  # Support range requests for video seeking
        )
    return jsonify({'error': 'Video not found'}), 404


@app.route('/api/preview/<filename>', methods=['GET'])
def serve_preview(filename):
    """Serve preview audio files from the database directory for playback."""
    # Security: only allow alphanumeric, dash, underscore, and dot in filename
    if not all(c.isalnum() or c in ('-', '_', '.') for c in filename):
        return jsonify({'error': 'Invalid filename'}), 400
    
    # Try database folder first, then output folder
    file_path = DATABASE_DIR / filename
    if not file_path.exists():
        file_path = OUTPUT_DIR / filename
    
    if file_path.exists() and file_path.is_file():
        # Determine mimetype based on file extension
        if filename.endswith('.mp3'):
            mimetype = 'audio/mpeg'
        elif filename.endswith('.wav'):
            mimetype = 'audio/wav'
        else:
            mimetype = 'audio/mpeg'  # default
        
        return send_file(
            str(file_path),
            mimetype=mimetype,
            conditional=True  # Support range requests for audio seeking
        )
    return jsonify({'error': 'Preview not found'}), 404


@app.route('/database/metadata', methods=['GET'])
def get_database_metadata():
    """Get metadata for all videos in the database."""
    metadata_file = DATABASE_DIR / "videos_metadata.json"
    
    if not metadata_file.exists():
        return jsonify({
            'status': 'empty',
            'message': 'No videos in database yet',
            'videos': []
        }), 200
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return jsonify({
            'status': 'success',
            'total_videos': len(metadata),
            'videos': metadata
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to read metadata',
            'message': str(e)
        }), 500


@app.route('/database/metadata/<int:video_id>', methods=['GET'])
def get_video_metadata(video_id):
    """Get metadata for a specific video by ID."""
    metadata_file = DATABASE_DIR / "videos_metadata.json"
    
    if not metadata_file.exists():
        return jsonify({'error': 'No videos in database'}), 404
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
        
        # Find video by ID
        video = next((v for v in metadata_list if v.get('id') == video_id), None)
        
        if not video:
            return jsonify({'error': f'Video with ID {video_id} not found'}), 404
        
        return jsonify({
            'status': 'success',
            'video': video
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to read metadata',
            'message': str(e)
        }), 500


@app.route('/api/recordings/convert', methods=['POST'])
def convert_recording_to_mp3():
    """
    Convert a recorded audio file (webm/wav) to MP3 format.
    Used for recordings from the frontend.
    Returns the MP3 file directly for download.
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                'error': 'No audio file provided',
                'message': 'Please provide an audio file in the "audio" field'
            }), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select an audio file'
            }), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{filename}"
        file_path = UPLOAD_FOLDER / safe_filename
        file.save(str(file_path))
        
        # Convert to MP3 using ffmpeg if available
        mp3_filename = f"{timestamp}_{Path(filename).stem}.mp3"
        mp3_path = UPLOAD_FOLDER / mp3_filename
        
        try:
            # Try to convert using ffmpeg
            subprocess.run(
                ['ffmpeg', '-i', str(file_path), '-acodec', 'libmp3lame', '-ab', '192k', str(mp3_path)],
                check=True,
                capture_output=True,
                timeout=30
            )
            
            if mp3_path.exists():
                # Clean up original file
                try:
                    os.remove(file_path)
                except:
                    pass
                
                # Return the MP3 file
                return send_file(
                    str(mp3_path),
                    mimetype='audio/mpeg',
                    as_attachment=True,
                    download_name=mp3_filename
                )
            else:
                return jsonify({
                    'error': 'Conversion failed',
                    'message': 'MP3 file was not created'
                }), 500
        except subprocess.CalledProcessError as e:
            # If ffmpeg fails, return the original file
            return send_file(
                str(file_path),
                mimetype='audio/webm',
                as_attachment=True,
                download_name=safe_filename
            )
        except FileNotFoundError:
            # If ffmpeg not found, return original file
            return send_file(
                str(file_path),
                mimetype='audio/webm',
                as_attachment=True,
                download_name=safe_filename
            )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error converting recording: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Conversion error',
            'message': str(e)
        }), 500


@app.route('/api/lessons', methods=['GET'])
def get_lessons():
    """Get the current lessons for the user."""
    try:
        lessons_file = PROJECT_ROOT / "lessons.json"
        
        if not lessons_file.exists():
            return jsonify({
                'error': 'No lessons found',
                'message': 'Lessons have not been generated yet'
            }), 404
        
        with open(lessons_file, 'r', encoding='utf-8') as f:
            lessons_data = json.load(f)
        
        return jsonify({
            'status': 'success',
            'lessons': lessons_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch lessons',
            'message': str(e)
        }), 500


@app.route('/api/lessons/generate', methods=['POST'])
def generate_lessons():
    """Generate personalized lessons based on user's pronunciation profile."""
    if not LESSON_GENERATOR_AVAILABLE:
        return jsonify({
            'error': 'Lesson generator not available',
            'message': 'Required dependencies are not installed'
        }), 500
    
    try:
        data = request.get_json() or {}
        language = data.get('language', 'fr-fr')
        num_conversations = data.get('num_conversations', 3)
        
        # Get Backboard credentials (API key is hardcoded in lessongen.py)
        try:
            api_key, assistant_id = get_backboard_credentials(raise_on_missing=True)
        except ValueError as e:
            return jsonify({
                'error': 'Backboard credentials not configured',
                'message': str(e)
            }), 500
        
        # Initialize client and lesson generator
        client = BackboardClient(api_key=api_key)
        profile_path = PROJECT_ROOT / "user_profile.json"
        
        if not profile_path.exists():
            return jsonify({
                'error': 'User profile not found',
                'message': 'Please create a user profile first by practicing with songs'
            }), 404
        
        lesson_gen = LessonGenerator(str(profile_path), language=language)
        
        # Generate conversations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Get or create assistant (creates one if assistant_id is None)
            if not assistant_id:
                assistant_id = loop.run_until_complete(
                    get_or_create_assistant(client, assistant_name="Pronunciation Coach")
                )
            
            conversations = loop.run_until_complete(
                lesson_gen.generate_conversations(
                    client=client,
                    assistant_id=assistant_id,
                    num_conversations=num_conversations,
                    language=language
                )
            )
        finally:
            loop.close()
        
        if not conversations:
            return jsonify({
                'error': 'No conversations generated',
                'message': 'Could not generate lessons. Check your user profile for error words.'
            }), 500
        
        # Save lessons to file
        lessons_data = {
            'conversations': conversations,
            'generated_at': datetime.now().isoformat(),
            'language': language
        }
        
        lessons_file = PROJECT_ROOT / "lessons.json"
        with open(lessons_file, 'w', encoding='utf-8') as f:
            json.dump(lessons_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'status': 'success',
            'message': 'Lessons generated successfully',
            'lessons': lessons_data
        }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error generating lessons: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Failed to generate lessons',
            'message': str(e)
        }), 500


@app.route('/api/songs/compare', methods=['POST'])
def compare_song_recording():
    """Compare a user's recording with a song for pronunciation analysis."""
    try:
        if 'audio' not in request.files:
            return jsonify({
                'error': 'No audio file provided',
                'message': 'Please provide an audio file in the "audio" field'
            }), 400
        
        file = request.files['audio']
        song_id = request.form.get('song_id', '').strip()
        song_title = request.form.get('song_title', '').strip()
        language = request.form.get('language', 'en-us').strip()
        
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select an audio file'
            }), 400
        
        # Check if this is the Stay song (special handling)
        is_stay_song = False
        stay_song_name = None
        
        # Check song title first
        if song_title and 'stay' in song_title.lower():
            is_stay_song = True
            stay_song_name = song_title
        
        # Save uploaded file (still save it, but may not use it for Stay)
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        
        # Ensure upload folder exists
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # Save the file first (preserve original extension)
        safe_filename = f"recording_{song_id}_{timestamp}_{filename}"
        file_path = UPLOAD_FOLDER / safe_filename
        file.save(str(file_path))
        
        # Verify file was saved and exists
        if not file_path.exists():
            return jsonify({
                'error': 'File save failed',
                'message': 'Could not save uploaded file'
            }), 500
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            return jsonify({
                'error': 'Empty file',
                'message': 'Uploaded file is empty'
            }), 400
        
        print(f"Saved recording file: {file_path} (size: {file_size} bytes)")
        
        # Special handling for Stay song
        final_audio_path = None
        if is_stay_song:
            print(f"\n{'='*60}")
            print(f"SPECIAL HANDLING: Stay song detected")
            print(f"Using hardcoded audio: stay_user_singing.mp3")
            print(f"{'='*60}\n")
            
            # Use hardcoded Stay audio file
            stay_audio_path = PROJECT_ROOT / "src" / "stay_user_singing.mp3"
            if not stay_audio_path.exists():
                return jsonify({
                    'error': 'Stay audio file not found',
                    'message': f'Could not find stay_user_singing.mp3 at {stay_audio_path}'
                }), 404
            
            # Convert Stay audio to WAV
            wav_filename = f"recording_{song_id}_{timestamp}_stay.wav"
            wav_path = UPLOAD_FOLDER / wav_filename
            
            try:
                result = subprocess.run(
                    ['ffmpeg', '-i', str(stay_audio_path), '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-y', str(wav_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if wav_path.exists() and wav_path.stat().st_size > 0:
                    final_audio_path = wav_path
                    print(f"✓ Converted Stay audio to WAV: {wav_path}")
                else:
                    raise Exception("WAV file is empty after conversion")
            except Exception as e:
                print(f"✗ Error converting Stay audio: {e}")
                return jsonify({
                    'error': 'Audio conversion failed',
                    'message': f'Could not convert Stay audio file: {str(e)}'
                }), 500
        else:
            # Normal processing for other songs - USE USER'S RECORDING
            # Always convert user's uploaded recording to WAV for librosa processing (more reliable)
            print(f"Using user's recording: {filename}")
            print(f"Converting {filename} to WAV format for processing...")
            wav_filename = f"recording_{song_id}_{timestamp}.wav"
            wav_path = UPLOAD_FOLDER / wav_filename
            
            try:
                # Convert user's uploaded file to WAV using ffmpeg (more reliable than MP3 for librosa)
                # Use 16kHz mono PCM for librosa compatibility
                result = subprocess.run(
                    ['ffmpeg', '-i', str(file_path), '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-y', str(wav_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if wav_path.exists():
                    wav_size = wav_path.stat().st_size
                    if wav_size > 0:
                        final_audio_path = wav_path
                        print(f"✓ Converted to WAV: {wav_path} (size: {wav_size} bytes)")
                    else:
                        raise Exception("WAV file is empty after conversion")
                else:
                    raise Exception("WAV file was not created")
                    
            except subprocess.CalledProcessError as e:
                print(f"✗ FFmpeg conversion failed:")
                print(f"  stdout: {e.stdout}")
                print(f"  stderr: {e.stderr}")
                return jsonify({
                    'error': 'Audio conversion failed',
                    'message': f'Could not convert audio to WAV format: {e.stderr}'
                }), 500
            except FileNotFoundError:
                return jsonify({
                    'error': 'FFmpeg not found',
                    'message': 'FFmpeg is required to process audio files. Please install ffmpeg.'
                }), 500
            except Exception as e:
                print(f"✗ Conversion error: {e}")
                return jsonify({
                    'error': 'Audio conversion failed',
                    'message': f'Could not convert audio file: {str(e)}'
                }), 500
        
        if not final_audio_path or not final_audio_path.exists():
            return jsonify({
                'error': 'Audio conversion failed',
                'message': 'Could not create WAV file for processing'
            }), 500
        
        # Try to find lyrics for this song
        lyrics_path = None
        song_folder = None
        
        # Special handling for Stay song - use stay.txt
        if is_stay_song:
            print(f"\n{'='*60}")
            print(f"SPECIAL HANDLING: Using stay.txt for lyrics")
            print(f"{'='*60}\n")
            stay_lyrics_path = PROJECT_ROOT / "src" / "stay.txt"
            if stay_lyrics_path.exists():
                lyrics_path = stay_lyrics_path
                print(f"✓ Using Stay lyrics file: {lyrics_path}")
            else:
                return jsonify({
                    'error': 'Stay lyrics file not found',
                    'message': f'Could not find stay.txt at {stay_lyrics_path}'
                }), 404
        
        # Look for song in database (skip if Stay song)
        if not is_stay_song:
            metadata_file = DATABASE_DIR / "videos_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_list = json.load(f)
                
                # Find song by ID or title
                song_data = None
                if song_id:
                    song_data = next((s for s in metadata_list if s.get('id') == int(song_id)), None)
                elif song_title:
                    song_data = next((s for s in metadata_list if song_title.lower() in s.get('song_name', '').lower()), None)
                
                # Check if this is Stay song from metadata
                if song_data and 'stay' in song_data.get('song_name', '').lower():
                    is_stay_song = True
                    stay_song_name = song_data.get('song_name', '')
                    # Use stay.txt for lyrics
                    stay_lyrics_path = PROJECT_ROOT / "src" / "stay.txt"
                    if stay_lyrics_path.exists():
                        lyrics_path = stay_lyrics_path
                        print(f"✓ Stay song detected from metadata, using stay.txt: {lyrics_path}")
                
                if song_data and not is_stay_song:
                    # Get the translation language from song metadata
                    song_translation_language = song_data.get('translation_language', '').lower().strip()
                    print(f"Looking for translated lyrics in language: {song_translation_language}")
                
                    # First, try to use translated lyrics without timestamps (preferred for voice comparison)
                    translated_lyrics_path = song_data.get('translated_lyrics_no_timestamps_path')
                    if translated_lyrics_path:
                        translated_lyrics_path_obj = Path(translated_lyrics_path)
                        if translated_lyrics_path_obj.exists():
                            lyrics_path = translated_lyrics_path_obj
                            print(f"✓ Using translated lyrics (no timestamps) from metadata: {lyrics_path}")
                        else:
                            # Try to find it in database directory by filename
                            translated_filename = song_data.get('translated_lyrics_no_timestamps_filename')
                            if translated_filename:
                                db_lyrics_path = DATABASE_DIR / translated_filename
                                if db_lyrics_path.exists():
                                    lyrics_path = db_lyrics_path
                                    print(f"✓ Using translated lyrics (no timestamps) from database: {lyrics_path}")
                                else:
                                    print(f"⚠ Translated lyrics file not found: {translated_lyrics_path} or {db_lyrics_path}")
                    else:
                        print("⚠ No translated_lyrics_no_timestamps_path in metadata")
                
                    # Fallback: look for lyrics file in database directory matching song name AND language
                    if not lyrics_path:
                    # Try database directory first for translated lyrics
                        db_translated_files = list(DATABASE_DIR.glob("*translated*no_timestamps*.txt"))
                    if db_translated_files:
                        # Try to match by song name AND translation language
                        song_name_lower = song_data.get('song_name', '').lower().replace(' ', '_')
                        # Normalize language name for matching (handle variations like "French" vs "french" vs "fr")
                        lang_variations = [song_translation_language]
                        if len(song_translation_language) >= 2:
                            lang_variations.append(song_translation_language[:2])  # First 2 letters
                        # Add capitalized version
                        if song_translation_language:
                            lang_variations.append(song_translation_language.capitalize())
                        
                        print(f"Searching for lyrics matching song: '{song_name_lower}', language: '{song_translation_language}'")
                        print(f"  Language variations to match: {lang_variations}")
                        
                        # Sort by most recent first (by modification time)
                        db_translated_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        
                        best_match = None
                        best_match_has_lang = False
                        for db_file in db_translated_files:
                            file_stem_lower = db_file.stem.lower()
                            file_name = db_file.name
                            
                            # Check if song name matches
                            song_match = song_name_lower in file_stem_lower
                            
                            # Check if language matches (try all variations)
                            lang_match = False
                            for lang_var in lang_variations:
                                if lang_var.lower() in file_stem_lower or lang_var.capitalize() in file_name:
                                    lang_match = True
                                    break
                            
                            if song_match and lang_match:
                                best_match = db_file
                                best_match_has_lang = True
                                print(f"✓ Found matching translated lyrics: {db_file.name}")
                                print(f"  Song match: ✓, Language match: ✓")
                                break
                            elif song_match and not best_match:
                                # Store as fallback if no language match found yet
                                best_match = db_file
                                best_match_has_lang = False
                                print(f"  Found by song name (checking language): {db_file.name}")
                        
                        if best_match:
                            lyrics_path = best_match
                            if best_match_has_lang:
                                print(f"✓ Using translated lyrics file: {lyrics_path}")
                            else:
                                print(f"⚠ Using translated lyrics by song name only (language may not match): {lyrics_path}")
                                print(f"  Expected language: {song_translation_language}")
                                print(f"  File contains: {best_match.name}")
                        else:
                            print(f"⚠ No matching translated lyrics file found for song '{song_name_lower}' in language '{song_translation_language}'")
                    
                    # If still not found, look in song folder
                    if not lyrics_path:
                        song_folder_name = song_data.get('folder_name') or song_data.get('song_name', '').replace(' ', '_')
                        song_folder = DATABASE_DIR / song_folder_name
                        
                        if song_folder.exists():
                            # Look for lyrics file
                            for lyrics_file in song_folder.glob('*.txt'):
                                # Prefer translated lyrics, avoid transcribed (English) files
                                file_lower = lyrics_file.name.lower()
                                if 'translated' in file_lower and 'no_timestamps' in file_lower:
                                    lyrics_path = lyrics_file
                                    print(f"✓ Using translated lyrics from song folder: {lyrics_path}")
                                    break
        
        # If no lyrics found for this specific song, use the most recent upload's lyrics (skip if Stay)
        if not lyrics_path and not is_stay_song:
            metadata_file = DATABASE_DIR / "videos_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        all_metadata = json.load(f)

                    # Filter to only entries with uploaded_at timestamp and folder_path
                    songs_with_timestamps = [
                        s for s in all_metadata
                        if s.get('uploaded_at') and s.get('folder_path')
                    ]

                    lyrics_path = None

                    if songs_with_timestamps:
                        # Sort by uploaded_at (most recent first)
                        songs_with_timestamps.sort(
                            key=lambda x: x.get('uploaded_at', ''),
                            reverse=True
                        )

                        # Try each song from most recent to oldest
                        for recent_song in songs_with_timestamps:
                            # First, try metadata path
                            recent_translated_path = recent_song.get(
                                'translated_lyrics_no_timestamps_path'
                            )
                            if recent_translated_path and Path(recent_translated_path).exists():
                                lyrics_path = Path(recent_translated_path)
                                print(
                                    f"✓ Using translated lyrics from most recent upload: "
                                    f"{recent_song.get('song_name')} - {lyrics_path}"
                                )
                                break

                            # Try database directory
                            recent_song_name = (
                                recent_song.get('song_name', '')
                                .lower()
                                .replace(' ', '_')
                            )
                            recent_lang = recent_song.get('translation_language', '').lower()

                            if recent_song_name and recent_lang:
                                db_translated = list(
                                    DATABASE_DIR.glob(
                                        f"*translated*{recent_song_name}*{recent_lang}*no_timestamps*.txt"
                                    )
                                )
                                if db_translated:
                                    lyrics_path = db_translated[0]
                                    print(
                                        f"✓ Found translated lyrics for most recent upload: {lyrics_path}"
                                    )
                                    break

                            # Last resort: search song folder
                            recent_folder_path = Path(recent_song.get('folder_path'))
                            if recent_folder_path.exists():
                                for lyrics_file in recent_folder_path.glob('*.txt'):
                                    file_lower = lyrics_file.name.lower()
                                    if 'translated' in file_lower and 'no_timestamps' in file_lower:
                                        lyrics_path = lyrics_file
                                        print(
                                            f"✓ Using translated lyrics from song folder: {lyrics_path}"
                                        )
                                        break

                            if lyrics_path:
                                break

                except Exception as e:
                    print(f"Error finding most recent upload lyrics: {e}")

                    
        # Final fallback: try database directory for any translated lyrics (NOT transcribed_lyrics.txt) (skip if Stay)
        if not lyrics_path and not is_stay_song:
            # Look for translated lyrics files in database directory
            db_translated_files = list(DATABASE_DIR.glob("*translated*no_timestamps*.txt"))
            if db_translated_files:
                # Use most recent translated lyrics file
                db_translated_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                lyrics_path = db_translated_files[0]
                print(f"⚠ Using most recent translated lyrics from database (may not match song): {lyrics_path}")
            else:
                print("⚠ No translated lyrics files found anywhere. Cannot perform voice comparison.")
        
        if not lyrics_path or not lyrics_path.exists():
            return jsonify({
                'status': 'warning',
                'message': 'Recording saved but translated lyrics not found for comparison. Please ensure the song has been processed with translation.',
                'recording_path': str(file_path),
                'filename': safe_filename,
                'note': 'Voice comparison requires translated lyrics (not English transcribed lyrics)'
            }), 200
        
        # Perform pronunciation comparison using SingingLanguageTrainer
        try:
            from singing_language_trainer import SingingLanguageTrainer
            
            # Initialize trainer with user profile
            profile_file = str(PROJECT_ROOT / "user_profile.json")
            trainer = SingingLanguageTrainer(profile_file=profile_file)
            
            # Verify file exists before processing
            if not file_path.exists():
                return jsonify({
                    'error': 'File not found',
                    'message': f'Recording file does not exist: {file_path}'
                }), 404
            
            # Check if file is readable
            try:
                file_size = file_path.stat().st_size
                if file_size == 0:
                    return jsonify({
                        'error': 'Empty file',
                        'message': 'Recording file is empty'
                    }), 400
            except Exception as e:
                return jsonify({
                    'error': 'File access error',
                    'message': f'Cannot access file: {str(e)}'
                }), 500
            
            # Process audio and compare with lyrics
            print(f"\n{'='*60}")
            print(f"Analyzing recording for song: {song_title}")
            print(f"  Audio: {final_audio_path} (size: {final_audio_path.stat().st_size} bytes)")
            print(f"  Lyrics: {lyrics_path}")
            if lyrics_path and lyrics_path.exists():
                lyrics_size = lyrics_path.stat().st_size
                with open(lyrics_path, 'r', encoding='utf-8') as f:
                    lyrics_content = f.read()
                    lyrics_preview = lyrics_content[:100].replace('\n', ' ')
                print(f"  Lyrics file size: {lyrics_size} bytes")
                print(f"  Lyrics preview: {lyrics_preview}...")
                # Verify this is the translated lyrics (not English)
                if 'translated_lyrics' in str(lyrics_path) and 'no_timestamps' in str(lyrics_path):
                    lang_info = 'unknown'
                    if song_data is not None:
                        lang_info = song_data.get('translation_language', 'unknown')
                    print(f"  ✓ Using TRANSLATED lyrics file (correct for language: {lang_info})")
                else:
                    print(f"  ⚠ Warning: May not be using translated lyrics file!")
            print(f"  Language code for comparison: {language}")
            print(f"{'='*60}\n")
            
            try:
                result = trainer.process_audio_and_lyrics(
                    audio_path=str(final_audio_path),
                    lyrics_path=str(lyrics_path),
                    language=language,
                    save_phonemes=False
                )
            except FileNotFoundError as e:
                return jsonify({
                    'error': 'Audio file not found',
                    'message': f'Could not find audio file: {str(e)}'
                }), 404
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error processing audio: {str(e)}")
                print(error_trace)
                return jsonify({
                    'error': 'Audio processing failed',
                    'message': f'Failed to process audio file: {str(e)}',
                    'hint': 'Make sure the audio file is a valid MP3/WAV file and librosa can read it'
                }), 500
            
            # Save updated profile
            trainer.save_profile(profile_file)
            
            # Extract scores from result
            accuracy = result.get('accuracy', 0.0)
            weighted_score = result.get('weighted_score', 0.0)
            weak_phonemes = result.get('weak_phonemes', [])
            line_accuracies = result.get('line_accuracies', [])
            word_errors_by_line = result.get('word_errors_by_line', [])
            
            # Calculate average line accuracy
            avg_line_accuracy = 0.0
            if line_accuracies:
                avg_line_accuracy = sum(line.get('accuracy', 0.0) for line in line_accuracies) / len(line_accuracies)
            
            # Get top 3 worst lines (lowest accuracy)
            worst_lines = sorted(line_accuracies, key=lambda x: x.get('accuracy', 1.0))[:3]
            worst_lines_formatted = [
                {
                    'line': line.get('line', 0),
                    'text': line.get('text', ''),
                    'accuracy': line.get('accuracy', 0.0)
                }
                for line in worst_lines
            ]
            
            print(f"\n{'='*60}")
            print(f"Analysis Complete!")
            print(f"  Overall Accuracy: {accuracy:.2%}")
            print(f"  Weighted Score: {weighted_score:.2%}")
            print(f"  Average Line Accuracy: {avg_line_accuracy:.2%}")
            print(f"\nTop 3 Worst Lines:")
            for line in worst_lines_formatted:
                print(f"  Line {line['line']}: {line['accuracy']:.2%} - {line['text'][:50]}")
            print(f"{'='*60}\n")
            
            # Save to database (recordings metadata)
            recording_metadata = {
                'song_id': song_id,
                'song_title': song_title,
                'recording_path': str(file_path),
                'filename': safe_filename,
                'accuracy': accuracy,
                'weighted_score': weighted_score,
                'avg_line_accuracy': avg_line_accuracy,
                'worst_lines': worst_lines_formatted,
                'analyzed_at': datetime.now().isoformat()
            }
            
            # Save to recordings metadata file
            recordings_metadata_file = DATABASE_DIR / "recordings_metadata.json"
            if recordings_metadata_file.exists():
                with open(recordings_metadata_file, 'r', encoding='utf-8') as f:
                    recordings_list = json.load(f)
            else:
                recordings_list = []
            
            recordings_list.append(recording_metadata)
            
            with open(recordings_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(recordings_list, f, indent=2, ensure_ascii=False)
            
            return jsonify({
                'status': 'success',
                'message': 'Recording analyzed successfully',
                'accuracy': accuracy,
                'weighted_score': weighted_score,
                'avg_line_accuracy': avg_line_accuracy,
                'weak_phonemes': weak_phonemes[:10],  # Top 10 weak phonemes
                'line_count': len(line_accuracies),
                'worst_lines': worst_lines_formatted,  # Top 3 worst lines
                'recording_path': str(final_audio_path),
                'filename': final_audio_path.name,
                'saved_to_db': True,
                'result': {
                    'accuracy': accuracy,
                    'weighted_score': weighted_score,
                    'avg_line_accuracy': avg_line_accuracy,
                    'weak_phonemes': weak_phonemes[:10],
                    'line_accuracies': line_accuracies[:5],  # Top 5 lines for display
                    'worst_lines': worst_lines_formatted
                }
            }), 200
            
        except ImportError:
            # If comparison modules not available, just save the recording
            return jsonify({
                'status': 'success',
                'message': 'Recording saved (comparison modules not available)',
                'recording_path': str(file_path),
                'filename': safe_filename
            }), 200
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error comparing recording: {str(e)}")
            print(error_trace)
            
            # Still return success but with warning
            return jsonify({
                'status': 'warning',
                'message': f'Recording saved but comparison failed: {str(e)}',
                'recording_path': str(file_path),
                'filename': safe_filename
            }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error saving song recording: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Failed to save recording',
            'message': str(e)
        }), 500


@app.route('/api/lessons/practice', methods=['POST'])
def save_practice_recording():
    """Save a practice recording for a lesson conversation."""
    try:
        if 'audio' not in request.files:
            return jsonify({
                'error': 'No audio file provided',
                'message': 'Please provide an audio file in the "audio" field'
            }), 400
        
        file = request.files['audio']
        conversation_index = request.form.get('conversation_index', '0')
        
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select an audio file'
            }), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"practice_{conversation_index}_{timestamp}_{filename}"
        file_path = UPLOAD_FOLDER / safe_filename
        file.save(str(file_path))
        
        # Try to convert to MP3 if possible
        mp3_path = None
        try:
            mp3_filename = f"practice_{conversation_index}_{timestamp}.mp3"
            mp3_path = UPLOAD_FOLDER / mp3_filename
            
            subprocess.run(
                ['ffmpeg', '-i', str(file_path), '-acodec', 'libmp3lame', '-ab', '192k', str(mp3_path)],
                check=True,
                capture_output=True,
                timeout=30
            )
            
            if mp3_path.exists():
                # Remove original if conversion successful
                try:
                    os.remove(file_path)
                except:
                    pass
                final_path = mp3_path
                final_filename = mp3_filename
            else:
                final_path = file_path
                final_filename = safe_filename
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # If conversion fails, use original file
            final_path = file_path
            final_filename = safe_filename
        
        return jsonify({
            'status': 'success',
            'message': 'Practice recording saved',
            'recording_path': str(final_path),
            'filename': final_filename,
            'conversation_index': conversation_index
        }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error saving practice recording: {str(e)}")
        print(error_trace)
        
        return jsonify({
            'error': 'Failed to save recording',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    # Run the Flask app
    print(f"\n{'='*60}")
    print("Music Video Processing API")
    print(f"{'='*60}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Database folder: {DATABASE_DIR}")
    print(f"\nEndpoints:")
    print(f"  GET  /health                - Health check")
    print(f"  POST /api/upload           - Upload song file (saves to database)")
    print(f"  GET  /api/songs            - List all uploaded songs")
    print(f"  POST /process              - Process file and return video")
    print(f"  POST /process-json         - Process file and return JSON with path")
    print(f"  GET  /download/<file>      - Download processed video")
    print(f"  GET  /database/metadata    - Get all video metadata")
    print(f"  GET  /database/metadata/<id> - Get specific video metadata")
    print(f"  POST /api/recordings/convert - Convert recording to MP3")
    print(f"  GET  /api/lessons          - Get user lessons")
    print(f"  POST /api/lessons/generate - Generate personalized lessons")
    print(f"  POST /api/lessons/practice - Save practice recording")
    print(f"\nStarting server on http://localhost:6767")
    print(f"{'='*60}\n")
    
    app.run(debug=True, host='0.0.0.0', port=6767)
