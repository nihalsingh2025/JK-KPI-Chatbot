"""
Standalone test script for fuzzy-matching user input against known enum
values (product_type, section, etc). Run this on its own to see how well
different inputs match, and to tune FUZZY_THRESHOLD, before wiring the
logic into retrieval/enum_values.py.

Install first:
    pip install rapidfuzz
"""

from rapidfuzz import process, fuzz,utils

PRODUCT_TYPES = [
    "Bead Apex", "Bead Bundle", "Belt", "Belt Mother Roll", "Cap Strip",
    "Cap Strip Mother Roll", "Carcass", "Chaffer", "Chaffer Mother Roll",
    "Cured Tyre", "Final Compound", "Green Tyre", "Inner Liner",
    "Master Compound", "Ply", "Ply Mother Roll", "Sidewall", "Tread",
]

FUZZY_THRESHOLD = 60 # 0-100, tune based on results below


def fuzzy_match(user_word: str, choices: list, threshold: int = FUZZY_THRESHOLD):
    """
    Returns (best_match, score) if score >= threshold, else None.
    """
    result = process.extractOne(user_word, choices, scorer=fuzz.WRatio,processor=utils.default_process)
    if result is None:
        return None
    match, score, _ = result
    if score >= threshold:
        return match, score
    return None


# --- test cases: intentionally misspelled / spaced-out inputs ---
test_inputs = [
    "sidewal",        # missing letter
    "side wall",      # extra space
    "sidewall",       # exact match
    "inerliner",      # missing letter, no space
    "inner liner",    # exact with space
    "innr linr",      # multiple typos
    "tread",          # exact match
    "traed",          # swapped letters
    "belt mothr roll",# typo in middle word
    "carcas",         # missing letter
    "xyzabc",         # should NOT match anything (below threshold)
]

if __name__ == "__main__":
    print(f"{'Input':<20} {'Matched to':<25} {'Score':<8} {'Accepted?'}")
    print("-" * 65)
    for word in test_inputs:
        result = fuzzy_match(word, PRODUCT_TYPES)
        if result:
            match, score = result
            print(f"{word:<20} {match:<25} {score:<8.1f} YES")
        else:
            # show the closest match anyway, just to see how close it was
            closest = process.extractOne(word, PRODUCT_TYPES, scorer=fuzz.WRatio)
            closest_str = f"{closest[0]} ({closest[1]:.1f})" if closest else "none"
            print(f"{word:<20} {'-':<25} {'-':<8} NO (closest: {closest_str})")