"""QORA AI Concierge — intent-based assistant that recommends marketplace services."""
import re

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_optional_user
from app.db.base import get_db
from app.db.models import Category, Service
from app.schemas.schemas import ChatIn, ChatOut, ServiceBrief

router = APIRouter(prefix="/assistant", tags=["assistant"])

STOPWORDS = {
    "a", "an", "the", "i", "me", "my", "for", "to", "of", "in", "on", "and", "or",
    "is", "are", "do", "does", "can", "you", "your", "with", "that", "this", "need",
    "want", "looking", "find", "get", "help", "please", "what", "which", "how", "we",
    "our", "us", "service", "services", "ai", "qora", "buy", "order", "about",
}


def _keywords(message: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", message.lower())
    return [w for w in words if w not in STOPWORDS]


def _brief(s: Service) -> ServiceBrief:
    return ServiceBrief(
        id=s.id,
        title=s.title,
        price_cents=s.price_cents,
        rating_avg=s.rating_avg,
        delivery_days=s.delivery_days,
        category_name=s.category.name if s.category else "",
    )


def _suggest(db: Session, keywords: list[str], limit: int = 3) -> list[Service]:
    q = (
        select(Service)
        .options(joinedload(Service.category))
        .where(Service.status == "active")
    )
    if keywords:
        clauses = []
        for kw in keywords:
            like = f"%{kw}%"
            clauses.append(
                or_(
                    Service.title.ilike(like),
                    Service.description.ilike(like),
                    Service.tags.ilike(like),
                    Service.category.has(Category.name.ilike(like)),
                )
            )
        q = q.where(or_(*clauses))
    q = q.order_by(Service.rating_avg.desc(), Service.orders_count.desc()).limit(limit)
    return list(db.scalars(q).unique().all())


@router.post("/chat", response_model=ChatOut)
def chat(data: ChatIn, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    msg = data.message.strip().lower()
    kws = _keywords(data.message)

    if any(k in msg for k in ("hello", "hi ", "hey", "salam", "سلام")) or msg in ("hi", "hey", "hello"):
        name = user.full_name.split()[0] if user else "there"
        return ChatOut(
            reply=(
                f"Hi {name}! 👋 I'm the QORA AI Concierge. "
                "Tell me what you need — for example “I need a chatbot for my website” "
                "or “who builds recommendation engines?” — and I'll match you with the right AI services."
            )
        )

    if any(k in msg for k in ("how it works", "how does this work", "platform", "what is qora")):
        return ChatOut(
            reply=(
                "QORA is a consumer AI service network: vetted providers publish AI services "
                "(chatbots, vision, data, automation…), you order with your wallet, track delivery, "
                "and pay only when the order is completed. Providers keep "
                "90% of each sale — QORA charges a 10% platform fee."
            )
        )

    if any(k in msg for k in ("wallet", "payment", "pay", "price", "cost", "top up", "topup")):
        return ChatOut(
            reply=(
                "Payments work through your QORA wallet: top it up from the Wallet page, "
                "then order any service instantly. If an order is cancelled before completion "
                "you get a full refund back to your wallet."
            )
        )

    if any(k in msg for k in ("provider", "sell", "offer", "freelance", "earn")):
        return ChatOut(
            reply=(
                "Great — become a provider! Register with a provider account, then publish your AI "
                "service from the Provider dashboard with pricing and delivery time. "
                "You receive 90% of every completed order."
            )
        )

    services = _suggest(db, kws)
    if services:
        names = ", ".join(f"“{s.title}”" for s in services[:2])
        return ChatOut(
            reply=(
                f"Here's what I found for you — {names}. "
                "Tap a suggestion below to open the service page and order it."
            ),
            suggestions=[_brief(s) for s in services],
        )

    top = _suggest(db, [], limit=3)
    return ChatOut(
        reply=(
            "I couldn't find an exact match, but these top-rated services are a good place to start. "
            "Try rephrasing with a capability (e.g. “chatbot”, “image”, “data”, “voice”)."
        ),
        suggestions=[_brief(s) for s in top],
    )
