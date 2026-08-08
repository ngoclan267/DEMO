"""
Pydantic schemas shared between the API layer and the agent graph state.
Mirrors the data model in section 15 of the PRD: Users, Topics, Sources,
Posts, Predictions, PainPoints, Notifications.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"          # nguon doi chieu ro rang
    UNVERIFIED = "unverified"      # chua du can cu
    NEEDS_REVIEW = "needs_review"  # Classification va Verification mau thuan


class CaseStatus(str, Enum):
    """Trang thai xu ly (Respond) cua mot Pain Point - lop nghiep vu con nguoi
    thao tac tren ket qua pipeline, khong phai output cua agent nao."""
    OPEN = "open"                  # moi phat hien, chua ai nhan xu ly
    IN_PROGRESS = "in_progress"    # dang duoc xu ly
    RESOLVED = "resolved"          # da xu ly xong


# ---------- Users ----------
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class User(UserBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Topics ----------
class TopicCreate(BaseModel):
    name: str
    keywords: list[str]
    sources: list[str]
    source_configs: dict[str, dict] = Field(
        default_factory=dict,
        description=(
            "Cau hinh crawl that theo tung nguon, vd "
            '{"google_play": {"app_id": "vn.com.techcombank.bb.app"}, '
            '"app_store": {"app_id": "1548623362", "country": "vn"}}'
        ),
    )
    alert_threshold: int = 10
    notifications_enabled: bool = True


class Topic(TopicCreate):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Sources / Posts ----------
class Source(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str          # google_play | app_store | linkedin | facebook ...
    url: Optional[str] = None


class Post(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    topic_id: UUID
    source: str
    author: Optional[str] = None
    content: str
    published_at: datetime
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    is_duplicate: bool = False
    is_spam: bool = False
    # Ket qua Classification Agent, luu lai tren chinh Post de dung cho bieu do
    # xu huong theo ngay/thang (GET /topics/{id}/trend) ma khong phai goi lai
    # LLM moi lan xem bieu do - xem repository.save_post_classifications.
    sentiment: Optional[Sentiment] = None
    topic_label: Optional[str] = None
    severity_score: Optional[float] = None


# ---------- Predictions (Classification Agent output) ----------
class Prediction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    post_id: UUID
    sentiment: Sentiment
    topic_label: str            # dang nhap | giao dich | bao mat | ...
    severity_score: float       # 0..1
    confidence_score: float     # 0..1


# ---------- Verification (Verification Agent output) ----------
class VerificationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    pain_point_id: UUID
    status: VerificationStatus
    reference_sources: list[str] = []
    reliability_score: float = 0.0
    reasoning: str = ""


# ---------- Consensus (Consensus Agent output) ----------
class ConsensusResult(BaseModel):
    pain_point_id: UUID
    agreement: bool
    final_confidence: float
    notes: str = ""


# ---------- Pain Points ----------
class PainPoint(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    topic_id: UUID
    title: str
    topic_label: Optional[str] = None   # nhan noi bo (vd "dang_nhap") - doi chieu voi TrendPoint.by_label
    description: str
    post_count: int
    trend: str                       # "up" | "down" | "flat"
    severity: Severity
    verification_status: VerificationStatus
    confidence_score: float
    sources: list[str] = []
    sample_posts: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # --- Respond (PRD moi bo sung - vong doi xu ly, khong phai output agent) ---
    status: CaseStatus = CaseStatus.OPEN
    assignee: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None


class PainPointUpdate(BaseModel):
    """Payload cap nhat trang thai xu ly (Respond) cho mot Pain Point."""
    status: Optional[CaseStatus] = None
    assignee: Optional[str] = None
    resolution_notes: Optional[str] = None


# ---------- Report (tong hop cross-topic - PRD moi bo sung) ----------
class TopicReportRow(BaseModel):
    topic_id: UUID
    topic_name: str
    total_negative: int
    open_count: int
    in_progress_count: int
    resolved_count: int
    high_severity_open: int
    avg_confidence: float


class ReportSummary(BaseModel):
    total_negative: int
    open_count: int
    in_progress_count: int
    resolved_count: int
    overdue_open_count: int
    avg_resolution_hours: Optional[float] = None
    resolved_within_sla_pct: Optional[float] = None
    by_topic: list[TopicReportRow] = []


# ---------- Trend (xu huong theo ngay - PRD moi bo sung, xem GET /topics/{id}/trend) ----------
class TrendPoint(BaseModel):
    date: str            # YYYY-MM-DD (theo published_at that cua tung phan hoi)
    total_posts: int
    negative_count: int
    by_label: dict[str, int] = {}   # topic_label -> so phan hoi tieu cuc trong ngay, dung cho sparkline tung Pain Point


class TopicTrend(BaseModel):
    topic_id: UUID
    points: list[TrendPoint] = []


# ---------- Notifications ----------
class Notification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    topic_id: UUID
    pain_point_id: UUID
    channel: str            # "email" | "website" | "both"
    title: str
    message: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    read: bool = False
