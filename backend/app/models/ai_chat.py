from sqlalchemy import BigInteger, DECIMAL, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")

    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
