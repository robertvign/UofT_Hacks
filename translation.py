from deep_translator import GoogleTranslator

input_file = "lyricsTest.txt"
output_file = "lyrics_translated.txt"

source_lang = "en"
target_lang = "es"  # Spanish

translator = GoogleTranslator(source=source_lang, target=target_lang)

with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "w", encoding="utf-8") as outfile:

    for line in infile:
        line = line.strip()

        if not line:
            outfile.write("\n")
            continue

        translated = translator.translate(line)
        outfile.write(translated + "\n")

print("Translation complete!")
