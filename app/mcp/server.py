import logging
from typing import Any, Literal

from fastmcp import FastMCP

from app.mcp.schema_introspection import (
    SchemaIntrospectionError,
    SchemaIntrospector,
    TableNotFoundError,
    resolve_sqlite_db_path,
)

logger = logging.getLogger(__name__)

DetailLevel = Literal["minimal", "full"]


def create_mcp_server(db_path: str | None = None) -> FastMCP:
    """Create an MCP server exposing SQLite schema introspection tools."""
    resolved_db_path = resolve_sqlite_db_path(db_path)
    introspector = SchemaIntrospector(resolved_db_path)

    mcp = FastMCP(
        "happy-bank-db-schema",
        instructions=(
            "Read-only SQLite schema introspection. "
            "Use list_tables to discover tables and describe_table for column metadata."
        ),
    )

    @mcp.tool(description="List available SQLite tables.")
    def list_tables(exclude_internal: bool = True) -> list[str]:
        logger.info("MCP tool call: list_tables (exclude_internal=%s)", exclude_internal)
        try:
            return introspector.list_tables(exclude_internal=exclude_internal)
        except SchemaIntrospectionError as exc:
            logger.error("list_tables failed: %s", exc, exc_info=True)
            raise ValueError(str(exc)) from exc

    @mcp.tool(
        description=(
            "Describe columns for a selected table. "
            "Use detail_level=minimal for name/type only or full for extended metadata."
        )
    )
    def describe_table(table_name: str, detail_level: DetailLevel = "minimal") -> dict[str, Any]:
        logger.info(
            "MCP tool call: describe_table (table_name=%s, detail_level=%s)",
            table_name,
            detail_level,
        )
        try:
            return introspector.describe_table(table_name=table_name, detail_level=detail_level)
        except TableNotFoundError as exc:
            logger.warning("describe_table table not found: %s", exc)
            raise ValueError(str(exc)) from exc
        except SchemaIntrospectionError as exc:
            logger.error("describe_table failed: %s", exc, exc_info=True)
            raise ValueError(str(exc)) from exc

    return mcp
