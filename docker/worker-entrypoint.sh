#!/bin/sh
# Load the GitHub token from a Docker/Compose secret file when provided, so it
# never has to appear in the container environment definition. The token value
# is never printed.
set -eu

if [ -z "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_TOKEN_FILE:-}" ]; then
    if [ -r "$GITHUB_TOKEN_FILE" ]; then
        GITHUB_TOKEN="$(tr -d '\r\n' < "$GITHUB_TOKEN_FILE")"
        export GITHUB_TOKEN
    else
        echo "ERROR: GITHUB_TOKEN_FILE is set but not readable: $GITHUB_TOKEN_FILE" >&2
        exit 1
    fi
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "ERROR: no GitHub token. Set GITHUB_TOKEN or GITHUB_TOKEN_FILE (see docker/README)." >&2
    exit 1
fi

exec "$@"
