"""Add synchronized full-text search for events.

Revision ID: 749a0eb08f31
Revises: 615206fdb353
"""

from alembic import op

revision = "749a0eb08f31"
down_revision = "615206fdb353"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE events_fts USING fts5(event_id UNINDEXED, text, tokenize='trigram')"
    )
    op.execute(
        "INSERT INTO events_fts(event_id, text) SELECT event_id, COALESCE(text, '') FROM events"
    )
    op.execute(
        """
        CREATE TRIGGER events_fts_insert AFTER INSERT ON events BEGIN
          INSERT INTO events_fts(event_id, text) VALUES (new.event_id, COALESCE(new.text, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_fts_update AFTER UPDATE OF text ON events BEGIN
          DELETE FROM events_fts WHERE event_id = old.event_id;
          INSERT INTO events_fts(event_id, text) VALUES (new.event_id, COALESCE(new.text, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_fts_delete AFTER DELETE ON events BEGIN
          DELETE FROM events_fts WHERE event_id = old.event_id;
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER events_fts_delete")
    op.execute("DROP TRIGGER events_fts_update")
    op.execute("DROP TRIGGER events_fts_insert")
    op.execute("DROP TABLE events_fts")
