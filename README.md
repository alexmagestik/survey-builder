# Survey Builder

Мини-SaaS для создания онлайн-опросов: анкет, тестов и голосований. Создатель
регистрируется, собирает опрос, получает уникальную ссылку и смотрит статистику.
Респонденту регистрация не нужна — достаточно указать имя.

## Возможности

- Регистрация и вход создателей (email + пароль).
- Создание опроса: название, описание, произвольное число вопросов.
- Типы вопросов:
  - один вариант;
  - несколько вариантов;
  - свободный текст;
  - для вопросов с выбором — дополнительное поле «Свой вариант».
- Готовые Jinja2-шаблоны:
  - опрос удовлетворённости;
  - анкета после покупки;
  - тестирование знаний по Python.
- Уникальная короткая ссылка вида `/survey/a82jd92k`.
- Прохождение опроса без регистрации, обязательное имя.
- Тесты с правильными ответами и автоматическим подсчётом баллов.
- Статистика: количество ответов, распределение вариантов, текстовые ответы,
  последние отправки, средний балл для тестов.
- Все данные — в SQLite через SQLAlchemy.
- Демо-данные: 3 опроса и ответы для наглядной статистики.

## Стек

- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2.0
- SQLite
- Jinja2
- bcrypt, itsdangerous, python-multipart

## Структура проекта

```
survey-builder/
├── auth/                    # регистрация, вход, сессии, CSRF
├── surveys/                 # создание, валидация, публичное прохождение
├── database/                # модели, подключение, seed
├── analytics/               # агрегаты статистики
├── templates/               # HTML-шаблоны и survey_templates/*.json.j2
├── static/                  # CSS и JS
├── tests/                   # pytest-тесты
├── main.py                  # точка входа FastAPI
├── config.py                # настройки из окружения
├── web.py                   # Jinja2, flash, CSRF-контекст
├── requirements.txt
└── README.md
```

## Быстрый старт

```bash
cd /Users/alex/Documents/Zerocoder/VIBE-CODE/survey-builder
source .venv/bin/activate
pip install -r requirements.txt
python -m database.seed
uvicorn main:app --reload
```

Откройте <http://127.0.0.1:8000>.

Демо-доступ:

```
email:    demo@example.com
password: demo12345
```

Команда seed создаёт демо-пользователя, три опроса из шаблонов и по 8 ответов
на каждый. В консоли печатаются ссылки вида `/survey/xxxxxxxx`.

Пересоздать базу с нуля:

```bash
python -m database.seed --reset
```

## Настройки

Скопируйте `.env.example` в `.env`, если нужно поменять значения:

```bash
cp .env.example .env
```

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SECRET_KEY` | dev-значение | подпись сессионных cookie |
| `DATABASE_URL` | `sqlite:///database/survey.db` | подключение к БД |
| `DEMO_EMAIL` | `demo@example.com` | email демо-пользователя |
| `DEMO_PASSWORD` | `demo12345` | пароль демо-пользователя |

## Как пользоваться

1. Зарегистрируйтесь или войдите под демо-пользователем.
2. Нажмите «Создать опрос».
3. Заполните название и описание.
4. Добавьте вопросы:
   - «Один вариант» или «Несколько вариантов» — заполните варианты;
   - «Свободный текст» — респондент введёт ответ сам;
   - «Свой вариант» — разрешает ответ «Другое» с текстом.
5. Для теста включите «Это тест с правильными ответами» и отметьте верные
   варианты галочкой «верный».
6. Сохраните опрос — на странице опроса будет готовая ссылка.
7. Отправьте ссылку респондентам.
8. Откройте «Статистика», чтобы увидеть ответы.

Можно начать с шаблона: на странице создания опроса нажмите «Заполнить» у
нужного шаблона — конструктор заполнится вопросами, которые можно поправить.

## Шаблоны опросов

