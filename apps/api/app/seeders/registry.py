# Author: Al Amin Ahamed
"""Seeder registry — ordered by dependency.

Import order determines execution order.  Reverse order is used for truncation
so foreign-key constraints resolve cleanly.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from app.seeders.acts import ActsSeeder
from app.seeders.base import Seeder
from app.seeders.corpus import CorpusSeeder
from app.seeders.feedback import FeedbackSeeder
from app.seeders.ingestion_runs import IngestionRunsSeeder
from app.seeders.queries import QueriesSeeder

# Earlier entries are dependencies of later ones.
SEEDERS: list[type[Seeder]] = [
    ActsSeeder,
    CorpusSeeder,
    IngestionRunsSeeder,
    QueriesSeeder,
    FeedbackSeeder,
]

SEEDERS_BY_NAME: dict[str, type[Seeder]] = {s.name: s for s in SEEDERS}
