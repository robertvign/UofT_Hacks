import re
import difflib

# --- Step 1: Read Genius lyrics ---
with open("genius_lyrics.txt", "r", encoding="utf-8") as f:
    genius_lines = [line.strip() for line in f if line.strip()]

# --- Step 2: Read audio transcription with timestamps ---
audio_lines = []
with open("transcribed_lyrics.txt", "r", encoding="utf-8") as f:
    for line in f:
        m = re.match(r"\[(\d+\.?\d*)s → (\d+\.?\d*)s\] (.+)", line)
        if m:
            start, end, text = m.groups()
            audio_lines.append((float(start), float(end), text.strip()))

# --- Step 3: Fuzzy match Genius lines to audio lines ---
aligned_lines = []
used_indices = set()  # To avoid duplicate matches
last_end_time = 0.0

for g_line in genius_lines:
    best_ratio = 0
    best_match = None
    best_idx = None

    for i, (start, end, a_line) in enumerate(audio_lines):
        if i in used_indices:
            continue
        if start < last_end_time:
            continue
        ratio = difflib.SequenceMatcher(None, g_line.lower(), a_line.lower()).ratio()
        if ratio > best_ratio:
            #
            best_ratio = ratio
            best_match = (start, end, a_line)
            best_idx = i

    if best_ratio > 0.6:  # You can adjust the threshold
        aligned_lines.append((best_match[0], best_match[1], g_line))
        used_indices.add(best_idx)
        #last_end_time = best_match[1]
    else:
        # If no good match, leave timestamps empty
        aligned_lines.append((None, None, g_line))

# --- Step 4: Write output ---
with open("genius_with_timestamps.txt", "w", encoding="utf-8") as f:
    for start, end, line in aligned_lines:
        if start is not None:
            f.write(f"[{start:.2f}s → {end:.2f}s] {line}\n")
        else:
            f.write(f"{line}\n")