Шаблоны лежат в `templates/survey_templates/` и являются настоящими Jinja2-
шаблонами, которые рендерятся в JSON-описание опроса:

- `satisfaction.json.j2` — оценка удовлетворённости;
- `post_purchase.json.j2` — анкета после покупки;
- `knowledge_test.json.j2` — тест по основам Python с баллами.

Пример:

```jinja
{% set scale = ["1 — очень плохо", "2 — плохо", "3 — нейтрально"] %}
{
  "key": "satisfaction",
  "title": {{ "Оценка сервиса" | tojson }},
  "questions": [
    {
      "text": {{ "Насколько вы довольны?" | tojson }},
      "type": "single",
      "required": true,
      "options": [
        {% for item in scale %}
        {"text": {{ item | tojson }}, "correct": false}{% if not loop.last %},{% endif %}
        {% endfor %}
      ]
    }
  ]
}
```

Загрузчик (`surveys/template_loader.py`) рендерит шаблон, парсит JSON и
валидирует его через Pydantic.

## Схема базы данных

```
users
  id, email UNIQUE, password_hash, created_at

surveys
  id, user_id → users.id, slug UNIQUE, title, description,
  template_key, scoring_enabled, is_active, created_at

questions
  id, survey_id → surveys.id, text,
  type ('single' | 'multiple' | 'text'),
  allow_other, required, position

options
  id, question_id → questions.id, text, position, is_correct

responses
  id, survey_id → surveys.id, respondent_name,
  score, max_score, created_at

answers
  id, response_id → responses.id, question_id → questions.id,
  option_id → options.id, text_value
```

Связи:

```
User 1─N Survey 1─N Question 1─N Option
                  │
                  └─N Response 1─N Answer N─1 Question
                                      └─N Option
```

`responses` группирует ответы одной отправки. Таблица `answers` хранит ответы
по конкретным вопросам: выбранный вариант (`option_id`) или текст
(`text_value`).

## Основные маршруты

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/` | главная |
| GET/POST | `/auth/register` | регистрация |
| GET/POST | `/auth/login` | вход |
| POST | `/auth/logout` | выход |
| GET | `/surveys` | мои опросы |
| GET | `/surveys/new` | конструктор |
| POST | `/surveys` | создать опрос |
| GET | `/surveys/{id}` | карточка и ссылка |
| POST | `/surveys/{id}/delete` | удалить опрос |
| GET | `/surveys/{id}/stats` | статистика |
| GET | `/survey/{slug}` | публичная форма |
| POST | `/survey/{slug}` | отправить ответы |
| GET | `/survey/{slug}/thanks` | спасибо / результат теста |

## Тесты

```bash
.venv/bin/pytest -q
```

Покрыто: регистрация и вход, CSRF, создание опроса, уникальность ссылки,
удаление, доступ владельца, публичная отправка, обязательные поля, подмена
варианта, неактивный опрос, подсчёт баллов, статистика и средний балл.

## Безопасность

- Пароли хранятся как bcrypt-хеши.
- Сессии подписаны `SECRET_KEY`.
- Все POST-формы защищены CSRF-токеном.
- Проверяется владелец опроса: чужие опросы и статистика возвращают 404.
- Jinja2 autoescape защищает от XSS; пользовательский текст не выводится через `|safe`.
- SQL-запросы строятся через SQLAlchemy ORM.
- `next` при входе проверяется, чтобы не было open redirect.

## Ограничения текущей версии

- Нет редактирования вопросов после создания — только создание и удаление.
- Нет подтверждения email, восстановления пароля и rate limiting.
- Нет экспорта в CSV/Excel, загрузки файлов и ветвления вопросов.
- Миграции не подключены: для изменения схемы в разработке используйте
  `python -m database.seed --reset`.
- SQLite подходит для демо и небольшой нагрузки; для продакшена стоит взять
  PostgreSQL и Alembic.

## Лицензия

Учебный проект. Используйте свободно.
