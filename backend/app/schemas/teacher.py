from pydantic import BaseModel, ConfigDict


class TeacherStudentRead(BaseModel):
    id: int
    name: str
    email: str
    grade: int | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TeacherGroupRead(BaseModel):
    id: int
    title: str
    students_count: int


class TeacherGroupCreate(BaseModel):
    title: str


class TeacherGroupUpdate(BaseModel):
    title: str


class TeacherDashboardStatsRead(BaseModel):
    connected_students_count: int
    average_percent: int
    average_grade: float
    earnings_total: float
    current_balance: float


class TeacherEarningHistoryItemRead(BaseModel):
    payment_id: int
    student_id: int
    student_name: str
    student_email: str
    group_title: str | None = None
    tariff_title: str
    tariff_price: float
    teacher_share: float
    paid_at: str


class TeacherWithdrawalHistoryItemRead(BaseModel):
    id: int
    amount: float
    status: str
    created_at: str


class TeacherWithdrawalCreateRead(BaseModel):
    id: int
    amount: float
    created_at: str
    current_balance: float
    status: str = "requested"


class TeacherEarningsHistoryRead(BaseModel):
    total_earned: float
    current_balance: float
    withdrawals: list[TeacherWithdrawalHistoryItemRead]
    items: list[TeacherEarningHistoryItemRead]


class TeacherGroupedStudentRead(BaseModel):
    id: int
    name: str
    grade: int | None = None
    predicted_grade: float
    tariff_title: str | None = None


class TeacherGroupWithStudentsRead(BaseModel):
    id: int
    title: str
    students_count: int
    students: list[TeacherGroupedStudentRead]


class TeacherStudentVariantResultRead(BaseModel):
    attempt_id: int
    title: str
    percent: int
    grade_mark: int | None = None
    finished_at: str | None = None


class TeacherStudentTaskHistoryRead(BaseModel):
    attempt_id: int
    task_id: int
    task_code: str | None = None
    topic_id: int | None = None
    topic_title: str | None = None
    is_correct: bool | None = None
    checked_at: str | None = None
    user_answer: str | None = None
    correct_answer: str | None = None
    task_prompt: str | None = None


class TeacherStudentGroupRead(BaseModel):
    id: int
    title: str


class TeacherStudentDetailsRead(BaseModel):
    id: int
    name: str
    email: str
    grade: int | None = None
    tariff_title: str | None = None
    solved_total: int
    correct_total: int
    wrong_total: int
    current_groups: list[TeacherStudentGroupRead]
    task_history: list[TeacherStudentTaskHistoryRead]
    variant_results: list[TeacherStudentVariantResultRead]
    weak_topics: list[str]


class TeacherStudentDisconnectRead(BaseModel):
    student_id: int
    removed_from_groups: int


class TeacherStudentMoveRequest(BaseModel):
    source_group_id: int
    target_group_id: int


class TeacherStudentMoveRead(BaseModel):
    student_id: int
    source_group_id: int
    target_group_id: int
