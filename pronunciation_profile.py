from collections import defaultdict

class UserPronunciationProfile:
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.total_counts = defaultdict(int)

    def update(self, ref_phonemes, user_phonemes):
        ref = ref_phonemes.split()
        usr = user_phonemes.split()

        for r, u in zip(ref, usr):
            self.total_counts[r] += 1
            if r != u:
                self.error_counts[r] += 1

    def weak_phonemes(self, threshold=0.4):
        weak = []
        for p in self.total_counts:
            error_rate = self.error_counts[p] / self.total_counts[p]
            if error_rate > threshold:
                weak.append(p)
        return weak

    def weighted_score(self, ref_phonemes, user_phonemes):
        ref = ref_phonemes.split()
        usr = user_phonemes.split()

        score = 0
        weight_sum = 0

        weak = self.weak_phonemes()

        for r, u in zip(ref, usr):
            weight = 2.0 if r in weak else 1.0
            score += weight * (1 if r == u else 0)
            weight_sum += weight

        return score / weight_sum
