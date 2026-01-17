# Install: pip install backboard-sdk
import asyncio
from backboard import BackboardClient

async def main():
    # Initialize the Backboard client
    client = BackboardClient(api_key="puRi9AvrjaHDN5TtbcyThRgFPYBHvX8_XnMVJgVvaSnV9HnhNDRtjshJ3rh-Ej4w")

    # Create an assistant
    assistant = await client.create_assistant(
        messages=[{"role": "system", "content": "You are a helpful assistant"}]
        #system_prompt="A helpful assistant"
    )

    # Create a thread
    thread = await client.create_thread(assistant.assistant_id)

    with open("genius_lyrics.txt", "r", encoding="utf-8") as file:
        geniuslyrics = file.read()

    with open("transcribed_lyrics.txt", "r", encoding="utf-8") as file:
        transcribedlyrics = file.read()

    # Send a message and get the complete response
    response = await client.add_message(
        thread_id=thread.thread_id,
        content="Take " + geniuslyrics + " and " + transcribedlyrics + " and compare them, if two lines are similar enough, take the timestamp from the transcribed file and insert it in the relevant line in the genius file, then store the genius file with the appropriate timestamps",
        llm_provider="google",
        model_name="gemini-2.5-flash",
        stream=False
    )

    # Print the AI's response
    #print(response.content)
    with open("genius_with_timestamps.txt", "w", encoding="utf-8") as file:
        file.write(response.content)

if __name__ == "__main__":
    asyncio.run(main())
