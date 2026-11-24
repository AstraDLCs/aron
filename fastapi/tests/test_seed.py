from sqlalchemy import func, select

from app import seed
from app.models.audit import AuditLog
from app.models.criteria import RecruitmentCriterion
from app.models.org import Position, Requirement, Source


def test_seed_demo_counts(db, capsys):
    assert seed.main(["--demo"], db=db) == 0
    assert db.scalar(select(func.count()).select_from(Position)) == 28
    assert db.scalar(select(func.count()).select_from(Requirement)) == 15
    assert db.scalar(select(func.sum(Requirement.quantity))) == 32
    assert db.scalar(select(func.count()).select_from(Source)) == 6
    assert db.scalar(select(func.count()).select_from(RecruitmentCriterion)) == 2
    root = db.scalar(select(Position).where(Position.parent_id.is_(None)))
    assert root.name == "Gerencia General"
    perf = db.scalar(select(Position).where(Position.name.like("Perforista%")))
    assert perf.area == "Perforación y Voladura" and perf.parent_id is not None
    row = db.scalar(select(AuditLog).where(AuditLog.action == "seed.demo"))
    assert row.user_name == "Sistema"


def test_seed_demo_state(client, db, make_user):
    seed.main(["--demo"], db=db)
    _, h = make_user()
    s = client.get("/api/state", headers=h).json()
    assert s["companyName"] == "Compañía Minera Las Bravas"
    assert len(s["positions"]) == 28 and len(s["jobNeeds"]) == 15
    assert s["kpis"]["totalVacancies"] == 32


def test_seed_refuses_non_empty(db, capsys):
    assert seed.main(["--demo"], db=db) == 0
    assert seed.main(["--demo"], db=db) == 1
    assert "La base ya tiene datos; no se cargó la demo" in capsys.readouterr().err
    assert db.scalar(select(func.count()).select_from(Position)) == 28
