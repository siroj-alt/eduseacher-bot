"""Ingliz tili daraja testi (A1–C1): 15 ta savol, har darajadan 3 tadan."""
from typing import Optional

LEVELS = ["A1", "A2", "B1", "B2", "C1"]

# (daraja, savol, variantlar, to'g'ri variant indeksi)
QUESTIONS = [
    ("A1", "She ___ a teacher.", ["is", "are", "am", "be"], 0),
    ("A1", "I ___ coffee every morning.", ["drinks", "drinking", "drink", "to drink"], 2),
    ("A1", "___ is your name?", ["Where", "What", "Who", "Why"], 1),
    ("A2", "Yesterday we ___ to the cinema.", ["go", "goes", "going", "went"], 3),
    ("A2", "There isn't ___ milk in the fridge.", ["any", "some", "many", "a"], 0),
    ("A2", "My brother is ___ than me.", ["tall", "more tall", "taller", "tallest"], 2),
    ("B1", "If it rains tomorrow, we ___ at home.", ["stay", "will stay", "would stay", "stayed"], 1),
    ("B1", "I have lived in Tashkent ___ 2015.", ["for", "since", "from", "during"], 1),
    ("B1", "She asked me where ___.", ["was I going", "I am going", "I was going", "am I going"], 2),
    ("B2", "By the time we arrived, the film ___.", ["already started", "has already started", "was already starting", "had already started"], 3),
    ("B2", "He suggested ___ a taxi.", ["to take", "taking", "take", "took"], 1),
    ("B2", "I wish I ___ more time to study yesterday.", ["had", "have", "had had", "would have"], 2),
    ("C1", "Hardly ___ the house when it started to rain.", ["she had left", "she left", "did she leave", "had she left"], 3),
    ("C1", "Not only ___ the exam, but she also got the highest score.", ["she passed", "did she pass", "passed she", "she did pass"], 1),
    ("C1", "I would rather you ___ me the truth yesterday.", ["told", "tell", "had told", "would tell"], 2),
]

TOTAL = len(QUESTIONS)
LETTERS = "ABCD"

# Daraja -> kurs darajasi kodi (bot qidiruvidagi b / i / a)
COURSE_LEVEL = {"A1": "b", "A2": "b", "B1": "i", "B2": "i", "C1": "a"}


def compute_level(answers: list) -> tuple:
    """(daraja, to'g'ri javoblar soni, har daraja bo'yicha to'g'rilar) — darajani ketma-ket 2/3 qoidasi belgilaydi."""
    per = {lv: 0 for lv in LEVELS}
    score = 0
    for i, (lv, _q, _opts, correct) in enumerate(QUESTIONS):
        if i < len(answers) and answers[i] == correct:
            per[lv] += 1
            score += 1
    reached = "A1"
    for lv in LEVELS:
        if per[lv] >= 2:
            reached = lv
        else:
            break
    return reached, score, per


def question(i: int) -> Optional[tuple]:
    return QUESTIONS[i] if 0 <= i < TOTAL else None
