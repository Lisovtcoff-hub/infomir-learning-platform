from backend.app.crud.attempt import create_attempt, finish_attempt, get_attempts_for_user, save_attempt_answer
from backend.app.crud.tariff import get_tariff_by_code, get_tariffs
from backend.app.crud.task import check_answer, get_task, get_tasks
from backend.app.crud.theory import create_or_update_topic, get_topic_by_slug, get_topics
from backend.app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_id, update_user_profile
from backend.app.crud.variant import get_variant_with_tasks, get_variants

__all__ = [
    "authenticate_user",
    "check_answer",
    "create_attempt",
    "create_or_update_topic",
    "create_user",
    "finish_attempt",
    "get_attempts_for_user",
    "get_task",
    "get_tariff_by_code",
    "get_tariffs",
    "get_tasks",
    "get_topic_by_slug",
    "get_topics",
    "get_user_by_email",
    "get_user_by_id",
    "get_variant_with_tasks",
    "get_variants",
    "save_attempt_answer",
    "update_user_profile",
]
