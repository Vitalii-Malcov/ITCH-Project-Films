import os

from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise RuntimeError(
        "Переменная окружения FIRECRAWL_API_KEY не задана"
    )

app = FirecrawlApp(api_key=api_key)

result = app.scrape_url("https://www.xing.com/jobs/frankfurt-main-junior-frontend-developer-commerce-shopify-155782256")

print(result.markdown)
