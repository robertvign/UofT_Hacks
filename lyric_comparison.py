import re
import difflib

# --- Step 1: Read Genius lyrics ---
with open("genius_lyrics.txt", "r", encoding="utf-8") as f:
    genius_lines = [line.strip() for line in f if line.strip()]

# --- Step 2: Read audio transcription with timestamps ---
audio_lines = []
with open("transcribed_lyrics.txt", "r", encoding="utf-8") as f:
    for line in f:
        m = re.match(
            r"\[(\d+(?:\.\d+)?)s\s*[-–—>→]+\s*(\d+(?:\.\d+)?)s\]\s*(.+)",
            line
        )
        if m:
            start, end, text = m.groups()
            audio_lines.append((float(start), float(end), text.strip()))

print("AUDIO LINES:", len(audio_lines))


# --- Step 3: Fuzzy match Genius lines to audio lines ---
aligned_lines = []
#used_indices = set()  # To avoid duplicate matches
MAX_LOOKAHEAD = 30.0
last_end_time = 0.0

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def word_similarity(a, b):
    a_words = set(normalize(a).split())
    b_words = set(normalize(b).split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)

for g_line in genius_lines:
    best_ratio = 0
    best_match = None

    for start, end, a_line in audio_lines:
        if start < last_end_time:
            continue
        if last_end_time > 0 and start > last_end_time + MAX_LOOKAHEAD:
            break

        ratio = word_similarity(g_line, a_line)

        if ratio > best_ratio:
            best_ratio = ratio
            best_match = (start, end)

    #print(g_line, best_ratio)

    if best_ratio > 0.2 and best_match is not None:
        aligned_lines.append((best_match[0], best_match[1], g_line))
        last_end_time = best_match[1]
    else:
        aligned_lines.append((None, None, g_line))

# --- Step 4: Write output ---
with open("genius_with_timestamps.txt", "w", encoding="utf-8") as f:
    for i, (start, end, line) in enumerate(aligned_lines):

        if line.startswith("["):
            f.write(f"{line}\n")
            continue
        
        # Get previous end time
        prev_end = aligned_lines[i - 1][1] if i > 0 else None

        # Get next start time
        next_start = aligned_lines[i + 1][0] if i + 1 < len(aligned_lines) else None

        # Determine start time
        if start is None:
            if prev_end is not None:
                start_time = prev_end
            elif next_start is not None:
                start_time = max(0.0, next_start - 2.0)  # fallback before next line
            else:
                start_time = 0.0  # absolute fallback
        else:
            start_time = start

        # Determine end time
        if end is None:
            if next_start is not None:
                end_time = next_start
            else:
                end_time = start_time + 2.0  # fallback duration
        else:
            end_time = end

        f.write(f"[{start_time:.2f}s → {end_time:.2f}s] {line}\n")
