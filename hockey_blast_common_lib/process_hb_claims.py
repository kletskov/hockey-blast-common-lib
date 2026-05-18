"""
Process pending HB profile claims from the sportsbook.

For each user who has claimed multiple hockey_blast human profiles,
merges the non-primary ones into the primary using merge_humans().
Stamps merged_at on processed claims so they aren't reprocessed.

Designed to run BEFORE stats aggregation in the nightly job so that
merged humans get fresh stats in the same run.
"""

import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.merge_humans import merge_humans


def get_pred_session():
    """Create a session to the sportsbook (pred) database."""
    pred_url = os.getenv("PRED_DATABASE_URL")
    if not pred_url:
        raise RuntimeError(
            "PRED_DATABASE_URL not set. "
            "Example: postgresql://foxyclaw:pass@localhost:5432/hockey_blast_sportsbook"
        )
    engine = create_engine(pred_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def process_hb_claims():
    """Find unmerged confirmed claims and merge them into primary profiles."""
    pred_session = get_pred_session()
    hb_session = create_session("boss")

    try:
        # Find confirmed non-primary claims that haven't been merged yet
        pending_merges = pred_session.execute(text("""
            SELECT c.id, c.user_id, c.hb_human_id, p.hb_human_id AS primary_human_id
            FROM pred_user_hb_claims c
            JOIN pred_user_hb_claims p
              ON p.user_id = c.user_id AND p.is_primary = true AND p.claim_status = 'confirmed'
            WHERE c.is_primary = false
              AND c.claim_status = 'confirmed'
              AND c.merged_at IS NULL
            ORDER BY c.user_id, c.id
        """)).fetchall()

        if not pending_merges:
            print("No pending HB claim merges found.", flush=True)
            return

        print(f"Found {len(pending_merges)} claim(s) to merge:", flush=True)

        for row in pending_merges:
            claim_id, user_id, secondary_id, primary_id = row
            print(
                f"  Claim {claim_id}: merging human {secondary_id} → {primary_id} "
                f"(user_id={user_id})",
                flush=True,
            )

            merge_humans(hb_session, primary_human_id=primary_id, secondary_human_id=secondary_id)

            # Stamp merged_at on the claim
            now = datetime.now(timezone.utc)
            pred_session.execute(
                text("UPDATE pred_user_hb_claims SET merged_at = :now WHERE id = :id"),
                {"now": now, "id": claim_id},
            )
            # Ensure pred_user.hb_human_id points to the primary
            pred_session.execute(
                text("UPDATE pred_users SET hb_human_id = :primary_id WHERE id = :user_id"),
                {"primary_id": primary_id, "user_id": user_id},
            )
            pred_session.commit()

            print(f"    ✓ Merged and stamped claim {claim_id}", flush=True)

        print(f"Done — processed {len(pending_merges)} merge(s).", flush=True)

    finally:
        pred_session.close()
        hb_session.close()


if __name__ == "__main__":
    process_hb_claims()
