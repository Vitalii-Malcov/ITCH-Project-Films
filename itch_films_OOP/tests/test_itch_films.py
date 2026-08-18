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
    def test_homepage_loads(self, page: Page):
        """Страница открывается, заголовок и поле поиска видны."""
        page.goto(BASE_URL)

        # Заголовок вкладки браузера
        expect(page).to_have_title("ITCH Films — Поиск фильмов")

        # Главный заголовок на странице
        expect(page.locator("h1.search-title")).to_be_visible()
        expect(page.locator("h1.search-title")).to_contain_text("Найди свой фильм")

        # Поле поиска
        expect(page.locator("#search-input")).to_be_visible()

    def test_genre_filters_visible(self, page: Page):
        """На главной отображаются кнопки жанров из MySQL."""
        page.goto(BASE_URL)

        # Хотя бы один жанр должен присутствовать
        genre_pills = page.locator("a.genre-pill")
        assert genre_pills.count() > 0, "Жанровые фильтры не найдены"

        # Жанры Action и Comedy должны быть в Sakila
        expect(page.locator("a.genre-pill:has-text('Action')")).to_be_visible()
        expect(page.locator("a.genre-pill:has-text('Comedy')")).to_be_visible()

    def test_genre_year_form_visible(self, page: Page):
        """Форма поиска по жанру + годам присутствует на главной."""
        page.goto(BASE_URL)
        expect(page.locator("select[name='genre']")).to_be_visible()
        expect(page.locator("input[name='year_from']")).to_be_visible()
        expect(page.locator("input[name='year_to']")).to_be_visible()


# ── 2. Автодополнение ──────────────────────────────────────────────

