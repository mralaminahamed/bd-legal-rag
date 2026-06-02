# Author: Al Amin Ahamed
"""Seed provisions, provision_revisions, and chunks for all registered Acts.

Each Act receives a compact statutory tree representative of its structure:
two chapters each containing three sections. Every section gets one BN
(authoritative) and one EN (reference translation) revision, each producing
one chunk with a deterministic fake 1024-dim embedding.

Embeddings are random (seeded for reproducibility) and are NOT suitable for
semantic search — run the full ingestion pipeline to get real Cohere embeddings.
The seeded corpus exists solely for dashboard display and UI smoke-testing.

Idempotent: skips any provision whose (act_id, sort_path) pair already exists.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act, Chunk, Provision, ProvisionRevision
from app.seeders.base import Seeder

_EMBED_DIM = 1024
_EFFECTIVE_FROM = date(2006, 10, 11)  # representative enactment date


@dataclass(frozen=True)
class _SectionSpec:
    """Static specification for one seeded provision.

    Attributes:
        chapter_num: Chapter number string (e.g. ``"I"``).
        chapter_title: Chapter heading.
        section_num: Section number string (e.g. ``"2"``).
        section_title: Section heading.
        text_bn: Authoritative Bengali statutory text.
        text_en: Reference English translation.
    """

    chapter_num: str
    chapter_title: str
    section_num: str
    section_title: str
    text_bn: str
    text_en: str


# ── Per-act corpus ────────────────────────────────────────────────────────────
# Realistic excerpts from the five v1.0 Acts.  The text is simplified but
# domain-accurate and bilingual.  Bengali is authoritative; English is the
# reference translation published on bdlaws.minlaw.gov.bd.

_CORPUS: dict[str, list[_SectionSpec]] = {
    "labour-act-2006": [
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="2",
            section_title="Definitions",
            text_bn=(
                "এই আইনে, প্রসঙ্গ বা বিষয়ের পরিপন্থী কিছু না থাকলে — "
                "'শ্রমিক' অর্থ এমন কোনো ব্যক্তি, যিনি মজুরি বা অন্য কোনো প্রতিদানের বিনিময়ে "
                "কোনো প্রতিষ্ঠানে কর্মরত আছেন; "
                "'মালিক' অর্থ এমন কোনো ব্যক্তি বা প্রতিষ্ঠান যার অধীনে শ্রমিক নিয়োজিত আছেন।"
            ),
            text_en=(
                "In this Act, unless the context otherwise requires — "
                "'worker' means any person employed in an establishment for hire or reward; "
                "'employer' means any person or body of persons by whom a worker is employed."
            ),
        ),
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="3",
            section_title="Application of Act",
            text_bn=(
                "এই আইন বাংলাদেশের সকল প্রতিষ্ঠানে প্রযোজ্য হইবে, যেখানে একজন বা একাধিক "
                "শ্রমিক নিয়োজিত আছেন, তবে সরকারি প্রতিষ্ঠান এবং এই আইনের তফসিলে উল্লিখিত "
                "প্রতিষ্ঠানসমূহে প্রযোজ্য হইবে না।"
            ),
            text_en=(
                "This Act shall apply to all establishments in Bangladesh in which one or more "
                "workers are employed, but shall not apply to government establishments and such "
                "other establishments as are specified in the Schedule."
            ),
        ),
        _SectionSpec(
            chapter_num="X",
            chapter_title="Weekly Holiday and Working Hours",
            section_num="103",
            section_title="Weekly holiday",
            text_bn=(
                "প্রত্যেক শ্রমিক প্রতি সপ্তাহে অন্তত একদিন সাপ্তাহিক ছুটি পাওয়ার অধিকারী। "
                "দোকান বা বাণিজ্যিক প্রতিষ্ঠানের ক্ষেত্রে ছুটির দিনটি প্রতিষ্ঠান বন্ধের দিনের "
                "সহিত সামঞ্জস্যপূর্ণ হইবে।"
            ),
            text_en=(
                "Every worker shall be entitled to one day weekly holiday per week. "
                "In the case of a shop or commercial establishment the day off shall "
                "coincide with the weekly closing day of such establishment."
            ),
        ),
        _SectionSpec(
            chapter_num="X",
            chapter_title="Weekly Holiday and Working Hours",
            section_num="100",
            section_title="Hours of work",
            text_bn=(
                "কোনো প্রাপ্তবয়স্ক শ্রমিককে কোনো দিনে আট ঘণ্টার বেশি এবং কোনো সপ্তাহে "
                "আটচল্লিশ ঘণ্টার বেশি কাজ করানো যাইবে না। ওভারটাইম কাজের ক্ষেত্রে সাধারণ "
                "মজুরির দ্বিগুণ হারে মজুরি প্রদান করিতে হইবে।"
            ),
            text_en=(
                "No adult worker shall be required to work in any establishment for more than "
                "eight hours in any day or forty-eight hours in any week. Overtime work shall "
                "be compensated at twice the ordinary rate of wages."
            ),
        ),
        _SectionSpec(
            chapter_num="XII",
            chapter_title="Leave and Holidays",
            section_num="117",
            section_title="Annual leave with wages",
            text_bn=(
                "প্রতিটি শ্রমিক প্রতি এগারো মাস কাজের বিপরীতে এক মাসের বার্ষিক ছুটি পাওয়ার "
                "অধিকারী। ছুটির মজুরি শ্রমিকের গড় মজুরি হারে প্রদেয়।"
            ),
            text_en=(
                "Every worker shall be entitled to annual leave with wages for a period of one "
                "month for every eleven months of service. Leave wages shall be payable at the "
                "average rate of wages earned by the worker."
            ),
        ),
        _SectionSpec(
            chapter_num="XII",
            chapter_title="Leave and Holidays",
            section_num="116",
            section_title="Festival holidays",
            text_bn=(
                "প্রতিটি শ্রমিক প্রতি বছর সরকার নির্ধারিত উৎসব ছুটি পাওয়ার অধিকারী। "
                "সরকার সরকারি গেজেটে বিজ্ঞপ্তি দ্বারা উৎসব ছুটির তালিকা প্রকাশ করিবে।"
            ),
            text_en=(
                "Every worker shall be entitled to festival holidays each year as declared by "
                "the government. The government shall publish the list of festival holidays "
                "by notification in the official gazette."
            ),
        ),
    ],
    "income-tax-act-2023": [
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="2",
            section_title="Definitions",
            text_bn=(
                "এই আইনে, প্রসঙ্গ বা বিষয়ের পরিপন্থী কিছু না থাকলে — "
                "'আয়বর্ষ' অর্থ ৩০ জুন তারিখে সমাপ্ত বার মাসের সময়কাল; "
                "'মোট আয়' অর্থ করযোগ্য সকল উৎস থেকে অর্জিত মোট আয়; "
                "'কর কর্তৃপক্ষ' অর্থ জাতীয় রাজস্ব বোর্ড বা তদ্দ্বারা ক্ষমতাপ্রাপ্ত যেকোনো কর্মকর্তা।"
            ),
            text_en=(
                "In this Act, unless the context otherwise requires — "
                "'income year' means a period of twelve months ending on the 30th day of June; "
                "'total income' means the total amount of income earned from all taxable sources; "
                "'tax authority' means the National Board of Revenue "
                "or any officer authorised by it."
            ),
        ),
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="3",
            section_title="Charge of income tax",
            text_bn=(
                "এই আইনের বিধান অনুযায়ী, প্রতিটি আয়বর্ষে সরকার নির্ধারিত হারে আয়কর ধার্য "
                "করা হইবে। আয়কর প্রতিটি আয়বর্ষের মোট আয়ের উপর আরোপযোগ্য।"
            ),
            text_en=(
                "In accordance with the provisions of this Act, income tax shall be charged for "
                "every income year at the rates specified by the government. Income tax is "
                "chargeable on the total income of every income year."
            ),
        ),
        _SectionSpec(
            chapter_num="II",
            chapter_title="Basis of Charge",
            section_num="10",
            section_title="Scope of total income",
            text_bn=(
                "মোট আয় নিম্নলিখিত উৎস থেকে অর্জিত আয় অন্তর্ভুক্ত করে: বেতন ও মজুরি, "
                "ব্যবসা বা পেশা থেকে আয়, সম্পত্তি থেকে আয়, মূলধন লাভ, এবং অন্যান্য উৎস।"
            ),
            text_en=(
                "Total income includes income derived from the following sources: salaries and "
                "wages, income from business or profession, income from property, capital gains, "
                "and income from other sources."
            ),
        ),
        _SectionSpec(
            chapter_num="II",
            chapter_title="Basis of Charge",
            section_num="20",
            section_title="Deductions from total income",
            text_bn=(
                "মোট আয় গণনার ক্ষেত্রে নিম্নলিখিত ব্যয় কর্তনযোগ্য: ব্যবসার প্রকৃত খরচ, "
                "বিনিয়োগ ভাতা এবং আইনে নির্ধারিত অন্যান্য ছাড়।"
            ),
            text_en=(
                "The following expenditures are deductible in computing total income: "
                "actual business expenses, investment allowances, and other deductions "
                "as specified in this Act."
            ),
        ),
        _SectionSpec(
            chapter_num="VIII",
            chapter_title="Tax Rates and Rebates",
            section_num="76",
            section_title="Tax rates for individuals",
            text_bn=(
                "স্বাভাবিক ব্যক্তির ক্ষেত্রে করমুক্ত আয়ের সীমা ৩,৫০,০০০ টাকা। "
                "করমুক্ত সীমার উপরে আয়ের ক্ষেত্রে স্তরভেদে ৫% থেকে ৩০% পর্যন্ত হারে আয়কর ধার্য হইবে।"
            ),
            text_en=(
                "The tax-exempt income threshold for individuals is BDT 350,000. "
                "Income exceeding the tax-free limit is subject to income tax at rates "
                "ranging from 5% to 30% depending on the income slab."
            ),
        ),
        _SectionSpec(
            chapter_num="VIII",
            chapter_title="Tax Rates and Rebates",
            section_num="82",
            section_title="Tax rebate on investment",
            text_bn=(
                "কোনো ব্যক্তি অনুমোদিত তহবিলে বিনিয়োগ করিলে বিনিয়োগের পরিমাণের উপর ১৫% "
                "হারে কর রেয়াত পাইবেন, তবে সর্বোচ্চ বিনিয়োগের সীমা মোট করযোগ্য আয়ের ২০%।"
            ),
            text_en=(
                "A person investing in approved funds shall be entitled to a tax rebate at the "
                "rate of 15% of the investment amount, subject to a maximum investment limit "
                "of 20% of total taxable income."
            ),
        ),
    ],
    "vat-sd-act-2012": [
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="2",
            section_title="Definitions",
            text_bn=(
                "এই আইনে, প্রসঙ্গ বা বিষয়ের পরিপন্থী কিছু না থাকলে — "
                "'মূল্য সংযোজন কর' বা 'মূসক' অর্থ এই আইনের অধীনে আরোপযোগ্য কর; "
                "'নিবন্ধিত ব্যক্তি' অর্থ এই আইনের অধীনে নিবন্ধিত কোনো সরবরাহকারী; "
                "'টার্নওভার' অর্থ কোনো নির্দিষ্ট সময়ে মোট বিক্রয়মূল্য।"
            ),
            text_en=(
                "In this Act, unless the context otherwise requires — "
                "'value added tax' or 'VAT' means the tax leviable under this Act; "
                "'registered person' means any supplier registered under this Act; "
                "'turnover' means the total value of sales in a specified period."
            ),
        ),
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="3",
            section_title="Imposition of VAT",
            text_bn=(
                "এই আইনের বিধান সাপেক্ষে, বাংলাদেশে সরবরাহকৃত পণ্য ও সেবার উপর মূল্য "
                "সংযোজন কর আরোপ করা হইবে। মূসকের হার সরকার সময়ে সময়ে নির্ধারণ করিবে।"
            ),
            text_en=(
                "Subject to the provisions of this Act, value added tax shall be imposed on "
                "goods and services supplied in Bangladesh. The rate of VAT shall be "
                "determined by the government from time to time."
            ),
        ),
        _SectionSpec(
            chapter_num="II",
            chapter_title="Registration",
            section_num="6",
            section_title="Registration requirement",
            text_bn=(
                "যেকোনো ব্যক্তি যিনি বাংলাদেশে ব্যবসায়িক কার্যক্রম পরিচালনা করেন এবং যাহার "
                "বার্ষিক টার্নওভার নির্ধারিত সীমা অতিক্রম করে, তাহাকে এই আইনের অধীনে নিবন্ধন "
                "করিতে হইবে। নিবন্ধন না করিয়া ব্যবসা পরিচালনা করিলে আইনি ব্যবস্থা গ্রহণযোগ্য।"
            ),
            text_en=(
                "Any person who conducts business activities in Bangladesh and whose annual "
                "turnover exceeds the prescribed threshold is required to register under this "
                "Act. Operating a business without registration is subject to legal action."
            ),
        ),
        _SectionSpec(
            chapter_num="II",
            chapter_title="Registration",
            section_num="7",
            section_title="Voluntary registration",
            text_bn=(
                "নির্ধারিত সীমার নিচে টার্নওভার থাকলেও যেকোনো ব্যক্তি স্বেচ্ছায় মূসক নিবন্ধন "
                "গ্রহণ করিতে পারিবেন। স্বেচ্ছামূলক নিবন্ধন গ্রহণের পর সকল বাধ্যতামূলক বিধান "
                "প্রযোজ্য হইবে।"
            ),
            text_en=(
                "Any person may voluntarily register for VAT even if their turnover falls "
                "below the prescribed threshold. Once voluntary registration is obtained, "
                "all mandatory provisions shall apply."
            ),
        ),
        _SectionSpec(
            chapter_num="V",
            chapter_title="Returns and Payments",
            section_num="64",
            section_title="Monthly VAT return",
            text_bn=(
                "প্রতিটি নিবন্ধিত ব্যক্তি প্রতি মাসে মূসক রিটার্ন দাখিল করিতে বাধ্য। রিটার্ন "
                "পরবর্তী মাসের পনেরো তারিখের মধ্যে জমা দিতে হইবে এবং প্রযোজ্য কর পরিশোধ করিতে হইবে।"
            ),
            text_en=(
                "Every registered person is required to file a monthly VAT return. The return "
                "must be submitted by the fifteenth day of the following month, along with "
                "payment of any applicable tax."
            ),
        ),
        _SectionSpec(
            chapter_num="V",
            chapter_title="Returns and Payments",
            section_num="85",
            section_title="Penalty for evasion",
            text_bn=(
                "মূসক ফাঁকি দেওয়ার ক্ষেত্রে ফাঁকির পরিমাণের সর্বোচ্চ তিনগুণ পর্যন্ত জরিমানা "
                "আরোপ করা যাইবে। পুনরাবৃত্তির ক্ষেত্রে কারাদণ্ডও প্রযোজ্য হইতে পারে।"
            ),
            text_en=(
                "In the case of VAT evasion, a penalty of up to three times the evaded amount "
                "may be imposed. In case of repetition, imprisonment may also be applicable."
            ),
        ),
    ],
    "digital-security-act-2018": [
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="2",
            section_title="Definitions",
            text_bn=(
                "এই আইনে, প্রসঙ্গ বা বিষয়ের পরিপন্থী কিছু না থাকলে — "
                "'ডিজিটাল নিরাপত্তা' অর্থ ডিজিটাল পরিকাঠামো, তথ্য ও যোগাযোগ প্রযুক্তি এবং "
                "সাইবার স্পেসের সুরক্ষা; 'সাইবার অপরাধ' অর্থ কম্পিউটার বা নেটওয়ার্ক ব্যবহার "
                "করিয়া সংঘটিত যেকোনো অপরাধ।"
            ),
            text_en=(
                "In this Act, unless the context otherwise requires — "
                "'digital security' means protection of digital infrastructure, information "
                "and communication technology, and cyberspace; 'cyber crime' means any offence "
                "committed using a computer or network."
            ),
        ),
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="3",
            section_title="Application",
            text_bn=(
                "এই আইন বাংলাদেশের সীমানার মধ্যে এবং বাইরে যেকোনো স্থানে বাংলাদেশের নাগরিক "
                "বা অবাসিক বাংলাদেশি কর্তৃক সংঘটিত সাইবার অপরাধের ক্ষেত্রে প্রযোজ্য।"
            ),
            text_en=(
                "This Act applies to cyber crimes committed by citizens or non-resident "
                "Bangladeshis both within and outside the territorial boundaries of Bangladesh."
            ),
        ),
        _SectionSpec(
            chapter_num="III",
            chapter_title="Offences and Penalties",
            section_num="14",
            section_title="Illegal access to digital system",
            text_bn=(
                "কোনো ব্যক্তি অনুমোদন ব্যতিরেকে কোনো কম্পিউটার সিস্টেম, সার্ভার বা নেটওয়ার্কে "
                "প্রবেশ করিলে তিনি অনধিক তিন বছর কারাদণ্ড বা অনধিক পাঁচ লক্ষ টাকা অর্থদণ্ড বা "
                "উভয় দণ্ডে দণ্ডিত হইবেন।"
            ),
            text_en=(
                "Any person who accesses a computer system, server or network without "
                "authorisation shall be punishable with imprisonment not exceeding three years "
                "or a fine not exceeding five lakh taka, or both."
            ),
        ),
        _SectionSpec(
            chapter_num="III",
            chapter_title="Offences and Penalties",
            section_num="17",
            section_title="Digital fraud",
            text_bn=(
                "কোনো ব্যক্তি ডিজিটাল মাধ্যম ব্যবহার করিয়া প্রতারণামূলক কার্যক্রম পরিচালনা করিলে "
                "সাত বছর পর্যন্ত কারাদণ্ড এবং পঁচিশ লক্ষ টাকা পর্যন্ত অর্থদণ্ড বিধান রহিয়াছে।"
            ),
            text_en=(
                "Any person who conducts fraudulent activities using digital means shall be "
                "subject to imprisonment of up to seven years and a fine of up to twenty-five "
                "lakh taka."
            ),
        ),
        _SectionSpec(
            chapter_num="III",
            chapter_title="Offences and Penalties",
            section_num="29",
            section_title="Publishing defamatory information",
            text_bn=(
                "কোনো ব্যক্তি যদি ওয়েবসাইট বা অন্য কোনো ডিজিটাল মাধ্যমে এমন কোনো তথ্য "
                "প্রকাশ করেন যাহা মানহানিকর, তাহা হইলে তিনি তিন বছর পর্যন্ত কারাদণ্ড বা "
                "পাঁচ লক্ষ টাকা পর্যন্ত অর্থদণ্ড বা উভয় দণ্ডে দণ্ডিত হইতে পারেন।"
            ),
            text_en=(
                "Any person who publishes defamatory information on a website or any other "
                "digital medium may be punished with imprisonment of up to three years or "
                "a fine of up to five lakh taka, or both."
            ),
        ),
        _SectionSpec(
            chapter_num="IV",
            chapter_title="Digital Security Agency",
            section_num="46",
            section_title="Establishment of Agency",
            text_bn=(
                "সরকার এই আইনের উদ্দেশ্য পূরণকল্পে ডিজিটাল নিরাপত্তা এজেন্সি প্রতিষ্ঠা করিবে। "
                "এজেন্সি সাইবার হুমকি পর্যবেক্ষণ, প্রতিরোধ ও সমন্বয়ের দায়িত্ব পালন করিবে।"
            ),
            text_en=(
                "The government shall establish the Digital Security Agency for the purposes "
                "of this Act. The Agency shall be responsible for monitoring, preventing and "
                "coordinating responses to cyber threats."
            ),
        ),
    ],
    "companies-act-1994": [
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="2",
            section_title="Definitions",
            text_bn=(
                "এই আইনে, প্রসঙ্গ বা বিষয়ের পরিপন্থী কিছু না থাকলে — "
                "'কোম্পানি' অর্থ এই আইনের অধীনে নিবন্ধিত যেকোনো কোম্পানি; "
                "'পরিচালক' অর্থ কোম্পানির পরিচালনা পর্ষদের সদস্য; "
                "'শেয়ারহোল্ডার' অর্থ কোম্পানির শেয়ারের মালিক।"
            ),
            text_en=(
                "In this Act, unless the context otherwise requires — "
                "'company' means any company incorporated under this Act; "
                "'director' means a member of the board of directors of a company; "
                "'shareholder' means a person holding shares in a company."
            ),
        ),
        _SectionSpec(
            chapter_num="I",
            chapter_title="Preliminary",
            section_num="4",
            section_title="Types of companies",
            text_bn=(
                "এই আইনের অধীনে নিম্নলিখিত ধরনের কোম্পানি গঠন করা যাইবে: "
                "শেয়ার দ্বারা সীমিত দায়ের কোম্পানি, গ্যারান্টি দ্বারা সীমিত দায়ের কোম্পানি, "
                "এবং অসীমিত দায়ের কোম্পানি।"
            ),
            text_en=(
                "The following types of companies may be formed under this Act: "
                "companies limited by shares, companies limited by guarantee, "
                "and unlimited liability companies."
            ),
        ),
        _SectionSpec(
            chapter_num="IV",
            chapter_title="Directors and Management",
            section_num="80",
            section_title="Appointment of directors",
            text_bn=(
                "একটি পাবলিক কোম্পানিতে ন্যূনতম তিনজন এবং একটি প্রাইভেট কোম্পানিতে ন্যূনতম "
                "দুইজন পরিচালক থাকিতে হইবে। পরিচালক সাধারণ সভায় শেয়ারহোল্ডারদের দ্বারা "
                "নির্বাচিত হইবেন।"
            ),
            text_en=(
                "A public company shall have a minimum of three directors and a private company "
                "a minimum of two directors. Directors shall be elected by shareholders at a "
                "general meeting."
            ),
        ),
        _SectionSpec(
            chapter_num="IV",
            chapter_title="Directors and Management",
            section_num="91",
            section_title="Duties of directors",
            text_bn=(
                "প্রতিটি পরিচালক কোম্পানির সর্বোত্তম স্বার্থে কাজ করিতে এবং যত্নসহকারে "
                "তাহার দায়িত্ব পালন করিতে বাধ্য। স্বার্থ-সংঘাতের ক্ষেত্রে পরিচালককে "
                "পর্ষদকে অবহিত করিতে হইবে।"
            ),
            text_en=(
                "Every director is obligated to act in the best interests of the company and "
                "to discharge their duties with due care and diligence. In cases of conflict "
                "of interest, the director must disclose to the board."
            ),
        ),
        _SectionSpec(
            chapter_num="VI",
            chapter_title="Meetings and Resolutions",
            section_num="81",
            section_title="Annual general meeting",
            text_bn=(
                "প্রতিটি কোম্পানি প্রতি বছর একটি বার্ষিক সাধারণ সভা আহ্বান করিবে। সভায় "
                "বার্ষিক প্রতিবেদন, আর্থিক বিবরণী এবং পরিচালক নির্বাচন বিষয়ে সিদ্ধান্ত গ্রহণ করা হইবে।"
            ),
            text_en=(
                "Every company shall convene an annual general meeting each year. The meeting "
                "shall resolve matters including the annual report, financial statements, "
                "and election of directors."
            ),
        ),
        _SectionSpec(
            chapter_num="VI",
            chapter_title="Meetings and Resolutions",
            section_num="85",
            section_title="Extraordinary general meeting",
            text_bn=(
                "পর্ষদ যেকোনো সময় অসাধারণ সাধারণ সভা আহ্বান করিতে পারিবে। এছাড়া শেয়ারহোল্ডারদের "
                "দশ শতাংশ দাবি করিলে পর্ষদ অসাধারণ সভা আহ্বান করিতে বাধ্য থাকিবে।"
            ),
            text_en=(
                "The board of directors may convene an extraordinary general meeting at any "
                "time. Additionally, the board is obligated to convene such a meeting upon "
                "the requisition of ten percent of the shareholders."
            ),
        ),
    ],
}


def _fake_embedding(rng: random.Random) -> list[float]:
    """Generate a deterministic fake 1024-dim embedding vector.

    Args:
        rng: Seeded random instance for reproducibility.

    Returns:
        list[float]: A 1024-element list of floats sampled from N(0, 1).
    """
    return [rng.gauss(0.0, 1.0) for _ in range(_EMBED_DIM)]


def _content_hash(text: str) -> str:
    """Compute SHA-256 of the given text for change-detection.

    Args:
        text: Statutory text to hash.

    Returns:
        str: Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(text.encode()).hexdigest()


