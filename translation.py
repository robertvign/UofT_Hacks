# Install: pip install backboard-sdk
import asyncio
from backboard import BackboardClient
import lyricgeneration as lyricsGeneration


async def main():
    # Initialize the Backboard client
    client = BackboardClient(api_key="espr_PvloS1GoOKc5snLiAyoB84OATVTEiBabkZO002VmnIg")

    # Create an assistant
    assistant = await client.create_assistant(
        name="Translator Assistant",
        system_prompt="A helpful assistant"
    )

    # Create a thread
    thread = await client.create_thread(assistant.assistant_id)

    # Send a message and get the complete response
    response = await client.add_message(
        thread_id=thread.thread_id,
        content="Translate these lyrics, maintainging the line structure, tone, and approximate number of syllables, while still mostly keeping word-for-word accuracy because it is for translation practice purposes. \n" + "abc"
        llm_provider="openai",
        model_name="gpt-4o",
        stream=False
    )

    # Print the AI's response
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())