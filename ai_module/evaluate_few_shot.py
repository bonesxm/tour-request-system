import csv
import json
from pathlib import Path
from sklearn.metrics import accuracy_score, f1_score

from ai_few_shot import analyze_few_shot


BASE_DIR = Path(__file__).resolve().parent
DATASET = BASE_DIR / "evals" / "dataset.jsonl"
RESULTS = BASE_DIR / "evals" / "ai_few_shot_results.csv"
RAW_RESULTS = BASE_DIR / "evals" / "ai_few_shot_raw.jsonl"

FIELDS = [
    "departure", "destination", "budget",
    "adults", "children", "priority"
]


def main():
    with open(DATASET, "r", encoding="utf-8-sig") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    results = []
    raw_results = []

    print("=== FEW-SHOT ТЕСТИРОВАНИЕ ===")
    print("Количество заявок:", len(dataset))

    for i, item in enumerate(dataset, start=1):
        print(f"Обрабатываем заявку {i}/{len(dataset)}...")

        try:
            prediction = analyze_few_shot(item["text"])
            error = None
        except Exception as exc:
            prediction = {}
            error = str(exc)
            print("Ошибка:", error)

        row = {
            "id": item["id"],
            "text": item["text"],
            "error": error or ""
        }

        for field in FIELDS:
            row[f"expected_{field}"] = item.get(field)
            row[f"predicted_{field}"] = prediction.get(field)

        results.append(row)

        raw_results.append({
            "id": item["id"],
            "text": item["text"],
            "prediction": prediction,
            "error": error
        })

    with open(RESULTS, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    with open(RAW_RESULTS, "w", encoding="utf-8") as f:
        for item in raw_results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print("\n=== РЕЗУЛЬТАТЫ FEW-SHOT ===")

    for field in FIELDS:
        correct = sum(
            row[f"expected_{field}"] == row[f"predicted_{field}"]
            for row in results
        )
        print(f"{field}: {correct / len(results):.3f}")

    expected_priority = [
        str(row["expected_priority"]) for row in results
    ]
    predicted_priority = [
        str(row["predicted_priority"]) for row in results
    ]

    print(
        "Priority Accuracy:",
        round(accuracy_score(expected_priority, predicted_priority), 3)
    )
    print(
        "Priority Macro F1:",
        round(f1_score(
            expected_priority,
            predicted_priority,
            labels=["Срочно", "Обычно"],
            average="macro",
            zero_division=0
        ), 3)
    )

    fully_correct = sum(
        all(
            row[f"expected_{field}"] == row[f"predicted_{field}"]
            for field in FIELDS
        )
        for row in results
    )

    print(
        "Полностью правильные заявки:",
        f"{fully_correct}/{len(results)}"
    )

    print("\nРезультаты сохранены в папке evals.")


if __name__ == "__main__":
    main()
