import requests
import io
from bs4 import BeautifulSoup

GENIUS_TOKEN = "puRi9AvrjaHDN5TtbcyThRgFPYBHvX8_XnMVJgVvaSnV9HnhNDRtjshJ3rh-Ej4w"


def get_song_url(song_title, artist_name):
    search_url = "https://api.genius.com/search"
    headers = {
        "Authorization": f"Bearer {GENIUS_TOKEN}"
    }
    params = {
        "q": f"{song_title} {artist_name}"
    }

    response = requests.get(search_url, headers=headers, params=params)
    print("Status code: ", response.status_code)
    print("Response Text: ", response.text)
    #response.raise_for_status()

    data = response.json()
    hits = data["response"]["hits"]

    if not hits:
        raise Exception("No song found on Genius.")

    return hits[0]["result"]["url"]


def get_lyrics(song_url):
    page = requests.get(song_url)
    page.raise_for_status()

    soup = BeautifulSoup(page.text, "html.parser")

    lyrics_containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})

    lyrics = "\n".join(
        container.get_text(separator="\n") for container in lyrics_containers
    )

    return lyrics.strip()

def save_lyrics_to_file(lyrics):
    tempString = io.StringIO(lyrics)
    line = tempString.readline()
    while line and "[" not in line:
        line = tempString.readline()
    newText = line + tempString.read()
    with open("genius_lyrics.txt", "w", encoding="utf-8") as file:
        file.write(newText)



    print(f"Lyrics saved to genius_lyrics")


if __name__ == "__main__":
    global song
    song = input("Enter song title: ")
    artist = input("Enter artist name: ")

    url = get_song_url(song, artist)
    print("\nGenius URL:", url)

    lyrics = get_lyrics(url)

    save_lyrics_to_file(lyrics)