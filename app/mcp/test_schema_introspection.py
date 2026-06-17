import sqlite3
from pathlib import Path

import pytest

from app.mcp.schema_introspection import (
    SchemaIntrospectionError,
    SchemaIntrospector,
    TableNotFoundError,
)


def _create_test_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute("CREATE TABLE client (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)")
    cursor.execute(
        "CREATE TABLE account ("
        "id INTEGER PRIMARY KEY, "
        "client_id INTEGER NOT NULL, "
        "balance INTEGER DEFAULT 0, "
        "FOREIGN KEY(client_id) REFERENCES client(id)"
        ")"
    )
    cursor.execute("CREATE INDEX idx_account_balance ON account(balance)")

    connection.commit()
    connection.close()


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    _create_test_db(db_path)
    return db_path


def test_list_tables_excludes_sqlite_internal(sqlite_db: Path) -> None:
    introspector = SchemaIntrospector(sqlite_db)

    tables = introspector.list_tables(exclude_internal=True)

    assert "client" in tables
    assert "account" in tables
    assert all(not table.startswith("sqlite_") for table in tables)


def test_describe_table_minimal(sqlite_db: Path) -> None:
    introspector = SchemaIntrospector(sqlite_db)

    result = introspector.describe_table("account", detail_level="minimal")

    assert result["table"] == "account"
    assert result["detail_level"] == "minimal"
    assert {column["name"] for column in result["columns"]} == {"id", "client_id", "balance"}
    assert {"name", "type"}.issubset(result["columns"][0].keys())


def test_describe_table_full(sqlite_db: Path) -> None:
    introspector = SchemaIntrospector(sqlite_db)

    result = introspector.describe_table("account", detail_level="full")

    assert result["table"] == "account"
    assert result["detail_level"] == "full"

    by_name = {column["name"]: column for column in result["columns"]}

    assert by_name["id"]["primary_key"] is True
    assert by_name["balance"]["indexed"] is True
    assert by_name["client_id"]["foreign_keys"] == ["client.id"]


def test_describe_table_is_case_insensitive(sqlite_db: Path) -> None:
    introspector = SchemaIntrospector(sqlite_db)

    result = introspector.describe_table("AcCoUnT", detail_level="minimal")

    assert result["table"] == "account"


def test_describe_table_raises_when_missing(sqlite_db: Path) -> None:
    introspector = SchemaIntrospector(sqlite_db)

    with pytest.raises(TableNotFoundError, match="Table was not found"):
        introspector.describe_table("missing_table")


def test_introspector_raises_when_file_missing(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"

    with pytest.raises(SchemaIntrospectionError, match="was not found"):
        SchemaIntrospector(missing_db)
