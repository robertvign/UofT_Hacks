# Install: pip install backboard-sdk
import asyncio
from backboard import BackboardClient
import lyricgeneration as lyricsGeneration


async def main():
    # Initialize the Backboard client

    with open("transcribed_lyrics.txt", "r", encoding="utf-8") as file:
        lyrics = file.read()

    client = BackboardClient(api_key="espr_-E7xd5n6PKHueWcNykyoDWDE3hewLEWyduHKDXmhKSI")

    # Create an assistant
    assistant = await client.create_assistant(
        name="Translator Assistant"
    )

    # Create a thread
    thread = await client.create_thread(assistant.assistant_id)

    # Send a message and get the complete response
    response = await client.add_message(
        thread_id=thread.thread_id,
        content="This is my own writing, and i need the whole file translated into spanish. output only the translated lines, maintaining a similar tone. Leave the info enclosed in [] as unchanged." + lyrics,
        llm_provider="google",
        model_name="gemini-2.5-flash",
        stream=False
    )

    # Print the AI's response
    with open("translated_genius_lyrics.txt", "w", encoding="utf-8") as file:
        file.write(response.content)
    print("file written")

if __name__ == "__main__":
    asyncio.run(main())