import os
from elevenlabs.client import ElevenLabs
import time

# 1. Initialize client with your API key
# Note: In a real project, keep this in your .env file!
client = ElevenLabs(
    api_key="7b81876c3068cb5ebce42c38ef0bb6ce4fd3574217f9f839faf649e4838f3a4d",
)

target_lang = "fr"  # Change this to "es" if you want Spanish
source_file = "lights_vocals.wav"

print(f"Starting dubbing for {source_file}...")

# 2. Open the file and start the dubbing project
# Replace the failing 'dub_a_video_or_an_audio_file' block with this:
with open(source_file, "rb") as audio_file:
    response = client.dubbing.create(
        file=(audio_file.name, audio_file, "audio/wav"),
        target_lang=target_lang,
        source_lang="en",
        num_speakers=1,
        watermark=True
    )

dubbing_id = response.dubbing_id
print(f"Project created! ID: {dubbing_id}")

# 3. Wait for the dubbing to complete
while True:
    metadata = client.dubbing.get_dubbing_project_metadata(dubbing_id)
    status = metadata.status
    
    if status == "finished":
        print("Dubbing successful! Downloading...")
        break
    elif status == "failed":
        print("Dubbing failed. Check your ElevenLabs dashboard for details.")
        exit()
    else:
        print(f"Current status: {status}... waiting 5 seconds.")
        time.sleep(5)

# 4. Download and save the dubbed file
output_filename = f"dubbed_{target_lang}.mp3"
dubbed_audio_generator = client.dubbing.get_dubbed_file(dubbing_id, target_lang)

with open(output_filename, "wb") as f:
    for chunk in dubbed_audio_generator:
        f.write(chunk)

print(f"Done! Your dubbed audio is saved as {output_filename}")