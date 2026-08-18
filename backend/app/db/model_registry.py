# Import models so Alembic autogenerate can discover metadata.
from backend.app.models.attempt import Attempt, AttemptAnswer  # noqa: F401
from backend.app.models.audit import AdminAuditLog  # noqa: F401
from backend.app.models.invite import TeacherInvite  # noqa: F401
from backend.app.models.tariff import Payment, Tariff, TeacherCommission, UserSubscription  # noqa: F401
from backend.app.models.task import Task, TaskCategory, TaskOption  # noqa: F401
from backend.app.models.teacher import TeacherGroup, TeacherGroupMember, TeacherProfile, TeacherWithdrawal  # noqa: F401
from backend.app.models.theory import TheoryTopic, TheoryTopicProgress  # noqa: F401
from backend.app.models.user import User, UserProfile  # noqa: F401
from backend.app.models.variant import Variant, VariantTask  # noqa: F401
