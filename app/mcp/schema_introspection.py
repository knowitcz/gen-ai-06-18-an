import logging
import os
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DetailLevel = Literal["minimal", "full"]


class SchemaIntrospectionError(Exception):
    """Raised when schema introspection fails."""


class TableNotFoundError(SchemaIntrospectionError):
    """Raised when a target table does not exist."""


class SchemaIntrospector:
    """Read-only schema introspection over a SQLite database file."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = self._create_engine(db_path)

    @staticmethod
    def _create_engine(db_path: Path) -> Engine:
        if not db_path.exists():
            raise SchemaIntrospectionError(f"SQLite database file was not found: {db_path}")

        logger.debug("Creating SQLite engine for schema introspection: %s", db_path)
        return create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )

    def list_tables(self, exclude_internal: bool = True) -> list[str]:
        """List available user tables in the SQLite database."""
        logger.info("Listing tables (exclude_internal=%s)", exclude_internal)
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            if exclude_internal:
                tables = [table for table in tables if not table.startswith("sqlite_")]

            tables.sort()
            logger.debug("Found %s table(s)", len(tables))
            return tables
        except Exception as exc:
            logger.error("Failed to list tables: %s", exc, exc_info=True)
            raise SchemaIntrospectionError("Failed to list database tables") from exc

    def describe_table(self, table_name: str, detail_level: DetailLevel = "minimal") -> dict[str, Any]:
        """Describe columns for a selected table using minimal or full details."""
        logger.info("Describing table '%s' with detail_level=%s", table_name, detail_level)
        try:
            resolved_table = self._resolve_table_name(table_name)
            inspector = inspect(self.engine)
            columns = inspector.get_columns(resolved_table)

            if detail_level == "minimal":
                result = {
                    "table": resolved_table,
                    "detail_level": detail_level,
                    "columns": [
                        {
                            "name": column["name"],
                            "type": str(column.get("type", "")),
                        }
                        for column in columns
                    ],
                }
                logger.debug("Minimal description prepared for table '%s'", resolved_table)
                return result

            indexed_columns, unique_columns = self._get_index_and_unique_columns(inspector, resolved_table)
            fk_map = self._build_foreign_key_map(inspector, resolved_table)
            pk_columns = set(inspector.get_pk_constraint(resolved_table).get("constrained_columns", []))

            result = {
                "table": resolved_table,
                "detail_level": detail_level,
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column.get("type", "")),
                        "nullable": bool(column.get("nullable", True)),
                        "default": column.get("default"),
                        "primary_key": column["name"] in pk_columns,
                        "foreign_keys": fk_map.get(column["name"], []),
                        "indexed": column["name"] in indexed_columns,
                        "unique": column["name"] in unique_columns,
                    }
                    for column in columns
                ],
            }
            logger.debug("Full description prepared for table '%s'", resolved_table)
            return result
        except TableNotFoundError:
            raise
        except Exception as exc:
            logger.error("Failed to describe table '%s': %s", table_name, exc, exc_info=True)
            raise SchemaIntrospectionError(f"Failed to describe table: {table_name}") from exc

    def _resolve_table_name(self, table_name: str) -> str:
        available_tables = self.list_tables(exclude_internal=False)
        normalized = table_name.lower().strip()

        for candidate in available_tables:
            if candidate.lower() == normalized:
                return candidate

        raise TableNotFoundError(f"Table was not found: {table_name}")

    @staticmethod
    def _build_foreign_key_map(inspector: Any, table_name: str) -> dict[str, list[str]]:
        fk_map: dict[str, list[str]] = {}
        for foreign_key in inspector.get_foreign_keys(table_name):
            referred_table = foreign_key.get("referred_table")
            referred_columns = foreign_key.get("referred_columns") or []
            constrained_columns = foreign_key.get("constrained_columns") or []

            for constrained, referred in zip(constrained_columns, referred_columns):
                fk_target = f"{referred_table}.{referred}" if referred_table and referred else ""
                if fk_target:
                    fk_map.setdefault(constrained, []).append(fk_target)

        return fk_map

    @staticmethod
    def _get_index_and_unique_columns(inspector: Any, table_name: str) -> tuple[set[str], set[str]]:
        indexed_columns: set[str] = set()
        unique_columns: set[str] = set()

        for index in inspector.get_indexes(table_name):
            for column_name in index.get("column_names") or []:
                if index.get("unique"):
                    unique_columns.add(column_name)
                else:
                    indexed_columns.add(column_name)

        for unique_constraint in inspector.get_unique_constraints(table_name):
            for column_name in unique_constraint.get("column_names") or []:
                unique_columns.add(column_name)

        return indexed_columns, unique_columns


def resolve_sqlite_db_path(explicit_db_path: str | None = None) -> Path:
    """Resolve the SQLite file path with sensible project defaults."""
    logger.info("Resolving SQLite database path")

    candidates: list[Path] = []

    if explicit_db_path:
        candidates.append(Path(explicit_db_path).expanduser().resolve())

    env_db_path = os.getenv("MCP_DB_PATH")
    if env_db_path:
        candidates.append(Path(env_db_path).expanduser().resolve())

    cwd = Path.cwd()
    candidates.append((cwd / "app.db").resolve())
    candidates.append((cwd / "app" / "app.db").resolve())

    project_root = Path(__file__).resolve().parents[2]
    candidates.append((project_root / "app.db").resolve())
    candidates.append((project_root / "app" / "app.db").resolve())

    for candidate in candidates:
        if candidate.exists():
            logger.info("Using SQLite database file at: %s", candidate)
            return candidate

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise SchemaIntrospectionError(
        f"Could not find SQLite database file. Checked: {searched}. "
        "Provide --db-path or set MCP_DB_PATH."
    )
