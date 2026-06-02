"""Generate eval records from the live corpus using Ollama.

Reads real provision text from the DB, generates factual questions in both
Bengali and English, and writes them to a JSONL file suitable for the harness.
Also appends a fixed pool of advice-seeking and out-of-scope records.

Usage:
    cd apps/api
    uv run python -m eval.generate_dataset [--output eval/dataset/generated.jsonl] [--limit 10]

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

import httpx
from app.config import get_settings
from app.db.engine import get_sessionmaker
from app.db.models import Act
from sqlalchemy import select, text

# ── Config ────────────────────────────────────────────────────────────────────

_DEFAULT_OUTPUT = Path(__file__).parent / "dataset" / "generated.jsonl"
_OLLAMA_MODEL = "gemma4:e2b"

# ── Fixed advice-seeking and out-of-scope pools ───────────────────────────────

_ADVICE_SEEKING: list[dict[str, object]] = [
    {"language": "en", "question": "Should I register my company as private limited?"},
    {"language": "en", "question": "Is it legal for me to operate without VAT registration?"},
    {"language": "en", "question": "What should I do if my employer doesn't pay overtime?"},
    {"language": "en", "question": "Can I sue my employer for wrongful termination?"},
    {"language": "en", "question": "Am I allowed to work more than 48 hours a week?"},
    {"language": "en", "question": "Should I appeal against a tax assessment?"},
    {"language": "en", "question": "How do I avoid paying income tax legally?"},
    {"language": "en", "question": "Is it legal for me to share company data with competitors?"},
    {"language": "en", "question": "What should I do if I receive a VAT notice?"},
    {"language": "en", "question": "Am I required to pay for my employee's overtime?"},
    {"language": "bn", "question": "আমার কি কোম্পানি নিবন্ধন করা উচিত?"},
    {"language": "bn", "question": "আমি কি মূসক নিবন্ধন ছাড়া ব্যবসা করতে পারব?"},
    {"language": "bn", "question": "আমার কর্মচারীকে ছাঁটাই করা কি ঠিক হবে?"},
    {"language": "bn", "question": "আমার কি করা উচিত যদি মালিক মজুরি না দেয়?"},
    {"language": "bn", "question": "আমি কি আমার কর কমাতে পারব?"},
]

_OUT_OF_SCOPE: list[dict[str, object]] = [
    {"language": "en", "question": "What is the current interest rate of Bangladesh Bank?"},
    {"language": "en", "question": "How do I file a case in the High Court?"},
    {"language": "en", "question": "Who is the current Chief Justice of Bangladesh?"},
    {"language": "en", "question": "What are the visa requirements for travelling to Bangladesh?"},
    {"language": "en", "question": "How do I register a trademark in Bangladesh?"},
    {"language": "en", "question": "What is the minimum wage in garment factories?"},
    {"language": "en", "question": "Can you draft an NDA for me?"},
    {"language": "en", "question": "What does Indian company law say about directors?"},
    {"language": "en", "question": "What is the exchange rate of USD to BDT today?"},
    {"language": "en", "question": "What is the population of Dhaka?"},
    {"language": "bn", "question": "বাংলাদেশ ব্যাংকের বর্তমান সুদের হার কত?"},
    {"language": "bn", "question": "হাইকোর্টে মামলা করার পদ্ধতি কী?"},
    {"language": "bn", "question": "ট্রেডমার্ক কীভাবে নিবন্ধন করব?"},
    {"language": "bn", "question": "আমার জমির দলিল কীভাবে রেজিস্ট্রি করব?"},
    {"language": "bn", "question": "ঢাকার বর্তমান জনসংখ্যা কত?"},
]


# ── Ollama helper ─────────────────────────────────────────────────────────────

async def _ask_ollama(prompt: str, settings_obj: object) -> str:
    """Send a generation request to Ollama and return the response text."""
    base_url: str = getattr(settings_obj, "ollama_base_url", "http://localhost:11434")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/api/generate",
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return str(resp.json().get("response", "")).strip()


# ── Question generation ───────────────────────────────────────────────────────

_EN_PROMPT = """\
You are a legal test-case generator. Given this statutory provision, write ONE concise
factual question in English that can be answered ONLY from this text. The question should
be specific (mention the Act name or section topic). Return ONLY the question, nothing else.

Provision ({section}):
{text}

Question:"""

_BN_PROMPT = """\
আপনি একজন আইনি পরীক্ষার প্রশ্ন তৈরিকারী। নিচের বিধান পড়ে একটি সংক্ষিপ্ত তথ্যমূলক প্রশ্ন
বাংলায় লিখুন যার উত্তর শুধুমাত্র এই বিধান থেকে দেওয়া সম্ভব। শুধু প্রশ্নটি লিখুন।

বিধান ({section}):
{text}

প্রশ্ন:"""

_REF_EN_PROMPT = """\
Given this statutory provision, write a ONE-sentence factual summary in English of what
it says. Be concise. Return ONLY the summary sentence.

