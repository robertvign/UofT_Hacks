# Database Folder

This folder contains all processed music videos and their metadata.

## Structure

- **Videos**: All final processed music videos are stored here with unique filenames
- **videos_metadata.json**: JSON file containing structured metadata about all videos
- **videos_metadata.txt**: Human-readable text file with video information

## Metadata Format

Each video entry includes:
- `id`: Unique identifier
- `song_name`: Name of the song
- `translation_language`: Target language for translation
- `video_filename`: Name of the video file
- `video_path`: Full path to the video file
- `original_file`: Original input file (if available)
- `file_size_bytes`: File size in bytes
- `file_size_mb`: File size in megabytes
- `created_at`: ISO timestamp of creation
- `created_date`: Date of creation (YYYY-MM-DD)
- `created_time`: Time of creation (HH:MM:SS)

## Accessing Videos

Videos can be accessed via:
- Direct file access from this folder
- API endpoint: `GET /download/<filename>`
- API endpoint: `GET /database/metadata` (to view all metadata)

