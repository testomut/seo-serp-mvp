# SEO SERP MVP

[![tests](https://github.com/testomut/seo-serp-mvp/actions/workflows/tests.yml/badge.svg)](https://github.com/testomut/seo-serp-mvp/actions/workflows/tests.yml)
[![daily](https://github.com/testomut/seo-serp-mvp/actions/workflows/daily.yml/badge.svg)](https://github.com/testomut/seo-serp-mvp/actions/workflows/daily.yml)

Каждый день собирает топ-10 Google.ca (mobile) по 10 ключам, хранит историю позиций и размечает каждый новый URL
с помощью LLM: подходит ли сайт для размещения, какие казино-бренды на нём, контакт владельца.

**Результат:** [Google-таблица](https://docs.google.com/spreadsheets/d/1cYC54BHTFjoNOcc95wbD3JBvfgg0xfXZahCWhIuQ5sU) (обновляется каждый день, только просмотр) · [`results.xlsx`](results.xlsx) (вкладки Help, Sites, Positions). **Видео:** [демонстрация, 4 мин](https://www.loom.com/share/86c5c1098ab6481884b60d504c0aef3f).
Подробнее: [как устроено](docs/DETAILS.md) · [проверка 20 URL](docs/QUALITY.md) · [запуск у себя](docs/SETUP.md) · [для менеджера](docs/MANAGER.md).

## Запуск (Python 3.12)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
python main.py --demo             # без ключей: демо-выдача, отдельные demo.db и demo-results.xlsx
```

Реальный прогон: `cp .env.example .env` (Windows: `copy`), вписать `SEARCHAPI_KEY` и `GEMINI_API_KEY`,
`python main.py`. Тесты: `python -m pytest`.

## Инструменты и почему

| Задача | Выбор | Почему |
|---|---|---|
| Выдача | SearchApi.io, резерв SerpApi | Мобильная выдача с гео Канада; свой парсинг Google упирается в капчу |
| LLM | Gemini Flash-Lite, резерв Claude / OpenAI | Бесплатный тариф, JSON-ответ; ответ проверяется по схеме |
| Хранение | SQLite + Excel / Google Sheets | SQLite без сервера; Excel и Sheets - вид для менеджера |
| Расписание | GitHub Actions | Бесплатно, без сервера |

## Стоимость прогона

**$0** на бесплатных тарифах. Допущения для платных: 10-13 поисков (вторая страница, если Google дал меньше 10)
по $0.004-0.015 = $0.05-0.20; разметка в Gemini Flash-Lite: первый прогон ~85 страниц × ~4 тыс. токенов ≈ $0.04,
дальше только новые URL (~30 в день) ≈ $0.015.

**Итого на платных тарифах: примерно $0.06-0.25 за прогон, $2-6 в месяц при ежедневном запуске.**

## Что сознательно не сделал

- Проход партнёрских редиректов (на какой бренд ведёт ссылка) - медленно и накручивает чужие клики;
  бренды и так берутся из текста и логотипов.
- Обход Cloudflare / JS-рендеринг: такие сайты помечаются `unknown` (на серверах GitHub их больше) -
  нужен тяжёлый браузер, а обход защиты - серая зона; лучше честный `unknown`, чем догадка.
- Поиск контакта глубже первой страницы; контакт на чужом домене (например, материнской компании) не берётся -
  нельзя надёжно отличить владельца от любой внешней ссылки; лучше пусто, чем неверно.
- Несколько стран и устройств: сейчас задаются одной строкой в `config.py` - по заданию нужна только
  Канада/mobile, а каждая комбинация добавляет 10-13 поисков за прогон и колонки в базе.

## Что дальше

Повторная ручная проверка 20 URL после перепроверки базы разметкой v2, проход редиректов, Playwright для JS-сайтов,
страны и устройства как колонки во вкладке Keywords, статус работы с сайтом (написали / ответили) в таблице.
