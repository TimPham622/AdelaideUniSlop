"""Original catalogue schema, frozen independently of the current ORM."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table("catalogue_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("payload", JSONB(), nullable=False))
    op.create_table("source_document",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("provenance", JSONB(), nullable=False))
    op.create_table("course_identity",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("institutional_id", sa.String(80), nullable=False))
    op.create_table("course_version",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("code", sa.String(20), sa.ForeignKey("course_identity.code"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("source_document.id"), nullable=False),
        sa.Column("data", JSONB(), nullable=False),
        sa.UniqueConstraint("code", "year"))
    op.create_index("ix_course_version_year", "course_version", ["year"])
    op.create_table("degree_version",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False, unique=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("source_document.id"), nullable=False),
        sa.Column("data", JSONB(), nullable=False))
    op.create_table("course_offering",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("version_id", sa.String(40), sa.ForeignKey("course_version.id"), nullable=False),
        sa.Column("period", sa.String(80), nullable=False),
        sa.Column("data", JSONB(), nullable=False))
    op.create_index("ix_course_offering_period", "course_offering", ["period"])
    op.create_table("course_relationship",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("data", JSONB(), nullable=False))
    op.create_table("search_evidence",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("version_id", sa.String(40), sa.ForeignKey("course_version.id"), nullable=False),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("vector", Vector(384), nullable=True))
    op.create_index("ix_search_evidence_version_id", "search_evidence", ["version_id"])
    op.execute("CREATE INDEX evidence_lexical ON search_evidence USING gin (to_tsvector('english', text))")
    op.execute("CREATE INDEX evidence_semantic ON search_evidence USING hnsw (vector vector_cosine_ops)")


def downgrade():
    op.drop_index("evidence_semantic", table_name="search_evidence")
    op.drop_index("evidence_lexical", table_name="search_evidence")
    op.drop_index("ix_search_evidence_version_id", table_name="search_evidence")
    op.drop_table("search_evidence")
    op.drop_table("course_relationship")
    op.drop_index("ix_course_offering_period", table_name="course_offering")
    op.drop_table("course_offering")
    op.drop_table("degree_version")
    op.drop_index("ix_course_version_year", table_name="course_version")
    op.drop_table("course_version")
    op.drop_table("course_identity")
    op.drop_table("source_document")
    op.drop_table("catalogue_revision")
