# Author: Al Amin Ahamed
"""Seed realistic sample queries to populate the Dashboard metrics.

Seeds 20 queries with a representative distribution:
- 8 HIGH-confidence normal queries (EN and BN)
- 4 MEDIUM-confidence queries
- 3 LOW-confidence queries
- 3 declined queries (advice-seeking)
- 1 cached query
- 1 degraded query

Idempotent: skips any query whose ``correlation_id`` already exists.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act, Query
from app.seeders.base import Seeder

_DEFAULT_COUNT = 20


@dataclass(frozen=True)
class _QuerySpec:
    """Static specification for one seeded query.

    Attributes:
        query_text: User question text.
        detected_language: Language detected from query (``bn`` or ``en``).
        confidence_tier: Retrieval confidence (``HIGH``/``MEDIUM``/``LOW``).
        declined: Whether the query was declined.
        cached: Whether the response was cache-hit.
        degraded: Whether fail-open was used.
        act_slug: Slug of the primary Act retrieved; ``None`` for cross-act.
        response_text: Truncated response text for display.
    """

    query_text: str
    detected_language: str
    confidence_tier: str
    declined: bool
    cached: bool
    degraded: bool
    act_slug: str | None
    response_text: str


_FIXTURES: list[_QuerySpec] = [
    # High confidence — English
    _QuerySpec(
        query_text="What is the weekly holiday entitlement under the Labour Act 2006?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="labour-act-2006",
        response_text=(
            "Under Section 103 of the Bangladesh Labour Act, 2006, every worker is entitled "
            "to at least one day of weekly holiday. For shops and commercial establishments, "
            "this day must coincide with the weekly closing day of the establishment.\n\n"
            "Source: {{cite:labour-act-2006-s103}}"
        ),
    ),
    _QuerySpec(
        query_text="What are the overtime pay requirements for workers?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="labour-act-2006",
        response_text=(
            "According to Section 100 of the Labour Act 2006, no adult worker may work more "
            "than 8 hours per day or 48 hours per week. Any overtime must be compensated at "
            "twice the ordinary rate of wages."
        ),
    ),
    _QuerySpec(
        query_text=(
            "What constitutes illegal access to a digital system"
            " under the Digital Security Act?"
        ),
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="digital-security-act-2018",
        response_text=(
            "Section 14 of the Digital Security Act 2018 provides that accessing a computer "
            "system, server, or network without authorisation is punishable with imprisonment "
            "not exceeding three years or a fine not exceeding five lakh taka, or both."
        ),
    ),
    _QuerySpec(
        query_text="How many directors does a public company require?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="companies-act-1994",
        response_text=(
            "Under Section 80 of the Companies Act 1994, a public company must have a minimum "
            "of three directors, while a private company requires at least two directors. "
            "Directors are elected by shareholders at a general meeting."
        ),
    ),
    _QuerySpec(
        query_text="What is the income tax rate for individuals in Bangladesh?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="income-tax-act-2023",
        response_text=(
            "Under Section 76 of the Income Tax Act 2023, individual taxpayers enjoy a "
            "tax-free threshold of BDT 350,000. Income above this threshold is taxed at "
            "graduated rates from 5% to 30%."
        ),
    ),
    _QuerySpec(
        query_text="When must a VAT-registered person file a monthly return?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="vat-sd-act-2012",
        response_text=(
            "According to Section 64 of the VAT and SD Act 2012, every registered person "
            "must file a monthly VAT return by the 15th day of the following month, together "
            "with payment of any applicable tax."
        ),
    ),
    # High confidence — Bengali
    _QuerySpec(
        query_text="শ্রম আইনে শ্রমিকের সাপ্তাহিক ছুটির বিধান কী?",
        detected_language="bn",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="labour-act-2006",
        response_text=(
            "বাংলাদেশ শ্রম আইন ২০০৬-এর ধারা ১০৩ অনুযায়ী, প্রত্যেক শ্রমিক প্রতি সপ্তাহে "
            "অন্তত একদিন সাপ্তাহিক ছুটি পাওয়ার অধিকারী। দোকান বা বাণিজ্যিক প্রতিষ্ঠানের "
            "ক্ষেত্রে ছুটির দিনটি প্রতিষ্ঠান বন্ধের দিনের সাথে সামঞ্জস্যপূর্ণ হইবে।"
        ),
    ),
    _QuerySpec(
        query_text="ভ্যাট ফাঁকির জন্য কী শাস্তির বিধান রয়েছে?",
        detected_language="bn",
        confidence_tier="HIGH",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="vat-sd-act-2012",
        response_text=(
            "মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন ২০১২-এর ধারা ৮৫ অনুযায়ী, মূসক ফাঁকির "
            "ক্ষেত্রে ফাঁকির পরিমাণের সর্বোচ্চ তিনগুণ পর্যন্ত জরিমানা আরোপ করা যাইবে। "
            "পুনরাবৃত্তির ক্ষেত্রে কারাদণ্ডও প্রযোজ্য হইতে পারে।"
        ),
    ),
    # Medium confidence
    _QuerySpec(
        query_text="What are the penalties for digital fraud under Bangladesh law?",
        detected_language="en",
        confidence_tier="MEDIUM",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="digital-security-act-2018",
        response_text=(
            "Section 17 of the Digital Security Act 2018 provides for imprisonment up to "
            "seven years and a fine up to twenty-five lakh taka for persons who conduct "
            "fraudulent activities using digital means."
        ),
    ),
    _QuerySpec(
        query_text="What investment tax rebate is available to individual taxpayers?",
        detected_language="en",
        confidence_tier="MEDIUM",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="income-tax-act-2023",
        response_text=(
            "Under Section 82 of the Income Tax Act 2023, individuals investing in approved "
            "funds are entitled to a 15% tax rebate on the investment amount, subject to a "
            "ceiling of 20% of total taxable income."
        ),
    ),
    _QuerySpec(
        query_text="কোম্পানির পরিচালকদের দায়িত্ব কী?",
        detected_language="bn",
        confidence_tier="MEDIUM",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="companies-act-1994",
        response_text=(
            "কোম্পানি আইন ১৯৯৪-এর ধারা ৯১ অনুযায়ী, প্রতিটি পরিচালক কোম্পানির সর্বোত্তম "
            "স্বার্থে কাজ করিতে এবং যত্নসহকারে তাহার দায়িত্ব পালন করিতে বাধ্য। স্বার্থ-সংঘাতের "
            "ক্ষেত্রে পরিচালককে পর্ষদকে অবহিত করিতে হইবে।"
        ),
    ),
    _QuerySpec(
        query_text="What is voluntary VAT registration and when should it be considered?",
        detected_language="en",
        confidence_tier="MEDIUM",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="vat-sd-act-2012",
        response_text=(
            "Under Section 7 of the VAT and SD Act 2012, any person may voluntarily register "
            "for VAT even if their turnover falls below the prescribed threshold. Once "
            "voluntary registration is obtained, all mandatory VAT obligations apply."
        ),
    ),
    # Low confidence (cross-act / ambiguous)
    _QuerySpec(
        query_text="What taxes apply to a new business in Bangladesh?",
        detected_language="en",
        confidence_tier="LOW",
        declined=False,
        cached=False,
        degraded=False,
        act_slug=None,
        response_text=(
            "Multiple statutes may apply to a new business in Bangladesh: "
            "the Income Tax Act 2023 governs corporate and personal income tax; "
            "the VAT and SD Act 2012 governs value added tax on supplies; and "
            "the Companies Act 1994 governs registration and company law obligations."
        ),
    ),
    _QuerySpec(
        query_text="What are an employer's obligations when terminating a worker?",
        detected_language="en",
        confidence_tier="LOW",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="labour-act-2006",
        response_text=(
            "The Labour Act 2006 sets out various worker protections related to termination. "
            "The relevant provisions depend on the grounds and category of employment. "
            "Please review Chapters V and VI of the Act for specific termination rules."
        ),
    ),
    _QuerySpec(
        query_text="ডিজিটাল মানহানির ক্ষেত্রে কী আইনি প্রতিকার পাওয়া যায়?",
        detected_language="bn",
        confidence_tier="LOW",
        declined=False,
        cached=False,
        degraded=False,
        act_slug="digital-security-act-2018",
        response_text=(
            "ডিজিটাল নিরাপত্তা আইন ২০১৮-এর ধারা ২৯ অনুযায়ী, ডিজিটাল মানহানির জন্য তিন "
            "বছর পর্যন্ত কারাদণ্ড বা পাঁচ লক্ষ টাকা পর্যন্ত অর্থদণ্ড বা উভয় দণ্ডে দণ্ডিত "
            "হওয়ার বিধান রহিয়াছে।"
        ),
    ),
    # Declined (advice-seeking)
    _QuerySpec(
        query_text="Should I register my company as private limited or public limited?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=True,
        cached=False,
        degraded=False,
        act_slug="companies-act-1994",
        response_text="",
    ),
    _QuerySpec(
        query_text=(
            "Is it legal for me to operate without VAT registration"
            " if my turnover is small?"
        ),
        detected_language="en",
        confidence_tier="HIGH",
        declined=True,
        cached=False,
        degraded=False,
        act_slug="vat-sd-act-2012",
        response_text="",
    ),
    _QuerySpec(
        query_text="আমার কর্মচারীকে চাকরি থেকে বরখাস্ত করা কি ঠিক হবে?",
        detected_language="bn",
        confidence_tier="HIGH",
        declined=True,
        cached=False,
        degraded=False,
        act_slug="labour-act-2006",
        response_text="",
    ),
    # Cached
    _QuerySpec(
        query_text="What is the weekly holiday entitlement under the Labour Act 2006?",
        detected_language="en",
        confidence_tier="HIGH",
        declined=False,
        cached=True,
        degraded=False,
        act_slug="labour-act-2006",
        response_text=(
            "Under Section 103 of the Bangladesh Labour Act, 2006, every worker is entitled "
            "to at least one day of weekly holiday per week."
        ),
    ),
    # Degraded
    _QuerySpec(
        query_text="What are the tax obligations for freelancers in Bangladesh?",
        detected_language="en",
        confidence_tier="LOW",
        declined=False,
        cached=False,
        degraded=True,
        act_slug="income-tax-act-2023",
        response_text=(
            "[Degraded mode — AI summary unavailable] "
            "Retrieved provisions: Income Tax Act 2023, Section 3 (Charge of income tax), "
            "Section 10 (Scope of total income)."
        ),
    ),
]


class QueriesSeeder(Seeder):
    """Seed sample queries to populate the dashboard metrics table."""

    name = "queries"
    depends_on = ["corpus"]
    truncate_sql = [
        "TRUNCATE TABLE feedback CASCADE",
        "TRUNCATE TABLE queries CASCADE",
    ]

    async def run(self, db: AsyncSession, *, count: int) -> int:
        """Seed sample queries.

        Args:
            db: Active async database session.
            count: Override for number of queries to seed (0 = default 20).

        Returns:
            int: Number of queries inserted.
        """
        n = count if count > 0 else _DEFAULT_COUNT
        fixtures = _FIXTURES[:n]

        acts_result = await db.execute(select(Act))
        acts_by_slug: dict[str, uuid.UUID] = {
            a.slug: a.id for a in acts_result.scalars().all()
        }

        rng = random.Random(42)  # noqa: S311
        base_dt = datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC)
        inserted = 0

        for i, spec in enumerate(fixtures):
            corr_id = f"seed-{i:03d}-{spec.query_text[:20].replace(' ', '-').lower()}"

            existing = await db.execute(
                select(Query).where(Query.correlation_id == corr_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            act_ids: list[uuid.UUID] = []
            if spec.act_slug and spec.act_slug in acts_by_slug:
                act_ids = [acts_by_slug[spec.act_slug]]

            latency = rng.randint(340, 2800)
            tokens_in = rng.randint(600, 2000)
            tokens_out = 0 if spec.declined else rng.randint(150, 500)
            cost = Decimal("0.000001") * (tokens_in + tokens_out * 5)

            q = Query(
                id=uuid.uuid4(),
                correlation_id=corr_id,
                detected_language=spec.detected_language,
                selected_language=spec.detected_language,
                act_ids=act_ids,
                as_of_date=None,
                query_text=spec.query_text,
                retrieved_chunk_ids=[],
                rerank_top_score=(
                    None
                    if spec.declined
                    else Decimal(str(round(rng.uniform(0.55, 0.95), 4)))
                ),
                declined=spec.declined,
                decline_reason="advice_seeking" if spec.declined else None,
                confidence_tier=spec.confidence_tier,
                degraded=spec.degraded,
                response_text=spec.response_text or None,
                provider=None if spec.declined else "anthropic",
                prompt_version="v1",
                disclaimer_version="v1",
                tokens_in=tokens_in if not spec.declined else None,
                tokens_out=tokens_out if not spec.declined else None,
                cost_usd=cost if not spec.declined else None,
                cached=spec.cached,
                latency_ms=latency,
                ip_hash="seeded-" + str(i % 4),
                created_at=base_dt + timedelta(minutes=i * 23),
            )
            db.add(q)
            inserted += 1

        await db.flush()
        return inserted
