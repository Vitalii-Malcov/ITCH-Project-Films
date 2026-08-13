from flask import Flask
from dotenv import load_dotenv


def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Регистрируем blueprint'ы (импорт внутри функции — избегаем циклических импортов)
    from firecrawl_app.routes import firecrawl_bp
    app.register_blueprint(firecrawl_bp)

    return app