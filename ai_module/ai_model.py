
import json
import urllib.request
import time


def analyze_with_ai(text):
    prompt = f"""
Ты анализируешь туристические заявки.
Извлеки данные из сообщения клиента.

Верни ТОЛЬКО JSON со следующими полями:
departure, destination, budget, adults, children, priority.

Правила:
- departure и destination — названия городов на русском.
- budget — число в тенге.
- adults и children — целые числа.
- priority — строго "Срочно" или "Обычно".
- Если информация отсутствует, используй null.
- Не придумывай отсутствующие данные.
- Никаких пояснений, только JSON.

Сообщение клиента:
{text}
"""

    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False,
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

    # Начало измерения времени
    start_time = time.perf_counter()

    # Отправляем заявку в Ollama
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

    # Время обработки заявки
    elapsed = time.perf_counter() - start_time
    print(f"\nВремя обработки заявки: {elapsed:.2f} сек.")

    # Получаем ответ ИИ
    raw_answer = result["response"]

    # Подсчитываем токены
    input_tokens = result.get("prompt_eval_count", 0)
    output_tokens = result.get("eval_count", 0)

    print("\n=== СТАТИСТИКА ТОКЕНОВ ===")
    print("Входные токены:", input_tokens)
    print("Выходные токены:", output_tokens)
    print("Всего токенов:", input_tokens + output_tokens)

    return json.loads(raw_answer)


if __name__ == "__main__":
    message = (
        "Срочно! Завтра хотим вылететь из Астаны в Дубай, "
        "2 взрослых и 1 ребёнок, бюджет 800 тысяч тенге"
    )

    result = analyze_with_ai(message)

    print("\nРезультат ИИ:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
