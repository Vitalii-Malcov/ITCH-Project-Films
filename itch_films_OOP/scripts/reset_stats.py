"""
scripts/reset_stats.py
──────────────────────────────────────────────────────────────────────
Консольная очистка статистики поисков (MongoDB, коллекция search_logs).

Раньше это была кнопка на странице /stats — убрали её оттуда: разрушительное
действие ("удалить всё без возможности восстановления") не должно быть
доступно любому посетителю сайта в один клик. Теперь это делает только
тот, у кого есть доступ к консоли сервера.

Использование (запуск из корня проекта itch_films_OOP/):
    python scripts/reset_stats.py            # спросит подтверждение
    python scripts/reset_stats.py --yes      # без вопроса (для автоматизации)
"""

import argparse
import os
import sys

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252,
# в неё не помещаются русские буквы из print() ниже).
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Настройка путей ──────────────────────────────────────────────────
# scripts/reset_stats.py живёт внутри itch_films_OOP/, поэтому корень
# проекта — на один уровень выше (нужен для local_settings.py и app/).
_script_dir: str = os.path.dirname(os.path.abspath(__file__))
_itch_films: str = os.path.dirname(_script_dir)
if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))

import local_settings
from app.services import MongoConnection, SearchLogger, SearchStatsRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удаляет всю статистику поисков из MongoDB (коллекция search_logs)."
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Не спрашивать подтверждение (для автоматизации/CI).",
    )
    args = parser.parse_args()

    connection = MongoConnection(
        local_settings.MONGO_URI, local_settings.MONGO_DATABASE,
        local_settings.MONGO_COLLECTION, label="MongoDB",
    )
    if not connection.is_connected:
        print("Нет подключения к MongoDB — нечего удалять.")
        return

    total = SearchStatsRepository(connection).get_total_searches()
    if total == 0:
        print("Статистика уже пуста.")
        return

    print(f"Записей в search_logs: {total}")

    if not args.yes:
        answer = input(
            "Удалить всю статистику без возможности восстановления? [y/N]: "
        ).strip().lower()
        if answer != "y":
            print("Отменено.")
            return

    deleted = SearchLogger(connection).delete_all()
    print(f"Удалено записей: {deleted}")


if __name__ == "__main__":
    main()