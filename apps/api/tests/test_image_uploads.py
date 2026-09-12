from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from return_agent.app import app
from return_agent.attachments import sanitize
from return_agent.db.attachments import AttachmentRecord
from return_agent.db.case import CaseEventRecord, CaseRecord
from return_agent.db.models import Base, EvidenceRecord
from return_agent_contracts.models import OrderSnapshot
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def image_bytes(fmt="PNG", exif=None):
    output = io.BytesIO()
    image = Image.new("RGB", (30, 20), "red")
    image.save(output, format=fmt, **({"exif": exif} if exif else {}))
    return output.getvalue()


class Orders:
    def load_order_snapshot(self, order_ref):
        if order_ref not in {"ORDER-1", "ORDER-2"}:
            raise LookupError(order_ref)
        return OrderSnapshot(
            order_ref=order_ref,
            order_snapshot_ref=order_ref + "@1",
            snapshot_version=1,
            captured_at="2026-09-12T00:00:00Z",
            delivered_at="2026-09-10T00:00:00Z",
            currency="TWD",
            refundable_amount_max="450",
            already_refunded_amount="0",
            line_items=[
                {
                    "line_item_id": "LI-1",
                    "sku_ref": "SKU-1",
                    "title": "收納盒",
                    "category_ref": "HOME",
                    "quantity": 1,
                    "refundable_amount": "450",
                }
            ],
        )


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    commands = []
    monkeypatch.setattr(app.state, "session_factory", factory)
    monkeypatch.setattr(
        app.state, "provider_bundle", SimpleNamespace(case_context_provider=Orders())
    )
    monkeypatch.setattr(
        app.state,
        "agent_command_outbox",
        SimpleNamespace(enqueue=lambda session, cmd: commands.append(cmd)),
    )
    monkeypatch.setattr(app.state, "internal_service_token", "internal-test")
    monkeypatch.setenv("RETURN_AGENT_IMAGE_DIR", str(tmp_path / "images"))
    yield TestClient(app), factory, commands, tmp_path / "images"
    engine.dispose()


def upload(client, **fields):
    return client.post(
        "/attachments",
        data={"order_ref": "ORDER-1", "subject": "LI-1", **fields},
        files={"file": ("../original.png", image_bytes(), "image/png")},
    )


def create(client, refs=(), order="ORDER-1", user="demo_customer"):
    return client.post(
        "/cases",
        json={
            "order_ref": order,
            "user_ref": user,
            "initial_message": "商品有損壞",
            "attached_artifact_refs": list(refs),
        },
    )


def test_upload_bind_replay_and_internal_transport(setup):
    client, factory, commands, path = setup
    assert client.get("/attachments/options", params={"order_ref": "ORDER-1"}).json()[
        "subjects"
    ] == {"ORDER": "訂單／外包裝", "LI-1": "收納盒"}
    result = upload(client)
    assert result.status_code == 201, result.text
    image = result.json()
    assert (path / image["attachment_id"]).exists()
    assert (
        client.get(f"/attachments/{image['attachment_id']}/content").headers[
            "content-type"
        ]
        == "image/png"
    )
    response = create(client, [image["artifact_ref"]])
    assert response.status_code == 201, response.text
    case = response.json()["case_ref"]
    page = client.get(f"/cases/{case}/conversation").json()
    assert page["turns"][0]["message"] == "商品有損壞"
    assert page["turns"][0]["attachments"] == [image]
    url = f"/internal/cases/{case}/images/{image['attachment_id']}"
    assert client.get(url).status_code == 401
    assert (
        client.get(url, headers={"Authorization": "Bearer internal-test"}).status_code
        == 200
    )
    assert (
        client.get(
            url.replace(case, "OTHER"),
            headers={"Authorization": "Bearer internal-test"},
        ).status_code
        == 404
    )
    with factory() as session:
        evidence = session.get(EvidenceRecord, image["evidence_id"])
        assert "must be inspected" in evidence.extracted_summary
    assert "base64" not in json.dumps([c.model_dump(mode="json") for c in commands])
    assert len(commands) == 1


@pytest.mark.parametrize("kind", ["order", "user", "case"])
def test_attachment_cannot_be_rebound(setup, kind):
    client, factory, commands, _ = setup
    image = upload(client).json()
    if kind == "case":
        assert create(client, [image["artifact_ref"]]).status_code == 201
    rejected = create(
        client,
        [image["artifact_ref"]],
        order="ORDER-2" if kind == "order" else "ORDER-1",
        user="someone-else" if kind == "user" else "demo_customer",
    )
    assert rejected.status_code == 403
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CaseRecord)) == (
            1 if kind == "case" else 0
        )
    assert len(commands) == (1 if kind == "case" else 0)