class TestAutocomplete:
    def test_dropdown_appears(self, page: Page):
        """Dropdown появляется при вводе от 2 символов."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ac")

        # Ждём появления dropdown (до 3 секунд — запрос к MySQL)
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        items = page.locator(".autocomplete-item")
        assert items.count() > 0, "Dropdown пустой — /api/suggest не вернул результаты"

    def test_dropdown_shows_genre_and_year(self, page: Page):
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

    def test_click_suggestion_triggers_search(self, page: Page):
        """Клик по элементу dropdown подставляет название и ищет."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        # Кликаем первый элемент
        page.locator(".autocomplete-item").first.click()

        # Должны появиться карточки фильмов
        page.wait_for_selector(".film-card", timeout=5000)
        expect(page.locator(".film-card").first).to_be_visible()

    def test_dropdown_closes_on_escape(self, page: Page):
        """Нажатие Escape закрывает dropdown."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ac")
        page.wait_for_selector(".autocomplete-dropdown.show", timeout=3000)

        page.keyboard.press("Escape")

        # Dropdown должен исчезнуть
        expect(page.locator(".autocomplete-dropdown")).not_to_have_class("show")


# ── 3. Поиск по названию ──────────────────────────────────────────

class TestSearchByTitle:
    def test_search_returns_film_cards(self, page: Page):
        """Поиск по 'ace' возвращает карточки фильмов из MySQL."""
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.click("button.search-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        cards = page.locator(".film-card")
        count = cards.count()
        assert count > 0, f"Нет результатов для запроса 'ace', получено: {count}"

    def test_results_header_text(self, page: Page):
        """Строка с описанием результатов отображается корректно."""
        page.goto(f"{BASE_URL}/search?q=love")
        page.wait_for_selector(".results-count")
        results_text = page.locator(".results-count").inner_text()
        assert "love" in results_text.lower(), "Запрос не указан в строке результатов"
        assert "найдено" in results_text.lower()

    def test_empty_search_result(self, page: Page):
        """Несуществующий запрос показывает блок 'Ничего не найдено'."""
        page.goto(f"{BASE_URL}/search?q=xyzxyzxyz_no_match")
        page.wait_for_selector(".no-results", timeout=5000)
        expect(page.locator(".no-results")).to_be_visible()
        expect(page.locator(".no-results")).to_contain_text("Ничего не найдено")


class TestFilmNewsModalBackButton:
    """
    Регрессия: кнопка "Подробнее" открывает модалку поверх /search?...
    (без смены URL). Раньше "назад" в браузере не закрывал модалку, а сразу
    уводил со страницы результатов поиска на предыдущую запись в истории
    (главная) — см. history.pushState/popstate в index.html:loadFilmNews().
    """

    def test_back_closes_modal_without_leaving_search_page(self, page: Page):
        # Идём через главную и реальный поиск (а не page.goto(".../search?...")
        # напрямую) — иначе в истории браузера не будет записи "/" и проверка
        # "второе 'назад' ведёт на главную" будет бессмысленной.
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.click("button.search-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        page.click("button.btn-news >> nth=0")
        expect(page.locator("#newsModal")).to_be_visible()
        # Bootstrap игнорирует hide() (в т.ч. вызванный нашим popstate-
        # слушателем), пока ещё не завершилась CSS-анимация открытия
        # (Modal._isTransitioning) — ждём её конца (transition ~300ms).
        page.wait_for_timeout(350)

        page.go_back()
        expect(page.locator("#newsModal")).to_be_hidden()
        assert "/search" in page.url, (
            f"Первое нажатие 'назад' должно было только закрыть модалку "
            f"и остаться на странице результатов поиска, получили: {page.url}"
        )

        page.go_back()
        assert page.url.rstrip("/") == BASE_URL, (
            f"Второе нажатие 'назад' (модалка уже закрыта) должно вести "
            f"на главную страницу, получили: {page.url}"
        )

    def test_close_button_consumes_history_entry(self, page: Page):
        """
        Закрытие крестиком (не через 'назад') не должно оставлять в истории
        мёртвую запись — следующее 'назад' сразу ведёт на главную.
        """
        page.goto(BASE_URL)
        page.fill("#search-input", "ace")
        page.click("button.search-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        page.click("button.btn-news >> nth=0")
        expect(page.locator("#newsModal")).to_be_visible()
        page.wait_for_timeout(350)  # см. комментарий в тесте выше про _isTransitioning

        page.click("#newsModal .btn-close")
        expect(page.locator("#newsModal")).to_be_hidden()
        # to_be_hidden() видит display:none в тот же момент, когда Bootstrap
        # его выставляет — ДО того как успевает завершиться наш собственный
        # обработчик hidden.bs.modal (history.back() для "смыва" фиктивной
        # записи). Без паузы здесь page.go_back() ниже иногда улетает почти
        # одновременно с этим внутренним back() и браузер схлопывает два
        # шага "назад" в один. Ждём, пока внутренняя навигация точно
        # завершится, прежде чем инициировать свою.
        page.wait_for_timeout(200)

        page.go_back()
        assert page.url.rstrip("/") == BASE_URL, (
            f"После закрытия крестиком фиктивная запись истории должна "
            f"быть 'смыта' — 'назад' должен сразу вести на главную, "
            f"получили: {page.url}"
        )


# ── 4. Поиск по жанру ─────────────────────────────────────────────

class TestSearchByGenre:
    def test_genre_click_shows_films(self, page: Page):
        """Клик по жанру 'Action' возвращает список фильмов."""
        page.goto(BASE_URL)
        page.click("a.genre-pill:has-text('Action')")
        page.wait_for_selector(".film-card", timeout=5000)

        # В строке результатов должен быть жанр
        expect(page.locator(".results-count")).to_contain_text("Action")

        # Карточки фильмов присутствуют
        assert page.locator(".film-card").count() > 0

    def test_genre_plus_year_form(self, page: Page):
        """Форма с жанром и годами возвращает результаты."""
        page.goto(BASE_URL)

        # Выбираем жанр в dropdown
        page.select_option("select[name='genre']", "Comedy")

        # Вводим диапазон годов
        page.fill("input[name='year_from']", "1990")
        page.fill("input[name='year_to']", "2026")

        # Нажимаем кнопку-фильтр
        page.click("button.gy-btn")
        page.wait_for_selector(".film-card", timeout=5000)

        expect(page.locator(".results-count")).to_contain_text("Comedy")
        assert page.locator(".film-card").count() > 0

    def test_year_out_of_range_shows_error(self, page: Page):
        """Год вне диапазона 1990–2026 (в т.ч. отрицательный) блокирует поиск с сообщением.

        Переходим по прямой ссылке (не через клик по кнопке формы), потому что
        браузерная HTML5-валидация (min="1990" на поле) сама не даст отправить
        форму со значением -5 — здесь же проверяется именно серверная защита.
        """
        page.goto(f"{BASE_URL}/search?genre=Comedy&year_from=-5&year_to=2026")

        error = page.locator(".alert-db-error")
        expect(error).to_be_visible()
        expect(error).to_contain_text("1990")
        # Карточек фильмов быть не должно — поиск не выполнялся.
        assert page.locator(".film-card").count() == 0

    def test_year_from_greater_than_year_to_shows_error(self, page: Page):
        """«Год от» больше «Год до» — тоже некорректный диапазон."""
        page.goto(f"{BASE_URL}/search?genre=Comedy&year_from=2020&year_to=1995")

        error = page.locator(".alert-db-error")
        expect(error).to_be_visible()
        assert page.locator(".film-card").count() == 0


# ── 5. Пагинация ──────────────────────────────────────────────────

class TestPagination:
    def test_next_10_button_visible(self, page: Page):
        """Поиск по 'the' показывает кнопку «Следующие 10»."""
        page.goto(f"{BASE_URL}/search?q=the")
        page.wait_for_selector(".film-card", timeout=5000)

        next_btn = page.locator("a.pagination-btn:has-text('Следующие 10')")
        expect(next_btn).to_be_visible()

    def test_next_page_loads_new_films(self, page: Page):
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

    def test_prev_button_returns_to_first_page(self, page: Page):
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
    def test_stats_page_loads(self, page: Page):
        """/stats открывается, заголовок MongoDB Analytics виден."""
        page.goto(f"{BASE_URL}/stats")
        expect(page).to_have_title("ITCH Films — Статистика")
        expect(page.locator("h1")).to_contain_text("MongoDB Analytics")

    def test_total_searches_counter_positive(self, page: Page):
        """Карточка 'Всего поисков' показывает число > 0."""
        page.goto(f"{BASE_URL}/stats")

        # Первая stat-value — «Всего поисков»
        total_text = page.locator(".stat-value").first.inner_text().strip()
        assert total_text.isdigit(), f"Ожидалось число, получено: '{total_text}'"
        assert int(total_text) > 0, "Счётчик поисков равен 0 — MongoDB не пишет логи"

    def test_popular_queries_displayed(self, page: Page):
        """Блок «Топ-5 популярных запросов» содержит элементы."""
        page.goto(f"{BASE_URL}/stats")

        popular_items = page.locator(".popular-item")
        assert popular_items.count() > 0, "Популярные запросы не отображаются"

    def test_recent_queries_displayed(self, page: Page):
        """Блок «Последние 5 запросов» содержит элементы."""
        page.goto(f"{BASE_URL}/stats")

        recent_items = page.locator(".recent-item")
        assert recent_items.count() > 0, "Последние запросы не отображаются"

    def test_total_searches_card_is_link(self, page: Page):
        """Карточка 'Всего поисков' — это ссылка на /stats/searches."""
        page.goto(f"{BASE_URL}/stats")

        link = page.locator("a.stat-card-link[href*='stats/searches']")
        expect(link).to_be_visible()

        # Проверяем что содержит число и подпись
        expect(link).to_contain_text("Всего поисков")

    def test_unique_queries_card_is_link(self, page: Page):
        """Карточка 'Уникальных запросов' — это ссылка на /stats/unique."""
        page.goto(f"{BASE_URL}/stats")

        link = page.locator("a.stat-card-link[href*='stats/unique']")
        expect(link).to_be_visible()
        expect(link).to_contain_text("Уникальных запросов")


# ── 7. Детальный список: все поиски ───────────────────────────────

class TestStatsSearches:
    def test_page_loads(self, page: Page):
        """/stats/searches загружается с таблицей записей."""
        page.goto(f"{BASE_URL}/stats/searches")
        expect(page).to_have_title("ITCH Films — Все поиски")
        expect(page.locator("h1")).to_contain_text("Все поиски")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_table_has_rows(self, page: Page):
        """В таблице есть хотя бы одна запись из MongoDB."""
        page.goto(f"{BASE_URL}/stats/searches")
        rows = page.locator(".stats-table tbody tr")
        assert rows.count() > 0, "Таблица пустая — MongoDB не возвращает данные"

    def test_search_type_badges_present(self, page: Page):
        """Строки содержат бейджи 🔎 Search или 🎭 Genre."""
        page.goto(f"{BASE_URL}/stats/searches")
        badges = page.locator(".recent-type-badge")
        assert badges.count() > 0, "Бейджи типов поиска не найдены"

    def test_header_record_count_badge(self, page: Page):
        """Бейдж в шапке показывает общее число записей."""
        page.goto(f"{BASE_URL}/stats/searches")
        badge_text = page.locator(".stats-db-badge").inner_text()
        assert "записей" in badge_text, f"Счётчик не найден: '{badge_text}'"
        # Извлекаем число и проверяем что оно > 0
        number = badge_text.split()[0]
        assert number.isdigit() and int(number) > 0

    def test_back_link_returns_to_stats(self, page: Page):
        """Кнопка «← Статистика» возвращает на /stats."""
        page.goto(f"{BASE_URL}/stats/searches")
        page.click("a.stats-back-link")
        expect(page).to_have_url(f"{BASE_URL}/stats")
        expect(page.locator("h1")).to_contain_text("MongoDB Analytics")

    def test_stats_card_click_opens_list(self, page: Page):
        """Клик по карточке 'Всего поисков' на /stats ведёт сюда."""
        page.goto(f"{BASE_URL}/stats")
        page.click("a.stat-card-link[href*='stats/searches']")
        expect(page).to_have_url(f"{BASE_URL}/stats/searches")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_next_10_pagination(self, page: Page):
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

    def test_second_page_via_offset(self, page: Page):
        """offset=10 загружает вторую страницу и показывает «Предыдущие 10»."""
        page.goto(f"{BASE_URL}/stats/searches?offset=10")
        expect(page.locator(".stats-table")).to_be_visible()
        expect(
            page.locator("a.pagination-btn:has-text('Предыдущие 10')")
        ).to_be_visible()


# ── 8. Детальный список: уникальные запросы ───────────────────────

class TestStatsUnique:
    def test_page_loads(self, page: Page):
        """/stats/unique загружается с таблицей уникальных запросов."""
        page.goto(f"{BASE_URL}/stats/unique")
        expect(page).to_have_title("ITCH Films — Уникальные запросы")
        expect(page.locator("h1")).to_contain_text("Уникальные запросы")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_table_has_rows(self, page: Page):
        """Таблица уникальных запросов не пустая."""
        page.goto(f"{BASE_URL}/stats/unique")
        rows = page.locator(".stats-table tbody tr")
        assert rows.count() > 0, "Таблица пустая"

    def test_count_column_format(self, page: Page):
        """Колонка с × count присутствует в строках."""
        page.goto(f"{BASE_URL}/stats/unique")
        counts = page.locator(".popular-count")
        assert counts.count() > 0, "Колонка 'Раз искали' не найдена"
        # Проверяем формат первого значения: «× N»
        first = counts.first.inner_text().strip()
        assert first.startswith("×"), f"Неожиданный формат: '{first}'"

    def test_sorted_by_frequency_desc(self, page: Page):
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

    def test_unique_card_click_opens_list(self, page: Page):
        """Клик по карточке 'Уникальных запросов' на /stats ведёт сюда."""
        page.goto(f"{BASE_URL}/stats")
        page.click("a.stat-card-link[href*='stats/unique']")
        expect(page).to_have_url(f"{BASE_URL}/stats/unique")
        expect(page.locator(".stats-table")).to_be_visible()

    def test_back_link(self, page: Page):
        """Кнопка «← Статистика» возвращает на /stats."""
        page.goto(f"{BASE_URL}/stats/unique")
        page.click("a.stats-back-link")
        expect(page).to_have_url(f"{BASE_URL}/stats")
