# ─────────────────────────────────────────────
# tests/test_itch_films.py
# Playwright-тесты для ITCH Films.
#
# Покрывают все ключевые сценарии из ТЗ:
#   1. Поиск по названию + автодополнение
#   2. Поиск по жанру
#   3. Поиск по жанру + диапазон годов
#   4. Пагинация «следующие / предыдущие 10»
#   5. Страница статистики MongoDB
# ─────────────────────────────────────────────

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"


# ── 1. Главная страница ────────────────────────────────────────────

class TestHomepage:
    def test_загрузка_главной(self, page: Page):
        """Страница открывается, заголовок и поле поиска видны."""
        page.goto(BASE_URL)

        # Заголовок вкладки браузера
        expect(page).to_have_title("ITCH Films — Поиск фильмов")

        # Главный заголовок на странице
        expect(page.locator("h1.search-title")).to_be_visible()
        expect(page.locator("h1.search-title")).to_contain_text("Найди свой фильм")

        # Поле поиска
        expect(page.locator("#search-input")).to_be_visible()

    def test_жанровые_фильтры_видны(self, page: Page):
        """На главной отображаются кнопки жанров из MySQL."""
        page.goto(BASE_URL)

        # Хотя бы один жанр должен присутствовать
        genre_pills = page.locator("a.genre-pill")
        assert genre_pills.count() > 0, "Жанровые фильтры не найдены"

        # Жанры Action и Comedy должны быть в Sakila
        expect(page.locator("a.genre-pill:has-text('Action')")).to_be_visible()
        expect(page.locator("a.genre-pill:has-text('Comedy')")).to_be_visible()

    def test_форма_жанр_год_видна(self, page: Page):
        """Форма поиска по жанру + годам присутствует на главной."""
        page.goto(BASE_URL)
        expect(page.locator("select[name='genre']")).to_be_visible()
        expect(page.locator("input[name='year_from']")).to_be_visible()
        expect(page.locator("input[name='year_to']")).to_be_visible()


# ── 2. Автодополнение ──────────────────────────────────────────────

class TestAutocomplete:
    def test_dropdown_появляется(self, page: Page):
        """Dropdown появляется при вводе от 2 символов."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ac")

        # Ждём появления dropdown (до 3 секунд — запрос к MySQL)
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        items = page.locator(".autocomplete-item")
        assert items.count() > 0, "Dropdown пустой — /api/suggest не вернул результаты"

    def test_dropdown_показывает_жанр_и_год(self, page: Page):
        """Каждый элемент dropdown содержит название + метаданные."""
        page.goto(BASE_URL)
        page.fill("#search-input", "love")
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        # Первый элемент должен иметь ac-title
        first_title = page.locator(".ac-title").first
        expect(first_title).to_be_visible()

        # Метаданные (жанр и год)
        first_meta = page.locator(".ac-meta").first
        expect(first_meta).to_be_visible()

    def test_клик_по_подсказке_запускает_поиск(self, page: Page):
        """Клик по элементу dropdown подставляет название и ищет."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        # Кликаем первый элемент
        page.locator(".autocomplete-item").first.click()

        # Должны появиться карточки фильмов
        page.wait_for_selector(".film-card", timeout=5000)
        expect(page.locator(".film-card").first).to_be_visible()

    def test_dropdown_закрывается_на_escape(self, page: Page):
        """Нажатие Escape закрывает dropdown."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ac")
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        page.keyboard.press("Escape")

        # Dropdown должен исчезнуть
        expect(page.locator(".autocomplete-dropdown")).not_to_have_class("show")


# ── 3. Поиск по названию ──────────────────────────────────────────

class TestSearchByTitle:
    def test_поиск_возвращает_карточки(self, page: Page):
        """Поиск по 'ace' возвращает карточки фильмов из MySQL."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.click("button.search-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        cards = page.locator(".film-card")
        count = cards.count()
        assert count > 0, f"Нет результатов для запроса 'ace', получено: {count}"

    def test_заголовок_результатов(self, page: Page):
        """Строка с описанием результатов отображается корректно."""
        page.goto(f"{BASE_URL}/search?q=love")
        page.wait_for_selector(".results-count")
        results_text = page.locator(".results-count").inner_text()
        assert "love" in results_text.lower(), "Запрос не указан в строке результатов"
        assert "найдено" in results_text.lower()

    def test_пустой_результат(self, page: Page):
        """Несуществующий запрос показывает блок 'Ничего не найдено'."""
        page.goto(f"{BASE_URL}/search?q=xyzxyzxyz_no_match")
        page.wait_for_selector(".no-results", timeout=5000)
        expect(page.locator(".no-results")).to_be_visible()
        expect(page.locator(".no-results")).to_contain_text("Ничего не найдено")


