"""Versioned catalogue, provenance, offerings and 384-dimensional evidence."""

from alembic import op
from slop.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(op.get_bind())
    op.execute(
        "CREATE INDEX evidence_lexical ON search_evidence USING gin (to_tsvector('english', text))"
    )
    op.execute(
        "CREATE INDEX evidence_semantic ON search_evidence USING hnsw (vector vector_cosine_ops)"
    )


def downgrade():
    Base.metadata.drop_all(op.get_bind())
