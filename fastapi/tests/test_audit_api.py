from datetime import UTC, datetime

from app.models.audit import AuditLog


def _row(db, action, summary, at, user_id=None, user_name="Sistema"):
    db.add(AuditLog(at=at, user_id=user_id, user_name=user_name, action=action, entity_type="x",
                    summary=summary))
    db.flush()


def _seed(db, user):
    _row(db, "cv.upload", "Subió un CV", datetime(2026, 1, 10, 12, tzinfo=UTC), user.id, user.full_name)
    _row(db, "cv.delete", "Eliminó un CV", datetime(2026, 2, 10, 12, tzinfo=UTC), user.id, user.full_name)
    _row(db, "criterion.create", "Creó el criterio Altura", datetime(2026, 3, 10, 12, tzinfo=UTC))
    _row(db, "position.update", "Editó el puesto", datetime(2026, 3, 11, 12, tzinfo=UTC))


def test_audit_requires_auth(client):
    assert client.get("/api/audit").status_code == 401


def test_audit_filters(client, db, make_user):
    user, h = make_user()
    _seed(db, user)
    db.commit()

    def get(**params):
        r = client.get("/api/audit", params=params, headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    assert get(entityType="x")["total"] == 4
    assert get(userId=user.id, entityType="x")["total"] == 2
    r = get(action="cv.", entityType="x")
    assert r["total"] == 2 and {i["action"] for i in r["items"]} == {"cv.upload", "cv.delete"}
    assert get(dateFrom="2026-02-01", dateTo="2026-03-10", entityType="x")["total"] == 2
    assert get(dateFrom="2026-03-11", entityType="x")["total"] == 1
    assert get(q="CRITERIO", entityType="x")["total"] == 1
    page = get(entityType="x", limit=1, offset=1)
    assert page["total"] == 4 and len(page["items"]) == 1
    item = get(action="criterion.create")["items"][0]
    assert set(item) == {"id", "at", "userId", "userName", "action", "entityType", "entityId", "summary",
                         "details", "ip"}
    assert client.get("/api/audit", params={"limit": 501}, headers=h).status_code == 422


def test_audit_export_csv_bom_and_logged(client, db, make_user):
    user, h = make_user()
    _seed(db, user)
    db.commit()
    r = client.get("/api/audit/export.csv", params={"action": "cv."}, headers=h)
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert text.startswith("\ufeff") and "Subió un CV" in text and "Creó el criterio" not in text
    logged = client.get("/api/audit", params={"action": "audit.export"}, headers=h).json()
    assert logged["total"] == 1