Provision:
{text}

Summary:"""

_REF_BN_PROMPT = """\
নিচের বিধানটি পড়ে একটি বাক্যে বাংলায় সারসংক্ষেপ লিখুন। শুধু সারসংক্ষেপটি লিখুন।

বিধান:
{text}

সারসংক্ষেপ:"""


def _extract_section_number(hierarchy_path: str) -> str | None:
    """Parse section number from a hierarchy_path string."""
    m = re.search(r"\bSection\s+(\w+)", hierarchy_path, re.IGNORECASE)
    return m.group(1) if m else None


# ── Main generator ────────────────────────────────────────────────────────────

async def generate(output: Path, limit_per_act: int) -> None:
    """Generate eval records and write to output JSONL.

    Args:
        output: Destination JSONL file path.
        limit_per_act: Maximum EN chunks to sample per Act (BN = same count).
    """
    settings_obj = get_settings()
    factory = get_sessionmaker()

    print(f"Connecting to DB and sampling chunks (limit={limit_per_act} per act)...")

    records: list[dict[str, object]] = []

    async with factory() as db:
        acts_result = await db.execute(select(Act))
        acts = list(acts_result.scalars().all())
        print(f"Found {len(acts)} registered Acts")

        for act in acts:
            print(f"\n  Act: {act.short_name}")
            for lang in ("en", "bn"):
                # Sample up to limit_per_act chunks with a section in hierarchy_path
                sql = text(
                    """
                    SELECT c.id, c.content, c.hierarchy_path
                    FROM chunks c
                    WHERE c.act_id = :act_id
                      AND c.language = :lang
                      AND c.hierarchy_path LIKE '%Section%'
                    ORDER BY random()
                    LIMIT :n
                    """
                )
                rows = (
                    await db.execute(sql, {"act_id": act.id, "lang": lang, "n": limit_per_act})
                ).mappings().all()

                for row in rows:
                    section_num = _extract_section_number(str(row["hierarchy_path"]))
                    if section_num is None:
                        continue

                    content = str(row["content"])[:800]  # keep prompts short
                    section_label = f"Section {section_num} of {act.short_name}"

                    try:
                        if lang == "en":
                            q = await _ask_ollama(
                                _EN_PROMPT.format(section=section_label, text=content),
                                settings_obj,
                            )
                            ref = await _ask_ollama(
                                _REF_EN_PROMPT.format(text=content), settings_obj
                            )
                        else:
                            q = await _ask_ollama(
                                _BN_PROMPT.format(section=section_label, text=content),
                                settings_obj,
                            )
                            ref = await _ask_ollama(
                                _REF_BN_PROMPT.format(text=content), settings_obj
                            )
                    except Exception as exc:  # noqa: BLE001
                        print(f"    Ollama error for {act.slug}/{lang}: {exc}")
                        continue

                    rec_id = (
                        f"{act.slug}-{lang}-gen-{uuid.uuid4().hex[:6]}"
                    )
                    records.append(
                        {
                            "id": rec_id,
                            "language": lang,
                            "act_slug": act.slug,
                            "question": q.strip(),
                            "expected_act": act.full_name_en,
                            "expected_section": section_num,
                            "expected_subsection": None,
                            "reference_summary": ref.strip(),
                            "must_cite": True,
                            "category": "factual",
                            "should_decline": False,
                            "as_of_date": None,
                        }
                    )
                    print(f"    [{lang}] s{section_num}: {q[:60]}…")

    # Append fixed decline pools
    for i, item in enumerate(_ADVICE_SEEKING):
        records.append(
            {
                "id": f"advice-gen-{i:03d}",
                "language": item["language"],
                "act_slug": None,
                "question": item["question"],
                "expected_act": None,
                "expected_section": None,
                "expected_subsection": None,
                "reference_summary": None,
                "must_cite": False,
                "category": "advice_seeking",
                "should_decline": True,
                "as_of_date": None,
            }
        )

    for i, item in enumerate(_OUT_OF_SCOPE):
        records.append(
            {
                "id": f"oos-gen-{i:03d}",
                "language": item["language"],
                "act_slug": None,
                "question": item["question"],
                "expected_act": None,
                "expected_section": None,
                "expected_subsection": None,
                "reference_summary": None,
                "must_cite": False,
                "category": "out_of_scope",
                "should_decline": True,
                "as_of_date": None,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    factual = sum(1 for r in records if not r["should_decline"])
    decline = sum(1 for r in records if r["should_decline"])
    print(f"\n✓ Wrote {len(records)} records to {output}")
    print(f"  factual: {factual}   decline: {decline}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate eval dataset from live corpus")
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output JSONL file (default: eval/dataset/generated.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=7,
        help="Max chunks to sample per (Act, language) pair (default: 7 → ~16×2×7=224 factual)",
    )
    args = parser.parse_args()
    asyncio.run(generate(output=args.output, limit_per_act=args.limit))
    sys.exit(0)
