"""Seed the QORA platform with the Phase-1 demo dataset.

Demo story (PHASING.md Phase-1 exit criteria):
Emma (consumer) says "Next week I have an English interview for a Product Manager position" →
structured intent → Interview Coach service (she follows it) → career-context permission →
mock interview runs → outcome SUCCESS → goal memory saved → journey started.

Run:  python seed.py
"""
import sys

sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.modules.identity.models import Device, SessionRecord, User
from app.modules.intent.models import Capability, Intent, IntentCapability
from app.modules.outcome.models import OutcomeRecord
from app.modules.permission.models import ContextGrant
from app.modules.personal_qora.models import Goal, Journey, Memory
from app.modules.profile.models import CreatorProfile, PrivateProfile
from app.modules.reputation.models import TrustScore
from app.modules.reward.models import RewardAccount
from app.modules.runtime.models import ServiceSession
from app.modules.service.models import (
    AiService,
    FollowedService,
    ServiceCapabilityMap,
    ServiceIntentMap,
    ServiceVersion,
)

INTENTS = [
    ("job_interview_preparation", "Job Interview Preparation", "Prepare for interviews: practice, feedback, role-specific coaching"),
    ("english_speaking_practice", "English Speaking Practice", "Practice spoken English with feedback"),
    ("trip_planning", "Trip Planning", "Build itineraries and travel plans"),
    ("startup_idea_validation", "Startup Idea Validation", "Stress-test a business idea before building"),
    ("writing_editing", "Writing & Editing", "Improve texts, proofreading, tone"),
    ("learning_tutoring", "Learning & Tutoring", "Explanations, study plans, practice questions"),
]

CAPABILITIES = [
    ("interview_coaching", "Interview Coaching"),
    ("feedback", "Feedback"),
    ("role_specific_prep", "Role-specific Prep"),
    ("english_practice", "English Practice"),
    ("conversation", "Conversation"),
    ("itinerary_planning", "Itinerary Planning"),
    ("recommendation", "Recommendation"),
    ("idea_critique", "Idea Critique"),
    ("market_analysis", "Market Analysis"),
    ("text_improvement", "Text Improvement"),
    ("proofreading", "Proofreading"),
    ("explanation", "Explanation"),
    ("practice_questions", "Practice Questions"),
]

INTENT_CAPS = {
    "job_interview_preparation": ["interview_coaching", "feedback", "role_specific_prep"],
    "english_speaking_practice": ["english_practice", "conversation", "feedback"],
    "trip_planning": ["itinerary_planning", "recommendation"],
    "startup_idea_validation": ["idea_critique", "market_analysis"],
    "writing_editing": ["text_improvement", "proofreading"],
    "learning_tutoring": ["explanation", "practice_questions"],
}

