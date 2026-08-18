import json
from pathlib import Path

from sqlalchemy import select

from backend.app.core.security import hash_password
import backend.app.db.model_registry  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.tariff import Tariff
from backend.app.models.task import Task, TaskCategory
from backend.app.models.theory import TheoryTopic
from backend.app.models.user import User, UserProfile
from backend.app.models.variant import Variant, VariantTask


ROOT_DIR = Path(__file__).resolve().parents[3]
THEORY_JSON_PATH = ROOT_DIR / "static" / "data" / "theory-data.json"


def exam_by_grade(grade: int) -> str:
    return "oge" if grade == 9 else "vpr"

def build_rich_content(payload: dict) -> list[dict]:
    blocks = payload.get("content_json")
    if isinstance(blocks, list):
        return blocks

    rich_blocks: list[dict] = []
    text = str(payload.get("text") or "").strip()
    if text:
        rich_blocks.append({"type": "paragraph", "text": text})

    concepts = payload.get("concepts") or []
    if isinstance(concepts, list) and concepts:
        rich_blocks.append({"type": "heading", "level": 3, "text": "Ключевые понятия"})
        rich_blocks.append({"type": "list", "style": "unordered", "items": [str(item) for item in concepts if str(item).strip()]})

    example = str(payload.get("example") or "").strip()
    if example:
        rich_blocks.append({"type": "heading", "level": 3, "text": "Пример"})
        rich_blocks.append({"type": "paragraph", "text": example})

    tip = str(payload.get("tip") or "").strip()
    if tip:
        rich_blocks.append({"type": "callout", "variant": "gray", "title": "Совет", "text": tip})

    return rich_blocks


def seed_theory(db):
    if not THEORY_JSON_PATH.exists():
        return

    data = json.loads(THEORY_JSON_PATH.read_text(encoding="utf-8-sig"))

    # Full refresh for grades 7-9 theory block.
    for topic in db.execute(select(TheoryTopic).join(TaskCategory, TaskCategory.id == TheoryTopic.category_id).where(TaskCategory.grade.in_([7, 8, 9]))).scalars().all():
        db.delete(topic)
    for category in db.execute(select(TaskCategory).where(TaskCategory.grade.in_([7, 8, 9]))).scalars().all():
        db.delete(category)
    db.flush()

    for grade_str, topics in data.items():
        grade = int(grade_str)
        exam_type = exam_by_grade(grade)
        for idx, (slug, payload) in enumerate(topics.items(), start=1):
            code = f"topic_{grade}_{slug}"
            category = TaskCategory(
                code=code,
                title=payload["title"],
                exam_type=exam_type,
                grade=grade,
                sort_order=idx,
            )
            db.add(category)
            db.flush()

            topic = TheoryTopic(
                category_id=category.id,
                slug=slug,
                content_json=build_rich_content(payload),
                sort_order=idx,
            )
            db.add(topic)
            db.flush()


def seed_user(db):
    email = "student@example.com"
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        return
    free = db.execute(select(Tariff).where(Tariff.code == "free")).scalar_one_or_none()
    user = User(
        name="Тестовый ученик",
        email=email,
        password_hash=hash_password("password123"),
        role="student",
        grade=8,
        paid_tariff_id=free.id if free else None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, school="Школа №1", city="Москва"))


def seed_tariffs(db):
    tariffs = [
        ("free", "Бесплатный", 0, 36500, "Базовый доступ", '["theory_basic", "practice_basic"]'),
        ("base", "Базовый", 299, 30, "Полная теория и тренировки", '["theory_basic", "practice_basic", "theory_full", "practice_full"]'),
        ("optimum", "Оптимальный", 599, 30, "Полный доступ", '["theory_basic", "practice_basic", "theory_full", "practice_full", "variants", "advanced_stats"]'),
    ]
    for code, title, price, duration_days, desc, features in tariffs:
        exists = db.execute(select(Tariff).where(Tariff.code == code)).scalar_one_or_none()
        if exists:
            exists.title = title
            exists.price = price
            exists.duration_days = duration_days
            exists.description = desc
            exists.features_json = features
            exists.is_active = True
        else:
            db.add(Tariff(code=code, title=title, price=price, duration_days=duration_days, description=desc, features_json=features, is_active=True))


