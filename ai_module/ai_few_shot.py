import json
import urllib.request


def analyze_few_shot(text):
    prompt = """
Ты анализируешь туристические заявки.
Верни только JSON с полями:
departure, destination, budget, adults, children, priority.

Правила:
- Названия городов пиши на русском языке.
- Бюджет указывай числом в тенге.
- priority: только "Срочно" или "Обычно".
- Если поле не указано, используй null.
- Не придумывай отсутствующие данные.
- Никаких пояснений и Markdown.

Пример 1
Заявка: Срочно из Астаны в Дубай, 2 взрослых,
1 ребёнок, бюджет 800 тысяч тенге.
Ответ:
{"departure":"Астана","destination":"Дубай",
"budget":800000,"adults":2,"children":1,
"priority":"Срочно"}

Пример 2
Заявка: Хотим из Алматы в Париж, 3 взрослых,
бюджет 1500000 тенге.
Ответ:
{"departure":"Алматы","destination":"Париж",
"budget":1500000,"adults":3,"children":null,
"priority":"Обычно"}

Пример 3
Заявка: Шұғыл! Астанадан Стамбулға,
2 ересек, бюджет 600 мың теңге.
Ответ:
{"departure":"Астана","destination":"Стамбул",
"budget":600000,"adults":2,"children":null,
"priority":"Срочно"}

Теперь обработай новую заявку.

Заявка:
""" + text + "\nОтвет:"

    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "seed": 42
        }
    }

    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

    return json.loads(result["response"])


if __name__ == "__main__":
    message = (
        "Срочно! Из Астаны в Сеул, "
        "2 взрослых, бюджет 900 тысяч тенге"
    )

    result = analyze_few_shot(message)
    print("Результат Few-shot:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
