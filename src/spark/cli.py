"""Command-line interface for Stats Spark local usage."""

import sys

from spark.cli_argument_builders import build_main_parser
from spark.cli_handlers import (
    handle_analyze,
    handle_cache,
    handle_config,
    handle_generate,
    handle_preview,
    handle_refresh,
    handle_unified,
)
from spark.logger import get_logger


def main():
    """Main CLI entry point."""
    parser = build_main_parser()

    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(0)

    logger = get_logger("spark-cli", verbose=getattr(args, "verbose", False))

    # Execute commands
    result = None
    if args.command == "unified":
        result = handle_unified(args, logger)
    elif args.command == "analyze":
        result = handle_analyze(args, logger)
    elif args.command == "generate":
        result = handle_generate(args, logger)
    elif args.command == "preview":
        result = handle_preview(args, logger)
    elif args.command == "config":
        result = handle_config(args, logger)
    elif args.command == "cache":
        result = handle_cache(args, logger)
    elif args.command == "refresh":
        result = handle_refresh(args, logger)

    if isinstance(result, int) and result != 0:
        sys.exit(result)


if __name__ == "__main__":
    main()
