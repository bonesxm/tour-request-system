
import csv
import json
from pathlib import Path
from sklearn.metrics import accuracy_score, f1_score

BASE = Path(__file__).resolve().parent / "evals"

FIELDS = [
    "departure", "destination", "budget",
    "adults", "children", "priority"
]

with open(BASE / "dataset.jsonl", encoding="utf-8-sig") as f:
    dataset = {
        str(item["id"]): item
        for line in f if line.strip()
        for item in [json.loads(line)]
    }

for name, filename in [
    ("ZERO-SHOT", "ai_zero_shot_results.csv"),
    ("FEW-SHOT", "ai_few_shot_results.csv")
]:
    with open(BASE / filename, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print("\n===", name, "===")
    print("Количество заявок:", len(rows))

    for field in FIELDS:
        correct = 0

        for row in rows:
            expected = dataset[str(row["id"])].get(field)
            predicted = row[f"predicted_{field}"]

            # В CSV пустая ячейка означает null.
            if predicted == "":
                predicted = None
            elif field in ("budget", "adults", "children"):
                try:
                    predicted = int(predicted)
                except (ValueError, TypeError):
                    pass

            if expected == predicted:
                correct += 1

        print(f"{field}: {correct / len(rows):.3f}")

    expected_priority = [
        dataset[str(row["id"])]["priority"]
        for row in rows
    ]
    predicted_priority = [
        row["predicted_priority"] or "Нет ответа"
        for row in rows
    ]

    print("Priority Accuracy:", round(
        accuracy_score(expected_priority, predicted_priority), 3
    ))

    print("Priority Macro F1:", round(
        f1_score(
            expected_priority,
            predicted_priority,
            labels=["Срочно", "Обычно"],
            average="macro",
            zero_division=0
        ), 3
    ))

    fully_correct = 0

    for row in rows:
        item = dataset[str(row["id"])]
        all_correct = True

        for field in FIELDS:
            predicted = row[f"predicted_{field}"]

            if predicted == "":
                predicted = None
            elif field in ("budget", "adults", "children"):
                try:
                    predicted = int(predicted)
                except (ValueError, TypeError):
                    pass

            if item.get(field) != predicted:
                all_correct = False

        if all_correct:
            fully_correct += 1

    print("Полностью правильные заявки:",
          f"{fully_correct}/{len(rows)}")