# ── 4. Поиск по жанру ─────────────────────────────────────────────

class TestSearchByGenre:
    def test_клик_по_жанру_показывает_фильмы(self, page: Page):
        """Клик по жанру 'Action' возвращает список фильмов."""
        page.goto(BASE_URL)
        page.click("a.genre-pill:has-text('Action')")
        page.wait_for_selector(".film-card", timeout=5000)

        # В строке результатов должен быть жанр
        expect(page.locator(".results-count")).to_contain_text("Action")

        # Карточки фильмов присутствуют
        assert page.locator(".film-card").count() > 0

    def test_форма_жанр_плюс_год(self, page: Page):
        """Форма с жанром и годами возвращает результаты."""
        page.goto(BASE_URL)

        # Выбираем жанр в dropdown
        page.select_option("select[name='genre']", "Comedy")

        # Вводим диапазон годов
        page.fill("input[name='year_from']", "1990")
        page.fill("input[name='year_to']", "2030")

        # Нажимаем кнопку-фильтр
        page.click("button.gy-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        expect(page.locator(".results-count")).to_contain_text("Comedy")
        assert page.locator(".film-card").count() > 0


# ── 5. Пагинация ──────────────────────────────────────────────────

class TestPagination:
    def test_кнопка_следующие_10(self, page: Page):
        """Поиск по 'the' показывает кнопку «Следующие 10»."""
        page.goto(f"{BASE_URL}/search?q=the")
        page.wait_for_selector(".film-card", timeout=5000)

        next_btn = page.locator("a.pagination-btn:has-text('Следующие 10')")
        expect(next_btn).to_be_visible()

    def test_переход_на_следующую_страницу(self, page: Page):
        """Клик «Следующие 10» загружает вторую страницу результатов."""
        page.goto(f"{BASE_URL}/search?q=the")
        page.wait_for_selector(".film-card", timeout=5000)

        # Первые 10 фильмов
        first_title = page.locator(".film-title").first.inner_text()

        # Кликаем «Следующие 10»
        page.click("a.pagination-btn:has-text('Следующие 10')")
        page.wait_for_selector(".film-card", timeout=5000)

        # На второй странице другие фильмы
        second_title = page.locator(".film-title").first.inner_text()
        assert first_title != second_title, "Вторая страница показывает те же фильмы"

        # Кнопка «Предыдущие 10» появилась
        expect(page.locator("a.pagination-btn:has-text('Предыдущие 10')")).to_be_visible()

    def test_возврат_на_первую_страницу(self, page: Page):
        """«Предыдущие 10» возвращает на первую страницу."""
        # Начинаем сразу со второй страницы
        page.goto(f"{BASE_URL}/search?q=the&offset=10")
        page.wait_for_selector(".film-card", timeout=5000)

        page.click("a.pagination-btn:has-text('Предыдущие 10')")
        page.wait_for_selector(".film-card", timeout=5000)

        # На первой странице нет «Предыдущих»
        expect(
            page.locator("a.pagination-btn:has-text('Предыдущие 10')")
        ).not_to_be_visible()


# ── 6. Страница статистики MongoDB ────────────────────────────────

class TestStatsPage:
    def test_страница_статистики_открывается(self, page: Page):
        """/stats открывается, заголовок MongoDB Analytics виден."""
        page.goto(f"{BASE_URL}/stats")
        expect(page).to_have_title("ITCH Films — Статистика")
        expect(page.locator("h1")).to_contain_text("MongoDB Analytics")

    def test_счётчик_поисков_больше_нуля(self, page: Page):
        """Карточка 'Всего поисков' показывает число > 0."""
        page.goto(f"{BASE_URL}/stats")

        # Первая stat-value — «Всего поисков»
        total_text = page.locator(".stat-value").first.inner_text().strip()
        assert total_text.isdigit(), f"Ожидалось число, получено: '{total_text}'"
        assert int(total_text) > 0, "Счётчик поисков равен 0 — MongoDB не пишет логи"

    def test_популярные_запросы_отображаются(self, page: Page):
        """Блок «Топ-5 популярных запросов» содержит элементы."""
        page.goto(f"{BASE_URL}/stats")

        popular_items = page.locator(".popular-item")
        assert popular_items.count() > 0, "Популярные запросы не отображаются"

    def test_последние_запросы_отображаются(self, page: Page):
        """Блок «Последние 5 запросов» содержит элементы."""
        page.goto(f"{BASE_URL}/stats")

        recent_items = page.locator(".recent-item")
        assert recent_items.count() > 0, "Последние запросы не отображаются"

    def test_карточка_всего_поисков_кликабельна(self, page: Page):
        """Карточка 'Всего поисков' — это ссылка на /stats/searches."""
        page.goto(f"{BASE_URL}/stats")

        link = page.locator("a.stat-card-link[href*='stats/searches']")
        expect(link).to_be_visible()

        # Проверяем что содержит число и подпись
        expect(link).to_contain_text("Всего поисков")

    def test_карточка_уникальных_кликабельна(self, page: Page):
        """Карточка 'Уникальных запросов' — это ссылка на /stats/unique."""
        page.goto(f"{BASE_URL}/stats")

        link = page.locator("a.stat-card-link[href*='stats/unique']")
        expect(link).to_be_visible()
        expect(link).to_contain_text("Уникальных запросов")


# ── 7. Детальный список: все поиски ───────────────────────────────

class TestStatsSearches:
    def test_страница_открывается(self, page: Page):
        """/stats/searches загружается с таблицей записей."""
        page.goto(f"{BASE_URL}/stats/searches")
        expect(page).to_have_title("ITCH Films — Все поиски")
        expect(page.locator("h1")).to_contain_text("Все поиски")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_таблица_содержит_строки(self, page: Page):
        """В таблице есть хотя бы одна запись из MongoDB."""
        page.goto(f"{BASE_URL}/stats/searches")
        rows = page.locator(".stats-table tbody tr")
        assert rows.count() > 0, "Таблица пустая — MongoDB не возвращает данные"

    def test_бейджи_типов_поиска(self, page: Page):
        """Строки содержат бейджи 🔎 Search или 🎭 Genre."""
        page.goto(f"{BASE_URL}/stats/searches")
        badges = page.locator(".recent-type-badge")
        assert badges.count() > 0, "Бейджи типов поиска не найдены"

    def test_счётчик_записей_в_шапке(self, page: Page):
        """Бейдж в шапке показывает общее число записей."""
        page.goto(f"{BASE_URL}/stats/searches")
        badge_text = page.locator(".stats-db-badge").inner_text()
        assert "записей" in badge_text, f"Счётчик не найден: '{badge_text}'"
        # Извлекаем число и проверяем что оно > 0
        number = badge_text.split()[0]
        assert number.isdigit() and int(number) > 0

    def test_ссылка_назад_ведёт_на_stats(self, page: Page):
        """Кнопка «← Статистика» возвращает на /stats."""
        page.goto(f"{BASE_URL}/stats/searches")
        page.click("a.stats-back-link")
        expect(page).to_have_url(f"{BASE_URL}/stats")
        expect(page.locator("h1")).to_contain_text("MongoDB Analytics")

    def test_клик_по_карточке_открывает_список(self, page: Page):
        """Клик по карточке 'Всего поисков' на /stats ведёт сюда."""
        page.goto(f"{BASE_URL}/stats")
        page.click("a.stat-card-link[href*='stats/searches']")
        expect(page).to_have_url(f"{BASE_URL}/stats/searches")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_пагинация_следующие_10(self, page: Page):
        """Если записей > 10 — кнопка «Следующие 10» видна."""
        page.goto(f"{BASE_URL}/stats/searches")
        total_text = page.locator(".stats-db-badge").inner_text().split()[0]
        total = int(total_text) if total_text.isdigit() else 0

        if total > 10:
            expect(
                page.locator("a.pagination-btn:has-text('Следующие 10')")
            ).to_be_visible()
        else:
            # Пагинация не нужна — кнопки нет
            expect(
                page.locator("a.pagination-btn:has-text('Следующие 10')")
            ).not_to_be_visible()

    def test_переход_на_вторую_страницу(self, page: Page):
        """offset=10 загружает вторую страницу и показывает «Предыдущие 10»."""
        page.goto(f"{BASE_URL}/stats/searches?offset=10")
        expect(page.locator(".stats-table")).to_be_visible()
        expect(
            page.locator("a.pagination-btn:has-text('Предыдущие 10')")
        ).to_be_visible()


# ── 8. Детальный список: уникальные запросы ───────────────────────

class TestStatsUnique:
    def test_страница_открывается(self, page: Page):
        """/stats/unique загружается с таблицей уникальных запросов."""
        page.goto(f"{BASE_URL}/stats/unique")
        expect(page).to_have_title("ITCH Films — Уникальные запросы")
        expect(page.locator("h1")).to_contain_text("Уникальные запросы")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_таблица_содержит_строки(self, page: Page):
        """Таблица уникальных запросов не пустая."""
        page.goto(f"{BASE_URL}/stats/unique")
        rows = page.locator(".stats-table tbody tr")
        assert rows.count() > 0, "Таблица пустая"

    def test_колонка_раз_искали(self, page: Page):
        """Колонка с × count присутствует в строках."""
        page.goto(f"{BASE_URL}/stats/unique")
        counts = page.locator(".popular-count")
        assert counts.count() > 0, "Колонка 'Раз искали' не найдена"
        # Проверяем формат первого значения: «× N»
        first = counts.first.inner_text().strip()
        assert first.startswith("×"), f"Неожиданный формат: '{first}'"

    def test_отсортировано_по_частоте(self, page: Page):
        """Первый запрос встречается не реже второго (sort count DESC)."""
        page.goto(f"{BASE_URL}/stats/unique")
        counts = page.locator(".popular-count")
        if counts.count() < 2:
            return  # нечего сравнивать

        first_n  = int(counts.nth(0).inner_text().replace("×", "").strip())
        second_n = int(counts.nth(1).inner_text().replace("×", "").strip())
        assert first_n >= second_n, (
            f"Неверная сортировка: первый={first_n}, второй={second_n}"
        )

    def test_клик_по_карточке_открывает_список(self, page: Page):
        """Клик по карточке 'Уникальных запросов' на /stats ведёт сюда."""
        page.goto(f"{BASE_URL}/stats")
        page.click("a.stat-card-link[href*='stats/unique']")
        expect(page).to_have_url(f"{BASE_URL}/stats/unique")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_ссылка_назад(self, page: Page):
        """Кнопка «← Статистика» возвращает на /stats."""
        page.goto(f"{BASE_URL}/stats/unique")
        page.click("a.stats-back-link")
        expect(page).to_have_url(f"{BASE_URL}/stats")
