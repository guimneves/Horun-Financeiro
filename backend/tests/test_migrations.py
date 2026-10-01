"""Um banco criado ANTES desta versão (sem as colunas novas) tem que ser
atualizado no lugar, sem perder dados — create_all() não altera tabelas que
já existem."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.db import session as db_session


def _old_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE project (id INTEGER PRIMARY KEY, code VARCHAR NOT NULL, name VARCHAR)')
        conn.exec_driver_sql('CREATE TABLE document (id INTEGER PRIMARY KEY, doc_type VARCHAR, storage_path VARCHAR)')
        conn.exec_driver_sql(
            "CREATE TABLE purchaseprocess (id INTEGER PRIMARY KEY, project_id INTEGER, process_number VARCHAR, title VARCHAR)"
        )
        conn.exec_driver_sql("INSERT INTO project VALUES (1, '25.465', 'Maturação')")
        conn.exec_driver_sql("INSERT INTO document VALUES (1, 'cotacao', 'projects/1/a.pdf')")
        conn.exec_driver_sql("INSERT INTO purchaseprocess VALUES (1, 1, '2024-1', 'Antigo')")
    return engine


def test_old_database_gets_new_columns_and_keeps_its_data(tmp_path, monkeypatch):
    engine = _old_database(tmp_path)
    monkeypatch.setattr(db_session, "engine", engine)

    db_session._run_migrations()

    inspector = inspect(engine)
    assert {"drive_folder", "balance_policy"} <= {c["name"] for c in inspector.get_columns("project")}
    assert {"storage_kind", "sha256"} <= {c["name"] for c in inspector.get_columns("document")}
    assert {"origin", "drive_rel_path"} <= {c["name"] for c in inspector.get_columns("purchaseprocess")}
    assert "uq_process_project_number" in {i["name"] for i in inspector.get_indexes("purchaseprocess")}

    with engine.connect() as conn:
        # linhas antigas ganham os valores padrão certos
        assert conn.execute(text("SELECT balance_policy FROM project")).scalar() == "bloquear"
        assert conn.execute(text("SELECT storage_kind FROM document")).scalar() == "upload"
        assert conn.execute(text("SELECT origin, title FROM purchaseprocess")).one() == ("manual", "Antigo")


def test_migrations_are_idempotent(tmp_path, monkeypatch):
    engine = _old_database(tmp_path)
    monkeypatch.setattr(db_session, "engine", engine)
    db_session._run_migrations()
    db_session._run_migrations()  # rodar de novo não pode falhar


def test_duplicate_process_numbers_in_an_old_database_do_not_stop_startup(tmp_path, monkeypatch):
    engine = _old_database(tmp_path)
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO purchaseprocess VALUES (2, 1, '2024-1', 'Duplicado')")
    monkeypatch.setattr(db_session, "engine", engine)

    db_session._run_migrations()  # o índice único não pode ser criado, mas isso não derruba o módulo

    assert "uq_process_project_number" not in {i["name"] for i in inspect(engine).get_indexes("purchaseprocess")}
    assert "origin" in {c["name"] for c in inspect(engine).get_columns("purchaseprocess")}