def test_evidence_resume_requires_submission_and_does_not_double_dispatch(setup):
    client, factory, commands, _ = setup
    case = create(client).json()["case_ref"]
    assert upload(client, case_ref=case).status_code == 409
    with factory.begin() as session:
        session.get(CaseRecord, case).status = "AWAITING_EVIDENCE"
    image = upload(client, case_ref=case).json()
    url = f"/internal/cases/{case}/images/{image['attachment_id']}"
    assert (
        client.get(url, headers={"Authorization": "Bearer internal-test"}).status_code
        == 403
    )
    payload = {
        "message": "已補交圖片",
        "attached_artifact_refs": [image["artifact_ref"]],
    }
    assert client.post(f"/cases/{case}/messages", json=payload).status_code == 200
    assert client.post(f"/cases/{case}/messages", json=payload).status_code == 409
    assert len(commands) == 2
    page = client.get(f"/cases/{case}/conversation").json()
    assert len(page["turns"]) == 2
    assert page["turns"][1]["attachments"] == [image]
    assert (
        client.get(url, headers={"Authorization": "Bearer internal-test"}).status_code
        == 200
    )


@pytest.mark.parametrize(
    "fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_supported_formats_remove_exif_without_changing_orientation(fmt, mime):
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private description"
    clean, content_type, width, height = sanitize(image_bytes(fmt, exif), mime)
    assert (content_type, width, height) == (mime, 20, 30)
    with Image.open(io.BytesIO(clean)) as image:
        assert not image.getexif()
        assert b"private description" not in clean


@pytest.mark.parametrize(
    "body,mime,status",
    [
        (b"", "image/png", 422),
        (b"not an image", "image/png", 422),
        (image_bytes(), "image/jpeg", 415),
        (image_bytes("GIF"), "image/gif", 415),
        (image_bytes()[:40], "image/png", 422),
    ],
)
def test_bad_images_rejected_without_metadata_or_files(setup, body, mime, status):
    client, factory, _, path = setup
    response = client.post(
        "/attachments",
        data={"order_ref": "ORDER-1", "subject": "LI-1"},
        files={"file": ("a", body, mime)},
    )
    assert response.status_code == status
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AttachmentRecord)) == 0
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 0
    assert not path.exists()


def test_limits_subjects_missing_files_and_unconfigured_provider(setup, monkeypatch):
    client, _, _, _ = setup
    assert upload(client, subject="OTHER").status_code == 422
    assert upload(client, order_ref="OTHER").status_code == 404
    assert create(client, ["artifact://upload/" + "a" * 32]).status_code == 404
    monkeypatch.setenv("RETURN_AGENT_IMAGE_MAX_PIXELS", "10")
    assert upload(client).status_code == 413
    monkeypatch.setenv("RETURN_AGENT_IMAGE_MAX_PIXELS", "25000000")
    monkeypatch.setenv("RETURN_AGENT_IMAGE_MAX_BYTES", "10")
    assert upload(client).status_code == 413
    assert client.post("/attachments", content=b"x" * 66000).status_code == 413
    monkeypatch.setattr(app.state, "provider_bundle", None)
    assert client.get("/attachments/options?order_ref=ORDER-1").status_code == 503


def test_streamed_body_cannot_bypass_limit(setup, monkeypatch):
    client, _, _, _ = setup
    monkeypatch.setenv("RETURN_AGENT_IMAGE_MAX_BYTES", "10")
    response = client.post(
        "/attachments",
        headers={"Content-Type": "multipart/form-data; boundary=x"},
        content=iter(
            [
                b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\nContent-Type: image/png\r\n\r\n',
                b"x" * 70000,
            ]
        ),
    )
    assert response.status_code == 413


def test_duplicate_count_and_corrupted_storage(setup, monkeypatch):
    client, factory, _, path = setup
    image = upload(client).json()
    assert create(client, [image["artifact_ref"]] * 2).status_code == 422
    monkeypatch.setenv("RETURN_AGENT_IMAGE_MAX_PER_MESSAGE", "1")
    assert (
        create(client, [image["artifact_ref"], "artifact://demo/other"]).status_code
        == 422
    )
    (path / image["attachment_id"]).write_bytes(b"corrupt")
    assert (
        client.get(f"/attachments/{image['attachment_id']}/content").status_code == 503
    )
    with factory.begin() as session:
        session.get(AttachmentRecord, image["attachment_id"]).user_ref = "another-user"
    assert (
        client.get(f"/attachments/{image['attachment_id']}/content").status_code == 404
    )


def test_failed_outbox_rolls_back_attachment_binding(setup, monkeypatch):
    client, factory, _, _ = setup
    image = upload(client).json()

    def fail(*args):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(
        app.state, "agent_command_outbox", SimpleNamespace(enqueue=fail)
    )
    with pytest.raises(RuntimeError, match="outbox unavailable"):
        create(client, [image["artifact_ref"]])
    with factory() as session:
        assert session.get(AttachmentRecord, image["attachment_id"]).case_ref is None
        assert session.scalar(select(func.count()).select_from(CaseRecord)) == 0
        assert session.scalar(select(func.count()).select_from(CaseEventRecord)) == 0
