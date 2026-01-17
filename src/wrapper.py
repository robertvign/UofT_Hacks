# Install: pip install backboard-sdk
import asyncio
from backboard import BackboardClient
import os

async def main():
    # --- Initialize the Backboard client ---
    api_key = os.environ.get("puRi9AvrjaHDN5TtbcyThRgFPYBHvX8_XnMVJgVvaSnV9HnhNDRtjshJ3rh-Ej4w")
    client = BackboardClient(api_key=api_key)

    # --- Create the assistant with name & description ---
    assistant = await client.create_assistant(
        name="Lyrics Timestamp Aligner",
        description="A tool to match Genius lyrics with timestamps from transcribed lyrics"
    )

    # --- Create a thread under that assistant ---
    thread = await client.create_thread(assistant.assistant_id)

    # --- Read files ---
    with open("genius_lyrics.txt", "r", encoding="utf-8") as f:
        genius_lyrics = f.read()

    with open("transcribed_lyrics.txt", "r", encoding="utf-8") as f:
        transcribed_lyrics = f.read()

    # --- Build a clear prompt ---
    prompt = f"""
You are a text processor.

We have two sets of text:

GENIUS LYRICS:
{genius_lyrics}

TRANSCRIBED LYRICS WITH TIME STAMPS:
{transcribed_lyrics}

Your task:
1. For each line in the Genius lyrics, find a matching line in the transcription.
2. If a match is found, insert the timestamp from the transcribed text before that line in the format [start → end].
3. If the line begins with '[', DO NOT add a timestamp — just output the line as is.
4. If a Genius line has no match, generate a reasonable timestamp using nearby lines.
5. Output the full Genius lyrics with timestamps exactly as text.
"""

    # --- Send the message to the assistant ---
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        llm_provider="google",
        model_name="gemini-2.5-flash",
        stream=False
    )

    # --- Write the output text to file ---
    with open("genius_with_timestamps.txt", "w", encoding="utf-8") as out:
        out.write(response.content)

    print("Done — output written to genius_with_timestamps.txt")

if __name__ == "__main__":
    asyncio.run(main())
