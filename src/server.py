from flask import Flask, request, send_file
from moviepy.editor import AudioFileClip, ImageClip
import os
import uuid

app = Flask("Duosingo")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert_mp3_to_mp4():
    # Check if file is in request
    if "file" not in request.files:
        return {"error": "No file part"}, 400

    file = request.files["file"]
    if file.filename == "":
        return {"error": "No selected file"}, 400

    # Save the uploaded MP3
    unique_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}.mp3")
    file.save(input_path)

    # Create an MP4 with a static image (replace with your own if you want)
    image_path = "cover.jpg"  # Make sure this exists
    output_path = os.path.join(OUTPUT_FOLDER, f"{unique_id}.mp4")

    audio_clip = AudioFileClip(input_path)
    image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
    image_clip = image_clip.set_audio(audio_clip)

    image_clip.write_videofile(output_path, fps=24)

    # Clean up the uploaded audio if you want
    os.remove(input_path)

    # Return the MP4
    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