def seed_tasks(db):
    for variant in db.execute(select(Variant).where(Variant.grade.in_([7, 8, 9]))).scalars().all():
        db.delete(variant)
    for task in db.execute(select(Task).where(Task.grade.in_([7, 8, 9]))).scalars().all():
        db.delete(task)
    db.flush()

    topics = db.execute(
        select(TheoryTopic)
        .join(TaskCategory, TaskCategory.id == TheoryTopic.category_id)
        .where(TaskCategory.grade.in_([7, 8, 9]))
        .order_by(TaskCategory.grade.asc(), TaskCategory.sort_order.asc())
    ).scalars().all()

    task_bank = {
        "info-and-properties": [
            ("Какая характеристика означает соответствие информации реальности?", "достоверность", "easy"),
            ("Информация, полезная для решения конкретной задачи, называется ...", "ценной", "easy"),
        ],
        "information-processes": [
            ("Какой процесс происходит при отправке сообщения в мессенджере?", "передача", "easy"),
            ("Какой процесс выполняет архив на диске?", "хранение", "easy"),
        ],
        "coding-and-bits": [
            ("Сколько бит в одном байте?", "8", "easy"),
            ("Как называется минимальная единица количества информации?", "бит", "easy"),
        ],
        "algorithms-basics": [
            ("Как называется повторение действий в алгоритме?", "цикл", "medium"),
            ("Какой элемент алгоритма выбирает путь по условию?", "ветвление", "medium"),
        ],
        "files-and-folders": [
            ("Что в имени report.pdf указывает тип файла?", "расширение", "easy"),
            ("Как называется последовательность папок к файлу?", "путь", "easy"),
        ],
        "safe-internet": [
            ("Как называется кража данных через поддельные сайты?", "фишинг", "medium"),
            ("Что нельзя сообщать посторонним: пароль или логин?", "пароль", "easy"),
        ],
        "information-amount": [
            ("Сколько байт в 1 КБ?", "1024", "easy"),
            ("Единица больше мегабайта — это ...", "гигабайт", "easy"),
        ],
        "number-systems": [
            ("Чему равно 1010(2) в десятичной системе?", "10", "medium"),
            ("Основание двоичной системы счисления?", "2", "easy"),
        ],
        "graphics-coding": [
            ("Минимальный элемент растрового изображения?", "пиксель", "easy"),
            ("Что влияет на размер растрового файла вместе с разрешением?", "глубина цвета", "medium"),
        ],
        "sound-coding": [
            ("Сколько каналов у стереозвука?", "2", "easy"),
            ("Что нужно учесть в размере звука кроме длительности?", "частоту дискретизации", "medium"),
        ],
        "logic-expressions": [
            ("Когда выражение A И B истинно?", "когда оба истинны", "medium"),
            ("Какая операция меняет истину на ложь?", "не", "easy"),
        ],
        "spreadsheets": [
            ("Как называется прямоугольная группа ячеек?", "диапазон", "easy"),
            ("Какая функция считает сумму в таблице?", "sum", "easy"),
        ],
        "logic-and-truth-tables": [
            ("Что строят для анализа логической формулы?", "таблицу истинности", "easy"),
            ("Какая операция выполняется раньше: НЕ или ИЛИ?", "не", "medium"),
        ],
        "algorithms-and-flowcharts": [
            ("Какой блок в блок-схеме обозначает условие?", "ромб", "easy"),
            ("Как называется возврат к предыдущему шагу алгоритма?", "цикл", "medium"),
        ],
        "programming-basics": [
            ("Где хранится изменяемое значение в программе?", "переменная", "easy"),
            ("Какой цикл удобен при известном числе повторов?", "for", "medium"),
        ],
        "data-analysis": [
            ("Какая операция оставляет строки по условию?", "фильтр", "easy"),
            ("Функция для среднего значения в таблице?", "срзнач", "medium"),
        ],
        "databases": [
            ("Как называется строка в таблице базы данных?", "запись", "easy"),
            ("Как называется команда выбора данных в SQL?", "select", "medium"),
        ],
        "networks-and-internet": [
            ("Что сопоставляет доменное имя и IP-адрес?", "dns", "medium"),
            ("Какой протокол защищенного веб-доступа?", "https", "easy"),
        ],
    }

    for topic in topics:
        if not topic.category_id:
            continue
        category = db.get(TaskCategory, topic.category_id)
        if not category:
            continue
        pairs = task_bank.get(topic.slug, [])
        for idx, (question, answer, difficulty) in enumerate(pairs, start=1):
            db.add(
                Task(
                    category_id=category.id,
                    grade=int(category.grade or 0),
                    exam_type=category.exam_type,
                    title=f"{category.title} · Задание {idx}",
                    question=question,
                    answer=answer,
                    hint=f"Вспомните основные определения по теме «{category.title}».",
                    explanation=f"Тема: {category.title}",
                    difficulty=difficulty,
                    source="seed-new",
                )
            )


def seed_variants(db):
    variants = [
        ("ВПР 7 · Вариант 1", "vpr", 7, "Базовый тренировочный вариант для 7 класса.", 45),
        ("ВПР 7 · Вариант 2", "vpr", 7, "Вариант с акцентом на алгоритмы и файлы.", 45),
        ("ВПР 7 · Вариант 3", "vpr", 7, "Пробный вариант для самопроверки.", 45),
        ("ВПР 8 · Вариант 1", "vpr", 8, "Базовый тренировочный вариант для 8 класса.", 45),
        ("ВПР 8 · Вариант 2", "vpr", 8, "Вариант со смешанными заданиями.", 45),
        ("ВПР 8 · Вариант 3", "vpr", 8, "Пробный вариант для самопроверки.", 45),
        ("ОГЭ · Вариант 1", "oge", 9, "Базовый тренировочный вариант в формате ОГЭ.", 150),
        ("ОГЭ · Вариант 2", "oge", 9, "Вариант со смешанными заданиями и разной сложностью.", 150),
        ("ОГЭ · Вариант 3", "oge", 9, "Пробный вариант для итоговой самопроверки.", 150),
    ]

    for title, exam_type, grade, description, time_limit_minutes in variants:
        variant = db.execute(
            select(Variant).where(
                Variant.title == title,
                Variant.exam_type == exam_type,
                Variant.grade == grade,
            )
        ).scalar_one_or_none()

        if not variant:
            variant = Variant(
                title=title,
                exam_type=exam_type,
                grade=grade,
                description=description,
                time_limit_minutes=time_limit_minutes,
            )
            db.add(variant)
            db.flush()
        else:
            variant.description = description
            variant.time_limit_minutes = time_limit_minutes

        db.query(VariantTask).filter(VariantTask.variant_id == variant.id).delete()
        tasks = db.execute(
            select(Task).where(Task.exam_type == exam_type, Task.grade == grade).order_by(Task.id.asc())
        ).scalars().all()
        for idx, task in enumerate(tasks, start=1):
            db.add(VariantTask(variant_id=variant.id, task_id=task.id, sort_order=idx, points=1))


def run_seed():
    db = SessionLocal()
    try:
        seed_tariffs(db)
        seed_user(db)
        seed_theory(db)
        seed_tasks(db)
        seed_variants(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
