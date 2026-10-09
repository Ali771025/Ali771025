"""Seed the QORA database with demo users, categories, services, orders and reviews.

Run:  python seed.py
"""
import sys

sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base, SessionLocal, engine
from app.db.models import Category, Order, Review, Service, Transaction, User, Wallet

AVATAR = {
    "admin": "#8b5cf6",
    "sarah": "#0ea5e9",
    "marcus": "#f59e0b",
    "lena": "#10b981",
    "omar": "#ef4444",
    "emma": "#ec4899",
}

CATEGORIES = [
    ("Chatbots & Assistants", "chatbots", "message-square", "Conversational AI, support bots, copilots"),
    ("Image & Vision", "image-vision", "image", "Generation, editing, detection, OCR"),
    ("Data & Analytics", "data-analytics", "bar-chart-3", "Prediction, dashboards, data pipelines"),
    ("Voice & Audio", "voice-audio", "mic", "TTS, transcription, voice cloning"),
    ("Automation & Agents", "automation-agents", "workflow", "Agentic workflows, RPA, integrations"),
    ("NLP & Content", "nlp-content", "file-text", "Writing, translation, summarization"),
    ("ML Engineering", "ml-engineering", "cpu", "Training, fine-tuning, MLOps, deployment"),
    ("Recommendation & Personalization", "recommendation", "target", "Recommenders, ranking, user modeling"),
]

PROVIDERS = [
    ("sarah@qora.ai", "Sarah Chen", "sarah", "Senior AI Engineer · NLP & RAG systems",
     "10+ years building production NLP systems. Ex-search infrastructure. I specialize in RAG pipelines, "
     "fine-tuning and evaluation."),
    ("marcus@qora.ai", "Marcus Webb", "marcus", "ML Solutions Architect · Vision & Automation",
     "I help companies ship computer-vision and automation systems that actually survive production."),
    ("lena@qora.ai", "Lena Novak", "lena", "Data Scientist · Predictive models & analytics",
     "PhD in statistics. I turn messy business data into forecasts and decisions."),
]

CONSUMERS = [
    ("omar@qora.ai", "Omar Farouk", "omar", "Product Manager @ retail startup"),
    ("emma@qora.ai", "Emma Larsson", "emma", "Founder @ D2C brand"),
]

