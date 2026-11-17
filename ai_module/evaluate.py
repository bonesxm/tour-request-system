import json
import csv
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score
from baseline import analyze_request


# Папка, в которой находится evaluate.py
BASE_DIR = Path(__file__).resolve().parent

DATASET = BASE_DIR / "evals" / "dataset.jsonl"
RESULTS = BASE_DIR / "evals" / "baseline_results.csv"

FIELDS = [
    "departure",
    "destination",
    "budget",
    "adults",
    "children",
    "priority"
]


def load_dataset():
    data = []

    with open(DATASET, "r", encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                data.append(json.loads(line))

    return data


def main():
    data = load_dataset()

    true_priority = []
    predicted_priority = []

    correct_fields = {field: 0 for field in FIELDS}
    fully_correct = 0
    results = []

    for item in data:
        prediction = analyze_request(item["text"])

        true_priority.append(item["priority"])
        predicted_priority.append(prediction["priority"])

        all_correct = True

        for field in FIELDS:
            if prediction.get(field) == item.get(field):
                correct_fields[field] += 1
            else:
                all_correct = False

        if all_correct:
            fully_correct += 1

        results.append({
            "id": item["id"],
            "text": item["text"],
            "expected": json.dumps(
                {field: item.get(field) for field in FIELDS},
                ensure_ascii=False
            ),
            "predicted": json.dumps(
                prediction,
                ensure_ascii=False
            ),
            "fully_correct": all_correct
        })

    total = len(data)

    if total == 0:
        print("Набор тестов пуст!")
        return

    print("\n=== BASELINE: БЕЗ ИИ ===")
    print("Количество заявок:", total)

    print("\nМетрики срочности:")
    print(
        "Accuracy:",
        round(accuracy_score(true_priority, predicted_priority), 3)
    )
    print(
        "Macro F1:",
        round(
            f1_score(
                true_priority,
                predicted_priority,
                labels=["Обычно", "Срочно"],
                average="macro",
                zero_division=0
            ),
            3
        )
    )

    print("\nТочность извлечения полей:")

    for field in FIELDS:
        accuracy = correct_fields[field] / total
        print(f"{field}: {accuracy:.3f}")

    print(
        "\nПолностью правильные заявки:",
        f"{fully_correct}/{total}"
    )

    with open(
        RESULTS, "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id", "text", "expected",
                "predicted", "fully_correct"
            ]
        )
        writer.writeheader()
        writer.writerows(results)

    print("\nРезультаты сохранены:", RESULTS)


if __name__ == "__main__":
    main()
