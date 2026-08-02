"""
SQLAlchemy модели таблиц базы данных.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Date, Time, Text,
    DateTime, Boolean, ForeignKey, UniqueConstraint, PrimaryKeyConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class Source(Base):
    """Источник данных (Telegram канал или сайт)."""
    __tablename__ = "sources"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String(200), nullable=False, unique=True)
    type      = Column(String(20), nullable=False)   # telegram | website
    url       = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Source {self.name!r} ({self.type})>"


class Event(Base):
    """Мероприятие."""
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(200), nullable=False)
    event_date  = Column(Date, nullable=False)
    event_time  = Column(Time, nullable=True)
    location    = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    source_url  = Column(Text, nullable=False)
    source_name = Column(String(200), nullable=True)
    price       = Column(String(100), nullable=True)
    category    = Column(String(50), nullable=True)
    source_id   = Column(Integer, ForeignKey("sources.id"), nullable=False)
    source      = relationship("Source", backref="events")

    # Поля по ТЗ
    language    = Column(String(20), nullable=True)   # ru | en | ru+en
    event_type  = Column(String(50), nullable=True)   # conference | meetup | forum | exhibition | seminar
    speakers    = Column(Text, nullable=True)
    is_online   = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Дедупликация: source_name + title + date
    __table_args__ = (
        UniqueConstraint("source_name", "title", "event_date", name="uq_event_source_title_date"),
    )

    def __repr__(self):
        return f"<Event {self.title!r} on {self.event_date}>"


class Publication(Base):
    """История публикаций в Telegram."""
    __tablename__ = "publications"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    published_at    = Column(DateTime, nullable=False, default=datetime.utcnow)
    telegram_msg_id = Column(String(50), nullable=True)
    period_from     = Column(Date, nullable=False)
    period_to       = Column(Date, nullable=False)
    success         = Column(Boolean, default=True)
    error_message   = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    events = relationship("PublicationEvent", back_populates="publication", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Publication {self.published_at} ok={self.success}>"


class PublicationEvent(Base):
    """Связь публикации ↔ событие (M2M)."""
    __tablename__ = "publication_events"

    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    event_id       = Column(Integer, ForeignKey("events.id"), nullable=False)

    publication = relationship("Publication", back_populates="events")
    event       = relationship("Event")

    __table_args__ = (
        PrimaryKeyConstraint("publication_id", "event_id"),
    )
