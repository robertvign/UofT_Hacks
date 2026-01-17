import Levenshtein

def phoneme_accuracy(reference, predicted):
    ref = reference.split()
    pred = predicted.split()

    distance = Levenshtein.distance(ref, pred)
    max_len = max(len(ref), len(pred))

    return 1.0 - (distance / max_len)
