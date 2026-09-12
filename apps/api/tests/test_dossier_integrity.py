from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from return_agent_contracts.models import HumanReviewDossier

from .test_human_adjudication import _pending


@pytest.mark.parametrize("field,value", [
    ("order_snapshot_ref", "different-order"), ("policy_bundle_version", "different-policy"),
    ("claim_registry_version", "different-registry"), ("revision_round", 2),
])
def test_early_proposal_cannot_disagree_with_correct_final_proposal(field, value):
    dossier = _pending()[-1].model_dump(mode="json")
    dossier["proposal_history"][0][field] = value
    with pytest.raises(ValidationError):
        HumanReviewDossier.model_validate(dossier)


@pytest.mark.parametrize("change", ["event_round", "reorder", "missing", "review"] )
def test_revision_chain_is_contiguous(change):
    dossier = _pending()[-1].model_dump(mode="json")
    if change == "event_round":
        dossier["revision_events"][0]["revision_round"] = 3
    elif change == "reorder":
        dossier["revision_events"].reverse()
    elif change == "missing":
        dossier["proposal_history"].pop(0)
    else:
        dossier["review_history"][0]["reviewer_prompt_version"] = "different"
    with pytest.raises(ValidationError):
        HumanReviewDossier.model_validate(dossier)


def test_offline_downgrade_contains_executable_data_guard():
    root = Path(__file__).resolve().parents[1]
    output = StringIO()
    config = Config(str(root / "alembic.ini"), output_buffer=output)
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", "postgresql+psycopg://unused/unused")
    command.downgrade(config, "0012_human_review_dossier:0011_memory_vectors", sql=True)
    sql = output.getvalue()
    assert "DO $$ BEGIN" in sql
    assert "RAISE EXCEPTION" in sql
    assert sql.index("RAISE EXCEPTION") < sql.index("DROP COLUMN dossier_payload")
