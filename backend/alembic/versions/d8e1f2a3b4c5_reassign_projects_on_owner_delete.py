"""reassign public projects to community account on owner delete

Replaces the projects.owner_id ``ON DELETE SET NULL`` behaviour, which left
ownerless ("NULL owner") projects behind when a profile was removed. Such
projects were a privilege-escalation hazard and could not be administered.

Instead, a BEFORE DELETE trigger on ``profiles`` now:
  - reassigns the deleted owner's PUBLIC projects to a fixed Community account
    (so shared/public content survives the account removal), and
  - deletes the deleted owner's PRIVATE projects (cascading to their entities,
    edges and transform runs).

The FK is also tightened to ``ON DELETE RESTRICT`` as a safety net: if the
trigger is ever absent, deleting a profile that still owns projects fails
closed rather than silently nulling ownership.

Revision ID: d8e1f2a3b4c5
Revises: b1c2d3e4f5a6
Create Date: 2026-06-04 10:00:00
"""

from alembic import op


revision = "d8e1f2a3b4c5"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

# Fixed profile that inherits ownership of public projects when their original
# owner is deleted, keeping community/public content alive after account
# removal. Distinct from the anonymous-user id (...0000) and never issued as a
# Supabase auth id, so no one can authenticate as it.
COMMUNITY_USER_ID = "00000000-0000-0000-0000-000000000001"
FK_NAME = "projects_owner_id_fkey"


def upgrade() -> None:
    # 1. Seed the Community account that inherits orphaned public projects.
    op.execute(
        f"""
        INSERT INTO profiles (id, email, display_name)
        VALUES ('{COMMUNITY_USER_ID}', 'community@localhost', 'Community')
        ON CONFLICT (id) DO NOTHING
        """
    )

    # 2. Reassignment logic: runs before a profile row is deleted, from any
    #    source (app, SQL, Supabase auth cascade).
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION reassign_projects_on_profile_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Never reassign the Community account to itself; its public
            -- projects are protected by the RESTRICT FK below instead.
            IF OLD.id = '{COMMUNITY_USER_ID}'::uuid THEN
                RETURN OLD;
            END IF;

            -- Public projects live on under the Community account.
            UPDATE projects
               SET owner_id = '{COMMUNITY_USER_ID}'::uuid
             WHERE owner_id = OLD.id
               AND is_public = true;

            -- Private projects are removed with the account (cascades to
            -- entities / edges / transform_runs / members / bookmarks).
            DELETE FROM projects
             WHERE owner_id = OLD.id
               AND is_public = false;

            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_reassign_projects_on_profile_delete ON profiles")
    op.execute(
        """
        CREATE TRIGGER trg_reassign_projects_on_profile_delete
            BEFORE DELETE ON profiles
            FOR EACH ROW
            EXECUTE FUNCTION reassign_projects_on_profile_delete()
        """
    )

    # 3. Tighten the FK: SET NULL -> RESTRICT (fail closed if the trigger is gone).
    op.execute(f"ALTER TABLE projects DROP CONSTRAINT IF EXISTS {FK_NAME}")
    op.execute(
        f"""
        ALTER TABLE projects
            ADD CONSTRAINT {FK_NAME}
            FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE RESTRICT
        """
    )


def downgrade() -> None:
    # Restore the original ON DELETE SET NULL behaviour.
    op.execute(f"ALTER TABLE projects DROP CONSTRAINT IF EXISTS {FK_NAME}")
    op.execute(
        f"""
        ALTER TABLE projects
            ADD CONSTRAINT {FK_NAME}
            FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE SET NULL
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_reassign_projects_on_profile_delete ON profiles")
    op.execute("DROP FUNCTION IF EXISTS reassign_projects_on_profile_delete()")
    # The Community profile is intentionally left in place; removing it could
    # orphan projects it has already adopted.
