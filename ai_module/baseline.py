
import re


def analyze_request(text):
    text = text.lower()

    # 1. Определяем срочность
    urgent_words = [
        "срочно", "немедленно", "сегодня",
        "завтра", "через час", "вылет через",
        "urgent", "asap", "шұғыл", "ертең"
    ]

    priority = "Срочно" if any(
        word in text for word in urgent_words
    ) else "Обычно"

    # 2. Определяем город отправления
    departure = None

    cities = {
        "Астана": ["астана", "астаны", "астане"],
        "Алматы": ["алматы"],
        "Шымкент": ["шымкент", "шымкента"]
    }

    for city, variants in cities.items():
        if any(variant in text for variant in variants):
            departure = city
            break

    # 3. Определяем направление
    destination = None

    destinations = [
        "дубай", "анталья", "стамбул",
        "париж", "сеул"
    ]

    for city in destinations:
        if city in text:
            destination = city.title()
            break

    # 4. Определяем бюджет
    budget = None

    match = re.search(
        r"(?:бюджет|до)\s*(\d[\d\s]*)\s*(тысяч|тыс|₸|тенге)?",
        text
    )

    if match:
        budget = int(match.group(1).replace(" ", ""))

        if match.group(2) in ("тысяч", "тыс"):
            budget *= 1000

    # 5. Определяем количество взрослых
    adults = None

    adult_match = re.search(
        r"(\d+)\s*(?:взрослых|взрослый|взрослые)",
        text
    )

    if adult_match:
        adults = int(adult_match.group(1))

    # 6. Определяем количество детей
    children = None

    child_match = re.search(
        r"(\d+)\s*(?:ребенок|ребенка|детей|ребёнок|ребёнка)",
        text
    )

    if child_match:
        children = int(child_match.group(1))

    # Возвращаем заполненную заявку
    return {
        "departure": departure,
        "destination": destination,
        "budget": budget,
        "adults": adults,
        "children": children,
        "priority": priority
    }


# Проверяем работу программы
if __name__ == "__main__":
    message = (
        "Срочно! Завтра хотим вылететь из Астаны "
        "в Дубай, 2 взрослых и 1 ребёнок, "
        "бюджет 800 тысяч тенге"
    )

    result = analyze_request(message)

    print("Результат анализа заявки:")
    print(result)
