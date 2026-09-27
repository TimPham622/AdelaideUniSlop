"""Allow multiple programmes in one catalogue year."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("degree_identity",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("program_code", sa.String(80), nullable=False),
        sa.Column("canonical_slug", sa.String(160), nullable=False))
    op.add_column("degree_version", sa.Column("degree_id", sa.String(80), nullable=True))
    op.execute("INSERT INTO degree_identity (id, program_code, canonical_slug) "
               "SELECT DISTINCT split_part(id, ':', 2), "
               "COALESCE(data->>'program_code', upper(split_part(id, ':', 2))), "
               "split_part(id, ':', 2) FROM degree_version")
    op.execute("UPDATE degree_version SET degree_id = split_part(id, ':', 2)")
    op.alter_column("degree_version", "degree_id", nullable=False)
    op.drop_constraint("degree_version_year_key", "degree_version", type_="unique")
    op.create_foreign_key("fk_degree_version_degree_id", "degree_version",
                          "degree_identity", ["degree_id"], ["id"])
    op.create_unique_constraint("uq_degree_version_degree_year", "degree_version",
                                ["degree_id", "year"])
    op.create_index("ix_degree_version_year", "degree_version", ["year"])


def downgrade():
    op.drop_index("ix_degree_version_year", table_name="degree_version")
    op.drop_constraint("uq_degree_version_degree_year", "degree_version", type_="unique")
    op.drop_constraint("fk_degree_version_degree_id", "degree_version", type_="foreignkey")
    op.drop_column("degree_version", "degree_id")
    op.create_unique_constraint("degree_version_year_key", "degree_version", ["year"])
    op.drop_table("degree_identity")
