from collections import defaultdict
import json
from pathlib import Path


class UserPronunciationProfile:
    """
    Tracks user's pronunciation errors and builds a personalized error dictionary.
    This dictionary accumulates over time as the user sings more songs.
    """
    
    def __init__(self, profile_file=None):
        """
        Initialize pronunciation profile.
        
        Args:
            profile_file: Optional path to save/load profile from (for persistence)
        """
        # Phoneme-level tracking
        self.error_counts = defaultdict(int)
        self.total_counts = defaultdict(int)
        
        # Word-level error tracking (for error dictionary)
        # Structure: {word: {'count': int, 'errors': int, 'ref_phonemes': str, 'user_phonemes_list': [str]}}
        self.word_errors = defaultdict(lambda: {
            'count': 0,
            'errors': 0,
            'ref_phonemes': '',
            'user_phonemes_list': [],
            'error_rate': 0.0
        })
        
        # Phoneme substitution patterns (which phonemes user substitutes)
        # Structure: {ref_phoneme: {user_phoneme: count}}
        self.phoneme_substitutions = defaultdict(lambda: defaultdict(int))
        
        self.profile_file = profile_file
        if profile_file and Path(profile_file).exists():
            self.load(profile_file)
    
    def update(self, ref_phonemes, user_phonemes, words=None, line_text=None):
        """
        Update profile with phoneme and word-level errors.
        
        Args:
            ref_phonemes: Reference phonemes (space-separated string or list)
            user_phonemes: User phonemes (space-separated string or list)
            words: Optional list of words corresponding to phonemes (for word-level tracking)
            line_text: Optional line text for context
        """
        # Handle both string and list inputs
        if isinstance(ref_phonemes, list):
            ref = ref_phonemes
        else:
            ref = ref_phonemes.split() if ref_phonemes else []
        
        if isinstance(user_phonemes, list):
            usr = user_phonemes
        else:
            usr = user_phonemes.split() if user_phonemes else []
        
        # Update phoneme-level tracking
        for r, u in zip(ref, usr):
            self.total_counts[r] += 1
            if r != u:
                self.error_counts[r] += 1
                # Track substitutions
                self.phoneme_substitutions[r][u] += 1
        
        # Update word-level tracking if words provided
        if words:
            ref_phoneme_list = ref if isinstance(ref, list) else ref.split()
            user_phoneme_list = usr if isinstance(usr, list) else usr.split()
            
            # Map words to phonemes (approximate)
            phonemes_per_word = len(ref_phoneme_list) / len(words) if words else 0
            word_idx = 0
            
            for i, word in enumerate(words):
                if i >= len(words):
                    break
                
                # Get phonemes for this word
                start_idx = int(i * phonemes_per_word)
                end_idx = int((i + 1) * phonemes_per_word)
                
                ref_word_phonemes = ' '.join(ref_phoneme_list[start_idx:end_idx])
                user_word_phonemes = ' '.join(user_phoneme_list[start_idx:end_idx]) if start_idx < len(user_phoneme_list) else ""
                
                # Update word error tracking
                word_key = word.lower().strip('.,!?;:()[]{}"\'').strip()
                if word_key:
                    self.word_errors[word_key]['count'] += 1
                    self.word_errors[word_key]['ref_phonemes'] = ref_word_phonemes
                    self.word_errors[word_key]['user_phonemes_list'].append(user_word_phonemes)
                    
                    # Check if word has errors
                    if ref_word_phonemes != user_word_phonemes:
                        self.word_errors[word_key]['errors'] += 1
                    
                    # Update error rate
                    if self.word_errors[word_key]['count'] > 0:
                        self.word_errors[word_key]['error_rate'] = (
                            self.word_errors[word_key]['errors'] / 
                            self.word_errors[word_key]['count']
                        )
    
    def weak_phonemes(self, threshold=0.4):
        """Get phonemes with error rate above threshold."""
        weak = []
        for p in self.total_counts:
            if self.total_counts[p] > 0:
                error_rate = self.error_counts[p] / self.total_counts[p]
                if error_rate > threshold:
                    weak.append(p)
        return weak
    
    def weak_words(self, threshold=0.3, min_count=1):
        """
        Get words with error rate above threshold.
        These are words the user struggles with.
        
        Args:
            threshold: Error rate threshold (default: 0.3 = 30%)
            min_count: Minimum number of occurrences to consider (default: 1)
        
        Returns:
            List of dictionaries with word info, sorted by error rate (worst first)
        """
        weak_words_list = []
        
        for word, data in self.word_errors.items():
            if data['count'] >= min_count and data['error_rate'] >= threshold:
                weak_words_list.append({
                    'word': word,
                    'error_rate': data['error_rate'],
                    'count': data['count'],
                    'errors': data['errors'],
                    'ref_phonemes': data['ref_phonemes'],
                    'common_user_phonemes': self._get_most_common_user_phoneme(word)
                })
        
        # Sort by error rate (worst first)
        weak_words_list.sort(key=lambda x: (x['error_rate'], x['errors']), reverse=True)
        return weak_words_list
    
    def _get_most_common_user_phoneme(self, word):
        """Get the most common user pronunciation for a word."""
        if word not in self.word_errors:
            return ""
        
        user_phonemes_list = self.word_errors[word]['user_phonemes_list']
        if not user_phonemes_list:
            return ""
        
        # Count occurrences
        from collections import Counter
        counter = Counter(user_phonemes_list)
        return counter.most_common(1)[0][0] if counter else ""
    
    def get_error_dictionary(self, min_errors=1):
        """
        Get error dictionary - words/phonemes the user struggles with.
        This is used for relearning algorithm.
        
        Returns:
            Dictionary with error patterns
        """
        error_dict = {
            'weak_phonemes': {},
            'weak_words': [],
            'phoneme_substitutions': {}
        }
        
        # Get weak phonemes with error rates
        for phoneme in self.total_counts:
            if self.total_counts[phoneme] > 0:
                error_rate = self.error_counts[phoneme] / self.total_counts[phoneme]
                if self.error_counts[phoneme] >= min_errors:
                    error_dict['weak_phonemes'][phoneme] = {
                        'error_rate': error_rate,
                        'total_count': self.total_counts[phoneme],
                        'error_count': self.error_counts[phoneme],
                        'most_common_substitution': self._get_most_common_substitution(phoneme)
                    }
        
        # Get weak words
        error_dict['weak_words'] = self.weak_words(threshold=0.2, min_count=min_errors)
        
        # Get phoneme substitution patterns
        for ref_phoneme, substitutions in self.phoneme_substitutions.items():
            if substitutions:
                error_dict['phoneme_substitutions'][ref_phoneme] = dict(substitutions)
        
        return error_dict
    
    def _get_most_common_substitution(self, ref_phoneme):
        """Get most common substitution for a reference phoneme."""
        if ref_phoneme not in self.phoneme_substitutions:
            return None
        
        substitutions = self.phoneme_substitutions[ref_phoneme]
        if not substitutions:
            return None
        
        # Return most common substitution
        return max(substitutions.items(), key=lambda x: x[1])[0]
    
    def weighted_score(self, ref_phonemes, user_phonemes):
        """Calculate weighted accuracy score."""
        ref = ref_phonemes.split()
        usr = user_phonemes.split()
        
        score = 0
        weight_sum = 0
        weak = self.weak_phonemes()
        
        for r, u in zip(ref, usr):
            weight = 2.0 if r in weak else 1.0
            score += weight * (1 if r == u else 0)
            weight_sum += weight
        
        return score / weight_sum if weight_sum > 0 else 0.0
    
    def save(self, profile_file=None):
        """Save profile to file for persistence."""
        save_path = profile_file or self.profile_file
        if not save_path:
            return
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        profile_data = {
            'error_counts': dict(self.error_counts),
            'total_counts': dict(self.total_counts),
            'word_errors': {k: {
                'count': v['count'],
                'errors': v['errors'],
                'ref_phonemes': v['ref_phonemes'],
                'user_phonemes_list': v['user_phonemes_list'][-10:],  # Keep last 10
                'error_rate': v['error_rate']
            } for k, v in self.word_errors.items()},
            'phoneme_substitutions': {
                k: dict(v) for k, v in self.phoneme_substitutions.items()
            }
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
    
    def load(self, profile_file):
        """Load profile from file."""
        profile_file = Path(profile_file)
        if not profile_file.exists():
            return
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            self.error_counts = defaultdict(int, profile_data.get('error_counts', {}))
            self.total_counts = defaultdict(int, profile_data.get('total_counts', {}))
            
            # Load word errors
            word_errors_data = profile_data.get('word_errors', {})
            for word, data in word_errors_data.items():
                self.word_errors[word] = {
                    'count': data.get('count', 0),
                    'errors': data.get('errors', 0),
                    'ref_phonemes': data.get('ref_phonemes', ''),
                    'user_phonemes_list': data.get('user_phonemes_list', []),
                    'error_rate': data.get('error_rate', 0.0)
                }
            
            # Load phoneme substitutions
            substitutions_data = profile_data.get('phoneme_substitutions', {})
            for ref_phoneme, substitutions in substitutions_data.items():
                self.phoneme_substitutions[ref_phoneme] = defaultdict(int, substitutions)
        except Exception as e:
            print(f"Warning: Could not load profile: {e}")