class CorpusSeeder(Seeder):
    """Seed provisions, revisions, and chunks for all registered Acts.

    The statutory tree per Act:
    - Chapters (kind=``chapter``) derived from the specs.
    - Sections (kind=``section``) under each chapter.
    - One BN + one EN ``provision_revision`` per section.
    - One ``chunk`` per revision (fake embedding, no real Cohere call).

    Idempotent: skips provisions whose ``(act_id, sort_path)`` pair exists.
    """

    name = "corpus"
    depends_on = ["acts"]
    truncate_sql = [
        "TRUNCATE TABLE chunks CASCADE",
        "TRUNCATE TABLE provision_revisions CASCADE",
        "TRUNCATE TABLE provisions CASCADE",
    ]

    async def run(self, db: AsyncSession, *, count: int) -> int:  # noqa: ARG002
        """Seed the statutory corpus for every registered Act.

        Args:
            db: Active async database session.
            count: Unused — the corpus is fixed per Act.

        Returns:
            int: Total number of chunks inserted.
        """
        from sqlalchemy import select as _select  # noqa: PLC0415

        acts_result = await db.execute(_select(Act))
        acts: list[Act] = list(acts_result.scalars().all())
        if not acts:
            raise RuntimeError("acts must be seeded before corpus")

        rng = random.Random(42)  # noqa: S311
        total_chunks = 0

        for act in acts:
            specs = _CORPUS.get(act.slug)
            if not specs:
                continue

            # Group specs by chapter
            chapters: dict[str, str] = {}
            for spec in specs:
                chapters[spec.chapter_num] = spec.chapter_title

            chapter_provisions: dict[str, uuid.UUID] = {}

            for ch_num, ch_title in chapters.items():
                ch_sort = f"{ch_num:>04}"
                ch_id = uuid.uuid4()

                # Skip if already seeded (idempotent)
                existing = await db.execute(
                    select(Provision).where(
                        Provision.act_id == act.id,
                        Provision.sort_path == ch_sort,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    ch_row = existing.scalar_one()
                    chapter_provisions[ch_num] = ch_row.id
                    continue

                chapter = Provision(
                    id=ch_id,
                    act_id=act.id,
                    parent_id=None,
                    kind="chapter",
                    number=ch_num,
                    title=ch_title,
                    sort_path=ch_sort,
                )
                db.add(chapter)
                await db.flush()
                chapter_provisions[ch_num] = ch_id

            for spec in specs:
                ch_sort = f"{spec.chapter_num:>04}"
                sec_sort = f"{ch_sort}/{spec.section_num:>04}"
                ch_prov_id = chapter_provisions.get(spec.chapter_num)
                if ch_prov_id is None:
                    continue

                # Idempotent check for section
                existing_sec = await db.execute(
                    select(Provision).where(
                        Provision.act_id == act.id,
                        Provision.sort_path == sec_sort,
                    )
                )
                existing_row = existing_sec.scalar_one_or_none()
                if existing_row is not None:
                    sec_id = existing_row.id
                else:
                    sec_id = uuid.uuid4()
                    section = Provision(
                        id=sec_id,
                        act_id=act.id,
                        parent_id=ch_prov_id,
                        kind="section",
                        number=spec.section_num,
                        title=spec.section_title,
                        sort_path=sec_sort,
                    )
                    db.add(section)
                    await db.flush()

                # Derive bdlaws numeric act ID from source YAML (e.g. act-952.html → "952")
                import re as _re  # noqa: PLC0415
                _yaml_path = (
                    Path(__file__).parents[4] / "config" / "acts" / f"{act.slug}.yaml"
                )
                _act_id_match = None
                if _yaml_path.exists():
                    _yaml_text = _yaml_path.read_text()
                    _act_id_match = _re.search(r"act-(\d+)\.html", _yaml_text)
                act_yaml_id = _act_id_match.group(1) if _act_id_match else act.slug
                source_base = f"http://bdlaws.minlaw.gov.bd/act-{act_yaml_id}.html"

                for lang, text, t_status in [
                    ("bn", spec.text_bn, "authoritative"),
                    ("en", spec.text_en, "reference_translation"),
                ]:
                    # Check if revision already exists
                    from sqlalchemy import and_ as _and  # noqa: PLC0415

                    existing_rev = await db.execute(
                        select(ProvisionRevision).where(
                            _and(
                                ProvisionRevision.provision_id == sec_id,
                                ProvisionRevision.language == lang,
                            )
                        )
                    )
                    if existing_rev.scalar_one_or_none() is not None:
                        continue

                    rev_id = uuid.uuid4()
                    rev = ProvisionRevision(
                        id=rev_id,
                        provision_id=sec_id,
                        language=lang,
                        translation_status=t_status,
                        text=text,
                        effective_from=_EFFECTIVE_FROM,
                        effective_to=None,
                        amending_act_id=None,
                        content_hash=_content_hash(text),
                        source_url=source_base,
                    )
                    db.add(rev)
                    await db.flush()

                    # One chunk per revision
                    hierarchy = (
                        f"{act.full_name_en} > "
                        f"Chapter {spec.chapter_num}: {spec.chapter_title} > "
                        f"Section {spec.section_num}: {spec.section_title}"
                    )
                    chunk = Chunk(
                        id=uuid.uuid4(),
                        revision_id=rev_id,
                        provision_id=sec_id,
                        act_id=act.id,
                        chunk_index=0,
                        language=lang,
                        hierarchy_path=hierarchy,
                        content=text,
                        token_count=len(text.split()),
                        embedding=_fake_embedding(rng),
                        meta={
                            "seeded": True,
                            "act_slug": act.slug,
                            "section": spec.section_num,
                        },
                    )
                    db.add(chunk)
                    total_chunks += 1

            await db.flush()

        return total_chunks
