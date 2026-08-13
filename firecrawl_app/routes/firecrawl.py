from dataclasses import asdict

from flask import Blueprint, request, jsonify

from services.firecrawl import (
    FirecrawlClient,
    FirecrawlConfigurationError,
    FirecrawlConnectionError,
    FirecrawlError,
    FirecrawlRateLimitError,
    FirecrawlValidationError,
)
from services.mongo import MongoService

firecrawl_bp = Blueprint("firecrawl", __name__, url_prefix="/api")

# MongoService не требует внешних credentials на момент импорта
mongo = MongoService()

ALLOWED_COLLECTIONS = {"scrapes", "searches", "crawls"}


def get_firecrawl_client() -> FirecrawlClient:
    return FirecrawlClient()


@firecrawl_bp.route("/scrape", methods=["POST"])
def scrape():
    """POST /api/scrape  — тело запроса: {"url": "..."}"""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing required field: url"}), 400

    try:
        result = get_firecrawl_client().scrape(data["url"])
        doc_id = mongo.save_scrape(result)
        response = asdict(result)
        response["_id"] = doc_id
        return jsonify(response)
    except FirecrawlConfigurationError:
        return jsonify({"error": "Firecrawl service is not configured"}), 503
    except FirecrawlValidationError as e:
        return jsonify({"error": str(e)}), 400
    except FirecrawlRateLimitError as e:
        return jsonify({"error": str(e)}), 429
    except FirecrawlConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except FirecrawlError as e:
        return jsonify({"error": str(e)}), 500


@firecrawl_bp.route("/crawl", methods=["POST"])
def crawl():
    """POST /api/crawl  — тело запроса: {"url": "...", "limit": 10}"""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing required field: url"}), 400

    limit = data.get("limit", 10)

    try:
        result = get_firecrawl_client().crawl(data["url"], limit=limit)
        doc_id = mongo.save_crawl(result)
        response = result.to_dict()
        response["_id"] = doc_id
        return jsonify(response)
    except FirecrawlConfigurationError:
        return jsonify({"error": "Firecrawl service is not configured"}), 503
    except FirecrawlValidationError as e:
        return jsonify({"error": str(e)}), 400
    except FirecrawlRateLimitError as e:
        return jsonify({"error": str(e)}), 429
    except FirecrawlConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except FirecrawlError as e:
        return jsonify({"error": str(e)}), 500


@firecrawl_bp.route("/search", methods=["POST"])
def search():
    """POST /api/search  — тело запроса: {"query": "...", "limit": 5}"""
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing required field: query"}), 400

    limit = data.get("limit", 5)

    try:
        result = get_firecrawl_client().search(data["query"], limit=limit)
        doc_id = mongo.save_search(result)
        response = result.to_dict()
        response["_id"] = doc_id
        return jsonify(response)
    except FirecrawlConfigurationError:
        return jsonify({"error": "Firecrawl service is not configured"}), 503
    except FirecrawlValidationError as e:
        return jsonify({"error": str(e)}), 400
    except FirecrawlRateLimitError as e:
        return jsonify({"error": str(e)}), 429
    except FirecrawlConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except FirecrawlError as e:
        return jsonify({"error": str(e)}), 500


# Endpoint зарезервирован для будущей реализации structured extraction.
# FirecrawlClient.extract() не реализован — сигнатура SDK не подтверждена.
@firecrawl_bp.route("/extract", methods=["POST"])
def extract():
    """POST /api/extract — не реализован."""
    return jsonify({"error": "Firecrawl extract is not implemented yet"}), 501


@firecrawl_bp.route("/history/<collection>", methods=["GET"])
def history(collection):
    """GET /api/history/<collection>?limit=10 — последние результаты из MongoDB."""
    if collection not in ALLOWED_COLLECTIONS:
        return jsonify({"error": f"Unknown collection '{collection}'. Use: scrapes, searches, crawls"}), 400

    limit = request.args.get("limit", 10, type=int)
    docs = mongo.get_recent(collection, limit=limit)
    return jsonify({"collection": collection, "count": len(docs), "results": docs})