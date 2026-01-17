"""
Flask API for Music Video Processing Pipeline
Accepts MP3 file, song name, and translation language(s)
Returns processed video with translated lyrics
"""

import os
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Import the main processing function
from music_video import process_music_video

# Initialize Flask app
app = Flask("Duosingo")

# Enable CORS manually
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATABASE_DIR = PROJECT_ROOT / "database"
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
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


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'Music Video Processing API is running'
    }), 200


@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_song():
    """
    Upload a song file, run the full music-video pipeline, and save to the database.
    
    Expected form data:
    - file: Audio file (MP3, WAV, etc.)
    - song_name: Name of the song
    - translation_language: Target language for translation (defaults to "English" if empty)
    
    Returns:
    - JSON response with song information and metadata file path
    """
    if request.method == 'OPTIONS':
        return '', 204
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please provide an audio file in the "file" field'
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
        
        # Validate file extension
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed file types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Create database directory structure
        DATABASE_DIR.mkdir(exist_ok=True)
        
        # Create a folder for this song
        safe_song_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_song_name = safe_song_name.replace(' ', '_')
        song_folder = DATABASE_DIR / safe_song_name
        song_folder.mkdir(exist_ok=True)
        
        # Save the uploaded file
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{filename}"
        file_path = song_folder / safe_filename
        file.save(str(file_path))
        
        # Get file info
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        # Create metadata entry
        metadata_entry = {
            "id": len(list(DATABASE_DIR.glob("*/metadata.txt"))) + 1,
            "song_name": song_name,
            "translation_language": translation_language if translation_language else "Not specified",
            "original_filename": filename,
            "saved_filename": safe_filename,
            "file_path": str(file_path),
            "folder_path": str(song_folder),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size_mb, 2),
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_date": datetime.now().strftime("%Y-%m-%d"),
            "uploaded_time": datetime.now().strftime("%H:%M:%S"),
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
            f.write(f"Translation Language: {metadata_entry['translation_language']}\n")
            f.write(f"Original Filename: {filename}\n")
            f.write(f"Saved Filename: {safe_filename}\n")
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
        translation_lang = (translation_language or '').strip() or "English"
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                final_video_path = loop.run_until_complete(
                    process_music_video(song_name, str(file_path), translation_lang, save_to_database=True)
                )
            finally:
                loop.close()
        except Exception as proc_err:
            import traceback
            proc_trace = traceback.format_exc()
            print(f"Processing failed: {proc_err}\n{proc_trace}")
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
            f.write(f"Translation Language: {metadata_entry['translation_language']}\n")
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
            'translation_language': metadata_entry['translation_language'],
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
                            elif key == 'translation_language':
                                song_info['language'] = value
                                song_info['translation_language'] = value
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
                
                # Use folder name as ID (or generate one)
                song_info['id'] = hash(song_folder.name) % 1000000
                
                # Set defaults for frontend compatibility
                song_info['region'] = song_info.get('translation_language', 'Unknown')
                song_info['coverUrl'] = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80"
                song_info['progress'] = 100 if song_info.get('has_video') else 0
                song_info['isFavorite'] = False
                
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
    print(f"\nStarting server on http://localhost:6767")
    print(f"{'='*60}\n")
    
    app.run(debug=True, host='0.0.0.0', port=6767)
