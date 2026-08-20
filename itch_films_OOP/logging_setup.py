"""
logging_setup.py
Настройка логирования: ошибки разных "направлений" пишутся в разные
файлы внутри logs/, а не все вперемешку в один файл или только в консоль.

    logs/database.log — MySQL (Sakila на чтение, личная write-база) и
                         MongoDB (статистика поисков)
    logs/network.log  — внешние API (OpenAI, Firecrawl)
    logs/app.log      — всё остальное: Flask-роуты общего назначения,
                         генерация постеров, работа с файлами на диске

Как это работает: Python logging строит логгеры по ИМЕНИ — два вызова
logging.getLogger("database") в разных файлах вернут ОДИН И ТОТ ЖЕ
объект-логгер. Поэтому модулям, которые логируют ошибки, достаточно
взять logging.getLogger("database") / ("network") / ("app") вместо
привычного logging.getLogger(__name__) — какой файл в logs/ получит
сообщение, решает выбор ИМЕНИ логгера, а не место в коде.

Вызывается один раз при старте — из create_app() (app/__init__.py).
"""

import logging
import os

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(_PROJECT_ROOT, "logs")

# %(filename)s:%(lineno)d — несмотря на общее имя логгера ("database"
# и т.д.), в самой строке лога всё равно видно, из какого именно файла
# и с какой строки она пришла.
_FORMAT = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d — %(message)s"

# Имя логгера (что берут другие модули через logging.getLogger(...)) →
# имя файла в logs/, куда он пишет.
_CATEGORIES = {
    "database": "database.log",
    "network":  "network.log",
    "app":      "app.log",
}


def setup_logging(level: int = logging.WARNING) -> None:
    """
    Создаёt logs/ (если его ещё нет) и вешает на каждый из трёх
    именованных логгеров свой FileHandler.

    Безопасно вызывать несколько раз (например, и из create_app(), и
    из тестов) — если у логгера уже есть обработчики, повторно их не
    добавляем, иначе одно и то же сообщение писалось бы в файл N раз.

    propagate НЕ трогаем (остаётся True по умолчанию) — сообщения всё
    равно продолжают доходить до root-логгера и попадать в консоль (как
    было раньше), просто ДОПОЛНИТЕЛЬНО сохраняются в файл. Ничего из
    старого поведения не убираем, только добавляем.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)

    for name, filename in _CATEGORIES.items():
        logger = logging.getLogger(name)
        if logger.handlers:
            continue
        logger.setLevel(level)
        handler = logging.FileHandler(os.path.join(LOGS_DIR, filename), encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