SERVICES = [
    {
        "name": "Interview Coach",
        "slug": "interview-coach",
        "summary": "Role-specific mock interviews with structured STAR feedback",
        "description": "A personal interview coach that runs realistic mock interviews tailored to your target role, "
        "scores your answers (structure, relevance, clarity) and gives an improvement checklist. "
        "It uses your career context only when you allow it.",
        "purpose": "Help candidates walk into interviews prepared and confident",
        "audience": "Job seekers preparing for English interviews",
        "category": "career",
        "risk_level": "MEDIUM",
        "creator_name": "Sarah Chen",
        "creator_headline": "Senior career coach · ex-tech recruiter",
        "intents": ["job_interview_preparation", "english_speaking_practice"],
        "caps": ["interview_coaching", "feedback", "role_specific_prep", "english_practice"],
        "context_requirements": ["career"],
        "outcome_definition": {
            "text": "A completed practice round with role-specific feedback and an improvement checklist",
            "signals": ["relevant_interaction", "deliverable_generated", "plan_produced"],
        },
        "system": "You are Interview Coach. Run a mock interview one question at a time, then give STAR-based feedback. "
        "Always end with a short improvement checklist. Stay strictly inside interview preparation.",
        "boundaries": "No medical, legal or financial advice. No guaranteeing job offers.",
    },
    {
        "name": "Trip Planner",
        "slug": "trip-planner",
        "summary": "Usable itineraries covering dates, budget and priorities",
        "description": "Turns your dates, budget and priorities into a day-by-day itinerary you can actually follow.",
        "purpose": "Reduce trip-planning effort to minutes",
        "audience": "Travelers who want a concrete plan",
        "category": "travel",
        "risk_level": "LOW",
        "creator_name": "Marcus Webb",
        "creator_headline": "Travel designer · 40+ countries",
        "intents": ["trip_planning"],
        "caps": ["itinerary_planning", "recommendation"],
        "context_requirements": ["travel"],
        "outcome_definition": {
            "text": "A usable itinerary covering dates, budget and priorities [PRD example]",
            "signals": ["relevant_interaction", "deliverable_generated"],
        },
        "system": "You are Trip Planner. Produce a day-by-day itinerary covering dates, budget and priorities.",
        "boundaries": "No visa/legal advice. Prices are estimates.",
    },
    {
        "name": "Startup Idea Validator",
        "slug": "startup-idea-validator",
        "summary": "Stress-test your idea with a validation checklist",
        "description": "Guides you through problem, solution test and market comparison, then generates a "
        "validation checklist with pass/fail criteria.",
        "purpose": "Help founders validate before they build",
        "audience": "Early-stage founders",
        "category": "business",
        "risk_level": "LOW",
        "creator_name": "Lena Novak",
        "creator_headline": "Product strategist · 3x founder",
        "intents": ["startup_idea_validation"],
        "caps": ["idea_critique", "market_analysis"],
        "context_requirements": [],
        "outcome_definition": {
            "text": "A validation checklist with pass/fail criteria for the next 2 weeks",
            "signals": ["relevant_interaction", "deliverable_generated", "plan_produced"],
        },
        "system": "You are Startup Idea Validator. Challenge assumptions politely; end with a checklist.",
        "boundaries": "No investment advice.",
    },
    {
        "name": "Writing Editor",
        "slug": "writing-editor",
        "summary": "Clearer, sharper text with rationale for every change",
        "description": "Edits your drafts for grammar, flow and tone, with a rationale for the biggest changes.",
        "purpose": "Make everyday writing professional",
        "audience": "Anyone writing in English",
        "category": "writing",
        "risk_level": "LOW",
        "creator_name": "Sarah Chen",
        "creator_headline": "Senior career coach · ex-tech recruiter",
        "intents": ["writing_editing"],
        "caps": ["text_improvement", "proofreading"],
        "context_requirements": [],
        "outcome_definition": {
            "text": "A revised text plus a change rationale",
            "signals": ["relevant_interaction", "deliverable_generated"],
        },
        "system": "You are Writing Editor. Return revised text + rationale. Preserve the author's voice.",
        "boundaries": "No academic dishonesty (no writing exams for users).",
    },
]


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ---- users ----
        emma = User(email="emma@qora.ai", password_hash=hash_password("consumer123"), roles="consumer")
        omar = User(email="omar@qora.ai", password_hash=hash_password("consumer123"), roles="consumer")
        sarah = User(email="sarah@qora.ai", password_hash=hash_password("provider123"), roles="consumer,creator")
        marcus = User(email="marcus@qora.ai", password_hash=hash_password("provider123"), roles="consumer,creator")
        lena = User(email="lena@qora.ai", password_hash=hash_password("provider123"), roles="consumer,creator")
        admin = User(email="admin@qora.ai", password_hash=hash_password("admin123"), roles="consumer,creator,admin")
        db.add_all([emma, omar, sarah, marcus, lena, admin])
        db.flush()

        priv = {
            emma.id: "Emma Larsson", omar.id: "Omar Farouk", sarah.id: "Sarah Chen",
            marcus.id: "Marcus Webb", lena.id: "Lena Novak", admin.id: "Qora Admin",
        }
        for uid, name in priv.items():
            db.add(PrivateProfile(user_id=uid, display_name=name))

        creators = {}
        for u, name, headline, tags, trust in [
            (sarah, "Sarah Chen", "Senior career coach · ex-tech recruiter", ["career", "coaching", "writing"], 0.82),
            (marcus, "Marcus Webb", "Travel designer · 40+ countries", ["travel", "planning"], 0.74),
            (lena, "Lena Novak", "Product strategist · 3x founder", ["startup", "product"], 0.78),
        ]:
            cp = CreatorProfile(user_id=u.id, display_name=name, headline=headline, expertise_tags=tags,
                                bio="Verified specialist on QORA.", verification_status="verified", trust_score=trust)
            db.add(cp)
            creators[name] = cp
        db.flush()

        # ---- intents & capabilities ----
        intents = {}
        for slug, name, desc in INTENTS:
            i = Intent(slug=slug, name=name, description=desc)
            db.add(i)
            intents[slug] = i
        caps = {}
        for slug, name in CAPABILITIES:
            c = Capability(slug=slug, name=name)
            db.add(c)
            caps[slug] = c
        db.flush()
        for islug, cslugs in INTENT_CAPS.items():
            for cs in cslugs:
                db.add(IntentCapability(intent_id=intents[islug].id, capability_id=caps[cs].id))

        # ---- services + versions ----
        services = {}
        for s in SERVICES:
            svc = AiService(
                creator_id=creators[s["creator_name"]].id,
                slug=s["slug"], name=s["name"], summary=s["summary"], description=s["description"],
                purpose=s["purpose"], audience=s["audience"], category=s["category"],
                risk_level=s["risk_level"], visibility="public", lifecycle_status="published",
                verification_status="verified",
                published_at=datetime.now(timezone.utc) - timedelta(days=12),
            )
            db.add(svc)
            db.flush()
            v = ServiceVersion(
                service_id=svc.id, version_no=1,
                purpose=s["purpose"], method="guided conversation + structured feedback",
                behavior="friendly, concrete, stays inside boundaries",
                system_instructions=s["system"], boundaries=s["boundaries"],
                outcome_definition=s["outcome_definition"],
                model_requirements={"reasoning": "medium", "structured_output": True, "tool_calling": False},
                context_requirements=s["context_requirements"],
                examples=[{"input": "Help me prep for a PM interview", "output": "starts a mock interview"}],
            )
            db.add(v)
            db.flush()
            svc.current_version_id = v.id
            for isl in s["intents"]:
                db.add(ServiceIntentMap(service_id=svc.id, intent_id=intents[isl].id, relevance=0.9))
            for cs in s["caps"]:
                db.add(ServiceCapabilityMap(service_id=svc.id, capability_id=caps[cs].id))
            db.add(TrustScore(subject_type="service", subject_id=svc.id, overall=creators[s["creator_name"]].trust_score,
                              components={"reliability": 0.8, "quality": 0.8, "safety": 0.9, "freshness": 0.9}))
            services[s["slug"]] = svc

        # ---- Emma's personal QORA ----
        db.add(Memory(user_id=emma.id, kind="profile_fact", subject="Role", content="Product Manager at a retail startup",
                      source="user", sensitivity="private", share_policy="ask"))
        db.add(Memory(user_id=emma.id, kind="preference", subject="Answer style", content="Prefers short, structured answers",
                      source="inferred", sensitivity="private", share_policy="allow"))
        db.add(Goal(user_id=emma.id, title="Land a PM role", description="Interview prep for English PM positions"))
        db.add(Journey(user_id=emma.id, kind="job_interview_preparation", state={"step": "not_started"}, history=[]))

        # follow = add to personal toolkit [PRD]
        db.add(FollowedService(user_id=emma.id, service_id=services["interview-coach"].id))
        db.add(FollowedService(user_id=emma.id, service_id=services["trip-planner"].id))

        # pre-granted career permission for the followed coach (demo of ALLOW_ONCE consumed later)
        db.add(ContextGrant(user_id=emma.id, service_id=services["trip-planner"].id,
                            context_type="travel", scope="*", mode="ALWAYS_ALLOW"))

        for u in (emma, omar, sarah, marcus, lena, admin):
            db.add(RewardAccount(user_id=u.id, balance_units=0))

        db.commit()
        print("QORA platform seed complete: %d users, %d services, intents+capabilities linked." % (6, len(SERVICES)))
    finally:
        db.close()


if __name__ == "__main__":
    seed()
