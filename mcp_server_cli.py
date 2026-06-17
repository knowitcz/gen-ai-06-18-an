import argparse
import logging

from app.logging_config import setup_logging
from app.mcp.server import create_mcp_server

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Happy Bank MCP server for SQLite schema introspection. "
            "Supports stdio and HTTP/SSE transports."
        )
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="MCP transport mode.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP/SSE host.")
    parser.add_argument("--port", type=int, default=8001, help="HTTP/SSE port.")
    parser.add_argument(
        "--path",
        default="/mcp",
        help="HTTP/SSE endpoint path used by FastMCP.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional path to SQLite database file. Overrides auto-discovery.",
    )
    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    logger.info(
        "Starting MCP server with transport=%s host=%s port=%s path=%s",
        args.transport,
        args.host,
        args.port,
        args.path,
    )

    mcp = create_mcp_server(db_path=args.db_path)

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
        return

    mcp.run(
        transport=args.transport,
        host=args.host,
        port=args.port,
        path=args.path,
        show_banner=False,
    )


if __name__ == "__main__":
    main()
