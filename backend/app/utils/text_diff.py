"""
Text comparison and difference analysis utilities
"""
import difflib
from typing import List, Dict, Tuple
from app.utils.logger import logger


class DiffWord:
    """Diff word representation"""

    def __init__(self, word: str, status: str, original_index: int = None, user_index: int = None):
        self.word = word
        self.status = status  # 'correct', 'missing', 'extra', 'incorrect'
        self.original_index = original_index
        self.user_index = user_index

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "word": self.word,
            "status": self.status,
            "original_index": self.original_index,
            "user_index": self.user_index
        }


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    # Convert to lowercase
    text = text.lower()

    # Remove extra whitespace
    text = " ".join(text.split())

    # Remove punctuation (keep apostrophes)
    import re
    text = re.sub(r'[^\w\']', ' ', text)

    return text.strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity ratio using SequenceMatcher

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity ratio (0.0 to 1.0)
    """
    words1 = normalize_text(text1).split()
    words2 = normalize_text(text2).split()

    matcher = difflib.SequenceMatcher(None, words1, words2)
    return matcher.ratio()


def compare_texts(original_text: str, user_text: str) -> Dict:
    """
    Compare original text with user text and generate detailed diff report

    Args:
        original_text: Target/correct text
        user_text: User spoken/transcribed text

    Returns:
        Dictionary containing:
        - score: Similarity score (0-100)
        - diff_words: List of DiffWord objects
        - correct_count: Number of correct words
        - total_count: Total word count in original
        - missing_count: Number of missing words
        - extra_count: Number of extra words
    """
    # Normalize texts
    orig_normalized = normalize_text(original_text)
    user_normalized = normalize_text(user_text)

    orig_words = orig_normalized.split()
    user_words = user_normalized.split()

    logger.debug(f"Comparing texts:")
    logger.debug(f"  Original: {orig_normalized}")
    logger.debug(f"  User:     {user_normalized}")

    # Calculate similarity
    matcher = difflib.SequenceMatcher(None, orig_words, user_words)
    similarity_ratio = matcher.ratio()
    score = int(similarity_ratio * 100)

    # Generate diff words
    diff_words = []
    correct_count = 0
    missing_count = 0
    extra_count = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Correct words
            for idx, word in enumerate(orig_words[i1:i2]):
                diff_words.append(DiffWord(
                    word=word,
                    status='correct',
                    original_index=i1 + idx,
                    user_index=j1 + idx
                ))
                correct_count += 1

        elif tag == 'delete':
            # Missing words (in original but not in user)
            for idx, word in enumerate(orig_words[i1:i2]):
                diff_words.append(DiffWord(
                    word=word,
                    status='missing',
                    original_index=i1 + idx,
                    user_index=None
                ))
                missing_count += 1

        elif tag == 'insert':
            # Extra words (in user but not in original)
            for idx, word in enumerate(user_words[j1:j2]):
                diff_words.append(DiffWord(
                    word=word,
                    status='extra',
                    original_index=None,
                    user_index=j1 + idx
                ))
                extra_count += 1

        elif tag == 'replace':
            # Incorrect words (different words)
            orig_segment = orig_words[i1:i2]
            user_segment = user_words[j1:j2]

            # Handle mismatched lengths
            max_len = max(len(orig_segment), len(user_segment))

            for idx in range(max_len):
                if idx < len(orig_segment):
                    diff_words.append(DiffWord(
                        word=orig_segment[idx],
                        status='missing',
                        original_index=i1 + idx,
                        user_index=None
                    ))
                    missing_count += 1

                if idx < len(user_segment):
                    diff_words.append(DiffWord(
                        word=user_segment[idx],
                        status='extra',
                        original_index=None,
                        user_index=j1 + idx
                    ))
                    extra_count += 1

    result = {
        "score": score,
        "diff_words": [dw.to_dict() for dw in diff_words],
        "correct_count": correct_count,
        "total_count": len(orig_words),
        "missing_count": missing_count,
        "extra_count": extra_count
    }

    logger.info(f"Comparison result: score={score}, correct={correct_count}/{len(orig_words)}")

    return result


def highlight_diff_text(original_text: str, user_text: str) -> str:
    """
    Generate HTML-highlighted diff text for display

    Args:
        original_text: Original text
        user_text: User text

    Returns:
        HTML string with highlighted differences
    """
    diff_result = compare_texts(original_text, user_text)

    html_parts = []
    for dw_dict in diff_result["diff_words"]:
        word = dw_dict["word"]
        status = dw_dict["status"]

        if status == "correct":
            html_parts.append(f'<span class="text-green-500">{word}</span>')
        elif status == "missing":
            html_parts.append(f'<span class="text-red-500 line-through">{word}</span>')
        elif status == "extra":
            html_parts.append(f'<span class="text-yellow-500 underline">{word}</span>')

    return " ".join(html_parts)


def get_accuracy_level(score: int) -> str:
    """
    Get accuracy level description based on score

    Args:
        score: Score (0-100)

    Returns:
        Accuracy level description
    """
    if score >= 90:
        return "优秀"
    elif score >= 75:
        return "良好"
    elif score >= 60:
        return "及格"
    else:
        return "需改进"


def calculate_word_accuracy(original_text: str, user_text: str) -> Dict[str, int]:
    """
    Calculate word-level accuracy metrics

    Args:
        original_text: Original text
        user_text: User text

    Returns:
        Dictionary with accuracy metrics
    """
    diff_result = compare_texts(original_text, user_text)

    total = diff_result["total_count"]
    correct = diff_result["correct_count"]

    if total > 0:
        accuracy = (correct / total) * 100
    else:
        accuracy = 0

    return {
        "accuracy": round(accuracy, 2),
        "correct": correct,
        "total": total,
        "missing": diff_result["missing_count"],
        "extra": diff_result["extra_count"]
    }
