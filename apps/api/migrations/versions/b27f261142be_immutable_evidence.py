"""Make published versions, recipe revisions, audit and usage append-only."""

from alembic import op

revision = "b27f261142be"
down_revision = "a4ba1e6b1232"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION reject_evidence_mutation() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'immutable evidence cannot be updated or deleted'; END;
    $$ LANGUAGE plpgsql""")
    for table in ["dataset_versions", "recipe_revisions", "audit_events", "usage_events"]:
        op.execute(
            f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_evidence_mutation()"
        )


def downgrade():
    for table in ["dataset_versions", "recipe_revisions", "audit_events", "usage_events"]:
        op.execute(f"DROP TRIGGER immutable_{table} ON {table}")
    op.execute("DROP FUNCTION reject_evidence_mutation()")
