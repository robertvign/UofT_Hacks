"""
Flask API for Music Video Processing Pipeline
Accepts MP3 file, song name, and translation language(s)
Returns processed video with translated lyrics
"""

import os
import asyncio
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Import the main processing function
from music_video import process_music_video

# Initialize Flask app
app = Flask("Duosingo")

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'flac', 'ogg', 'mp4', 'mov', 'avi'}

# Create necessary directories
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

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
            loop.run_until_complete(
                process_music_video(song_name, file_path, translation_language)
            )
        finally:
            loop.close()
        
        # Check if output file was created
        final_video_path = OUTPUT_DIR / "final.mp4"
        
        if not final_video_path.exists():
            return jsonify({
                'error': 'Processing failed',
                'message': 'Video processing completed but output file was not found'
            }), 500
        
        # Return the video file
        return send_file(
            str(final_video_path),
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f"{song_name.replace(' ', '_')}_{translation_language}.mp4"
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
            loop.run_until_complete(
                process_music_video(song_name, file_path, translation_language)
            )
        finally:
            loop.close()
        
        # Check if output file was created
        final_video_path = OUTPUT_DIR / "final.mp4"
        
        if not final_video_path.exists():
            return jsonify({
                'error': 'Processing failed',
                'message': 'Video processing completed but output file was not found'
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': 'Video processed successfully',
            'video_path': str(final_video_path),
            'video_url': f'/download/{final_video_path.name}',
            'song_name': song_name,
            'translation_language': translation_language
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
    """Download a processed video file."""
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(
            str(file_path),
            mimetype='video/mp4',
            as_attachment=True
        )
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    # Run the Flask app
    print(f"\n{'='*60}")
    print("Music Video Processing API")
    print(f"{'='*60}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"\nEndpoints:")
    print(f"  GET  /health          - Health check")
    print(f"  POST /process         - Process file and return video")
    print(f"  POST /process-json    - Process file and return JSON with path")
    print(f"  GET  /download/<file> - Download processed video")
    print(f"\nStarting server on http://localhost:6767")
    print(f"{'='*60}\n")
    
    app.run(debug=True, host='0.0.0.0', port=6767)