SERVICES = [
    # (title, desc, price_usd, days, category_slug, provider_email, tags)
    ("Custom GPT Support Chatbot", "Production-ready customer-support chatbot trained on your docs and help center. "
     "Includes multilingual answers, human hand-off, analytics dashboard and a 2-week tuning window. Deployed to "
     "your website with a single script tag.", 890, 10, "chatbots", "sarah@qora.ai", "chatbot,rag,support,llm"),
    ("RAG Knowledge Base Setup", "Turn your internal documents into a question-answering system: chunking strategy, "
     "embeddings, hybrid search, citation answers and an evaluation harness. Delivered as a repo plus walkthrough.",
     1250, 14, "chatbots", "sarah@qora.ai", "rag,embeddings,knowledge-base,llm"),
    ("AI Image Generation Pipeline", "Branded image-generation pipeline (SDXL / Flux) with style fine-tuning on your "
     "brand assets, moderation filters and a simple web app for your team.", 1490, 12, "image-vision", "marcus@qora.ai",
     "image,diffusion,brand,generation"),
    ("Object Detection for Quality Control", "Custom YOLO-based defect detection for production lines. Includes data "
     "annotation guide, training, ONNX export and edge deployment instructions.", 2200, 21, "image-vision",
     "marcus@qora.ai", "vision,detection,yolo,edge"),
    ("Document OCR & Extraction", "Extract structured fields from invoices, IDs and contracts. Layout-aware OCR plus "
     "LLM validation with confidence scores. REST API + web demo included.", 980, 9, "image-vision", "marcus@qora.ai",
     "ocr,extraction,documents,api"),
    ("Sales Forecasting Model", "Demand / sales forecasting with gradient boosting + time-series features. Backtests, "
     "confidence intervals and an executive dashboard your team can actually read.", 1350, 15, "data-analytics",
     "lena@qora.ai", "forecasting,analytics,python,tableau"),
    ("Customer Churn Prediction", "Churn scoring model with interpretable risk factors, cohort analysis and a "
     "retention playbook wired to your CRM.", 1100, 12, "data-analytics", "lena@qora.ai", "churn,prediction,crm"),
    ("Realistic Voice Cloning & TTS", "Clone a voice from 30 minutes of audio for narration, IVR and product voice. "
     "Emotion control, 12 languages, commercial license.", 750, 7, "voice-audio", "sarah@qora.ai", "tts,voice,clone,audio"),
    ("Meeting Transcription & Summaries", "Speech-to-text pipeline with speaker diarization, searchable transcripts "
     "and automatic action-item summaries pushed to Slack or email.", 490, 5, "voice-audio", "lena@qora.ai",
     "transcription,asr,summarization,meetings"),
    ("AI Automation Workflows", "Agentic automations that connect your tools (CRM, email, sheets, Slack). Includes "
     "error handling, logging and a month of monitoring.", 640, 8, "automation-agents", "marcus@qora.ai",
     "agents,automation,n8n,workflow"),
    ("LLM Content Engine", "SEO-aware content system: briefs, drafts and brand-tone rewriting with a review queue. "
     "Built on your style guide — no generic AI filler.", 560, 7, "nlp-content", "sarah@qora.ai",
     "content,seo,writing,llm"),
    ("Model Fine-Tuning & Deployment", "Fine-tune and ship your own LLM or embedding model: dataset curation, LoRA / "
     "full fine-tune, eval suite and cost-optimized serving (vLLM).", 2500, 25, "ml-engineering", "sarah@qora.ai",
     "finetuning,vllm,mlops,training"),
    ("Recommendation Engine", "Personalized recommendations (collaborative + content-based) with A/B-ready ranking "
     "API. Proven lift playbook for e-commerce and content platforms.", 1800, 18, "recommendation", "lena@qora.ai",
     "recommendation,ranking,personalization"),
    ("Data Cleaning & Feature Store", "Rescue messy data: dedupe, normalize, enrich and set up a lightweight feature "
     "store your models can rely on.", 420, 6, "data-analytics", "lena@qora.ai", "data,features,etl,cleaning"),
]


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        cats = {}
        for name, slug, icon, desc in CATEGORIES:
            c = Category(name=name, slug=slug, icon=icon, description=desc)
            db.add(c)
            cats[slug] = c
        db.flush()

        admin = User(
            email="admin@qora.ai",
            hashed_password=hash_password("admin123"),
            full_name="Qora Admin",
            role="admin",
            headline="Platform administrator",
            avatar_color=AVATAR["admin"],
        )
        db.add(admin)

        providers = {}
        for email, name, key, headline, bio in PROVIDERS:
            u = User(
                email=email,
                hashed_password=hash_password("provider123"),
                full_name=name,
                role="provider",
                headline=headline,
                bio=bio,
                avatar_color=AVATAR[key],
            )
            db.add(u)
            providers[email] = u

        consumers = {}
        for email, name, key, headline in CONSUMERS:
            u = User(
                email=email,
                hashed_password=hash_password("consumer123"),
                full_name=name,
                role="consumer",
                headline=headline,
                avatar_color=AVATAR[key],
            )
            db.add(u)
            consumers[email] = u
        db.flush()

        wallets = {}
        for u in [admin, *providers.values(), *consumers.values()]:
            w = Wallet(user_id=u.id, balance_cents=0)
            db.add(w)
            wallets[u.id] = w
        db.flush()

        # Fund demo wallets
        for u, amount in [(consumers["omar@qora.ai"], 800000), (consumers["emma@qora.ai"], 700000),
                          (providers["sarah@qora.ai"], 250000), (providers["marcus@qora.ai"], 180000),
                          (providers["lena@qora.ai"], 150000)]:
            wallets[u.id].balance_cents = amount
            db.add(Transaction(wallet_id=wallets[u.id].id, kind="topup", amount_cents=amount,
                               description="Wallet top-up (test payment)"))

        services = []
        for title, desc, price, days, cat_slug, p_email, tags in SERVICES:
            slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-")
            s = Service(
                title=title,
                slug=slug,
                description=desc,
                price_cents=price * 100,
                delivery_days=days,
                tags=tags,
                category_id=cats[cat_slug].id,
                provider_id=providers[p_email].id,
                created_at=now - timedelta(days=len(services) * 2),
            )
            db.add(s)
            services.append(s)
        db.flush()

        # Reviews first (ratings appear on the landing page)
        review_data = [
            (0, "omar@qora.ai", 5, "Sarah delivered an exceptional chatbot — our ticket volume dropped 35% in the first month."),
            (1, "emma@qora.ai", 5, "The RAG setup is rock solid. Answers cite sources, which our legal team loves."),
            (2, "emma@qora.ai", 4, "Great pipeline and style tuning. Delivery took the full window but worth it."),
            (5, "omar@qora.ai", 5, "Forecasts were within 4% of actuals last quarter. The dashboard is beautifully clear."),
            (8, "emma@qora.ai", 4, "Transcription quality is excellent, even with heavy accents."),
            (9, "omar@qora.ai", 5, "Marcus automated 6 hours of daily ops work. Paid for itself in a week."),
        ]
        rating_map: dict[int, list[int]] = {}
        for idx, email, rating, comment in review_data:
            svc = services[idx]
            buyer = consumers[email]
            order = Order(
                service_id=svc.id,
                buyer_id=buyer.id,
                provider_id=svc.provider_id,
                requirements="Demo order — seeded review.",
                price_cents=svc.price_cents,
                status="completed",
                created_at=now - timedelta(days=20 + idx),
                delivered_at=now - timedelta(days=15 + idx),
            )
            db.add(order)
            db.flush()
            db.add(Review(order_id=order.id, service_id=svc.id, author_id=buyer.id,
                          rating=rating, comment=comment,
                          created_at=now - timedelta(days=14 + idx)))
            svc.orders_count += 1
            rating_map.setdefault(svc.id, []).append(rating)
            # buyer purchase (ledger consistency)
            bw = wallets[buyer.id]
            bw.balance_cents -= svc.price_cents
            db.add(Transaction(wallet_id=bw.id, kind="purchase", amount_cents=-svc.price_cents,
                               description=f"Order — {svc.title}"))
            # provider earning (90%)
            earnings = svc.price_cents * 90 // 100
            pw = wallets[svc.provider_id]
            pw.balance_cents += earnings
            db.add(Transaction(wallet_id=pw.id, kind="earning", amount_cents=earnings,
                               description=f"Earnings — order for “{svc.title}”"))

        for sid, ratings in rating_map.items():
            svc = db.get(Service, sid)
            svc.rating_avg = round(sum(ratings) / len(ratings), 2)
            svc.rating_count = len(ratings)

        # One live order
        svc = services[3]
        omar = consumers["omar@qora.ai"]
        wallets[omar.id].balance_cents -= svc.price_cents
        db.add(Transaction(wallet_id=wallets[omar.id].id, kind="purchase", amount_cents=-svc.price_cents,
                           description=f"Order — {svc.title}"))
        db.add(Order(
            service_id=svc.id, buyer_id=omar.id, provider_id=svc.provider_id,
            requirements="Detect surface defects on ceramic tiles — I can share 500 sample images.",
            price_cents=svc.price_cents, status="in_progress",
            created_at=now - timedelta(days=3),
        ))
        svc.orders_count += 1

        db.commit()
        print("Seed complete: %d categories, %d services, demo logins ready." % (len(CATEGORIES), len(SERVICES)))
    finally:
        db.close()


if __name__ == "__main__":
    seed()
