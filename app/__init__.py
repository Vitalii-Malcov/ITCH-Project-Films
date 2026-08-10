from flask import Flask
from dotenv import load_dotenv


def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Register blueprints (import here to avoid circular imports)
    from app.routes import firecrawl_bp
    app.register_blueprint(firecrawl_bp)

    return app