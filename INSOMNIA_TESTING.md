# Testing the API with Insomnia

## Step 1: Start the Server

First, start the Flask server:

```bash
cd /Users/ryan/Developer/UofT_Hacks
python src/server.py
```

You should see:
```
============================================================
Music Video Processing API
============================================================
Upload folder: /Users/ryan/Developer/UofT_Hacks/uploads
Output folder: /Users/ryan/Developer/UofT_Hacks/output
...
Starting server on http://localhost:5000
============================================================
```

## Step 2: Set Up Insomnia Requests

### Request 1: Health Check

**Method:** `GET`  
**URL:** `http://localhost:5000/health`

**Headers:** None needed

**Expected Response:**
```json
{
  "status": "healthy",
  "message": "Music Video Processing API is running"
}
```

---

### Request 2: Process Music (Returns Video File)

**Method:** `POST`  
**URL:** `http://localhost:5000/process`

**Body Type:** `Multipart Form`

**Form Fields:**
- `file` (File): Select your MP3/audio file
  - Click the dropdown next to the field name
  - Select "File" (not "Text")
  - Click "Choose File" and select your audio file
- `song_name` (Text): Name of the song
  - Example: `"The Weeknd - Blinding Lights"`
  - Example: `"Taylor Swift - Anti-Hero"`
- `translation_language` (Text): Target language
  - Example: `"spanish"`
  - Example: `"french"`
  - Example: `"german"`

**Expected Response:**
- A video file download (MP4 format)
- The file will be named like: `The_Weeknd_-_Blinding_Lights_spanish.mp4`

**Note:** This request may take several minutes as it processes the entire pipeline (transcription, translation, video generation).

---

### Request 3: Process Music (Returns JSON)

**Method:** `POST`  
**URL:** `http://localhost:5000/process-json`

**Body Type:** `Multipart Form`

**Form Fields:** (Same as Request 2)
- `file` (File): Your MP3/audio file
- `song_name` (Text): Name of the song
- `translation_language` (Text): Target language

**Expected Response:**
```json
{
  "status": "success",
  "message": "Video processed successfully",
  "video_path": "/Users/ryan/Developer/UofT_Hacks/output/final.mp4",
  "video_url": "/download/final.mp4",
  "song_name": "The Weeknd - Blinding Lights",
  "translation_language": "spanish"
}
```

---

### Request 4: Download Processed Video

**Method:** `GET`  
**URL:** `http://localhost:5000/download/final.mp4`

**Headers:** None needed

**Expected Response:**
- Video file download

**Note:** Use this after `/process-json` to download the video file separately.

---

## Insomnia Setup Steps

1. **Create a New Request:**
   - Click the "+" button in Insomnia
   - Select "New Request"
   - Name it (e.g., "Health Check")

2. **Set Method and URL:**
   - Select the HTTP method (GET, POST, etc.)
   - Enter the full URL: `http://localhost:5000/health`

3. **For POST Requests with Files:**
   - Go to the "Body" tab
   - Select "Multipart Form" from the dropdown
   - Click "Add" to add fields:
     - For `file`: Click the field type dropdown → Select "File" → Click "Choose File"
     - For `song_name` and `translation_language`: Keep as "Text" and enter values

4. **Send Request:**
   - Click the "Send" button
   - View response in the right panel

## Example Test Flow

1. **Test Health Check:**
   - GET `http://localhost:5000/health`
   - Should return `{"status": "healthy"}`

2. **Process a Song:**
   - POST `http://localhost:5000/process-json`
   - Body: 
     - `file`: [Select your MP3 file]
     - `song_name`: `"The Weeknd - Blinding Lights"`
     - `translation_language`: `"spanish"`
   - Wait for processing (may take 2-5 minutes)
   - Should return JSON with video path

3. **Download Video:**
   - GET `http://localhost:5000/download/final.mp4`
   - Should download the processed video

## Troubleshooting

- **Connection Refused:** Make sure the server is running (`python src/server.py`)
- **400 Bad Request:** Check that all required fields are filled (file, song_name, translation_language)
- **500 Internal Server Error:** Check server console for error messages
- **File Not Found:** Make sure you're using a valid audio file format (MP3, WAV, etc.)

## Tips

- Start with the health check to verify the server is running
- Use `/process-json` first to see if processing succeeded before downloading
- Processing can take several minutes - be patient!
- Check the server console for progress updates

