try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False


def _levenshtein_distance(s1, s2):
    """
    Compute Levenshtein distance between two sequences.
    Pure Python implementation if python-Levenshtein is not available.
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def phoneme_accuracy(reference, predicted):
    """
    Calculate phoneme accuracy using Levenshtein distance.
    
    Args:
        reference: Reference phonemes (space-separated string)
        predicted: Predicted phonemes (space-separated string)
    
    Returns:
        Accuracy score between 0.0 and 1.0
    """
    ref = reference.split()
    pred = predicted.split()
    
    if HAS_LEVENSHTEIN:
        distance = Levenshtein.distance(ref, pred)
    else:
        distance = _levenshtein_distance(ref, pred)
    
    max_len = max(len(ref), len(pred))
    
    if max_len == 0:
        return 1.0
    
    return 1.0 - (distance / max_len)
