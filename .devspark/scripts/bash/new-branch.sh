#!/usr/bin/env bash
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
# Unified branch-creation entry point .
# Work branches establish a safe delivery branch without scaffolding a specification.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/common.sh"

# Messages go to stderr so stdout carries only JSON.
err() { printf '%s\n' "$*" >&2; }
# Exit codes: 0 ok | 1 usage/type | 2 collision | 3 empty slug
die() { err "[new-branch] $1"; exit "$2"; }

TYPE=""
SHORT_NAME=""
NUMBER=0
JSON=false
DRY_RUN=false
ASSUME_YES=false
DESCRIPTION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type) TYPE="${2:-}"; shift 2 ;;
        --short-name) SHORT_NAME="${2:-}"; shift 2 ;;
        --number) NUMBER="${2:-0}"; shift 2 ;;
        --json) JSON=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --yes) ASSUME_YES=true; shift ;;
        --help) err "Usage: ./new-branch.sh --type <fix|work> [--short-name <slug>] [--number N] [--json] [--dry-run] [--yes] <description>"; exit 0 ;;
        *) DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1"; shift ;;
    esac
done

# Branch type is required and explicit. New work never scaffolds a full-spec or quick-spec
# bundle; existing bundles continue on their own branches.
TYPE="$(printf '%s' "$TYPE" | tr '[:upper:]' '[:lower:]')"
case "$TYPE" in
    fix|work) ;;
    *) die "type must be one of: fix, work" 1 ;;
esac

if [[ -z "$SHORT_NAME" && -z "$DESCRIPTION" ]]; then
    die "a description or --short-name is required" 1
fi

# Use the shared normalizer.
if [[ -n "$SHORT_NAME" ]]; then
    SLUG="$(clean_branch_name "$SHORT_NAME")"
else
    SLUG="$(clean_branch_name "$DESCRIPTION")"
    SLUG="$(printf '%s' "$SLUG" | tr '-' '\n' | grep -v '^$' | head -4 | tr '\n' '-' | sed 's/-$//')"
fi
[[ -n "$SLUG" ]] || die "description did not yield a usable short name" 3

REPO_ROOT="$(get_repo_root)"
HAS_GIT=false
if has_git; then HAS_GIT=true; fi
if [[ "$TYPE" == "work" && "$HAS_GIT" != true ]]; then
    die "work branches require a Git repository" 1
fi

# Derive the global index unless --number overrides it.
if [[ "$((10#${NUMBER}))" -le 0 ]]; then
    NUMBER="$(get_next_unified_index)"
fi

# Guard against index collisions.
if [[ "$(test_index_collision "$NUMBER" "$REPO_ROOT")" == "true" ]]; then
    die "index $(printf '%03d' "$((10#$NUMBER))") is already in use by an existing branch or spec directory - recompute" 2
fi

FEATURE_NUM="$(printf '%03d' "$((10#$NUMBER))")"
BRANCH_NAME="${FEATURE_NUM}-${TYPE}-${SLUG}"

# 244-byte limit.
if [[ "${#BRANCH_NAME}" -gt 244 ]]; then
    keep=$(( 244 - ${#FEATURE_NUM} - ${#TYPE} - 2 ))
    SLUG="$(printf '%s' "$SLUG" | cut -c1-"$keep" | sed 's/-$//')"
    BRANCH_NAME="${FEATURE_NUM}-${TYPE}-${SLUG}"
    err "[new-branch] branch name truncated to 244 bytes: $BRANCH_NAME"
fi

# The composed name must be a valid Git ref.
if [[ "$HAS_GIT" == true ]]; then
    if ! git check-ref-format --branch "$BRANCH_NAME" >/dev/null 2>&1; then
        die "composed branch name is not a valid git ref: $BRANCH_NAME" 1
    fi
fi

# Artifact destination by type .
SPECS_DIR="$REPO_ROOT/.devspark.work/specs"
QF_DIR="$REPO_ROOT/.devspark.work/quickfixes"
case "$TYPE" in
    fix)   ARTIFACT_PATH="$QF_DIR/$BRANCH_NAME.md" ;;
    work)  ARTIFACT_PATH="$SPECS_DIR/$BRANCH_NAME/work.md" ;;
esac

SWITCHED=false

if [[ "$DRY_RUN" == true ]]; then
    ARTIFACT_PATH=""
else
    # Confirm branch safety before moving HEAD.
    if [[ "$HAS_GIT" == true ]]; then
        CURRENT="$(get_current_branch)"
        proceed=$ASSUME_YES
        if [[ "$proceed" != true ]]; then
            if [[ -t 0 ]]; then
                err "[new-branch] Create and switch to '$BRANCH_NAME' from '$CURRENT'? (y/N)"
                read -r answer
                [[ "$answer" =~ ^([yY]|[yY][eE][sS])$ ]] && proceed=true
            else
                die "refusing to switch branches without confirmation (pass --yes in non-interactive use)" 1
            fi
        fi
        [[ "$proceed" == true ]] || die "aborted by user; no branch created" 1

        # Create offline with bounded recompute and retry.
        attempt=0
        while true; do
            if git checkout -b "$BRANCH_NAME" >/dev/null 2>&1; then SWITCHED=true; break; fi
            attempt=$((attempt + 1))
            if [[ "$attempt" -ge 3 ]]; then die "failed to create branch '$BRANCH_NAME' after $attempt attempts (it may already exist)" 2; fi
            NUMBER="$(get_next_unified_index)"
            FEATURE_NUM="$(printf '%03d' "$((10#$NUMBER))")"
            BRANCH_NAME="${FEATURE_NUM}-${TYPE}-${SLUG}"
            if [[ "$TYPE" == "fix" ]]; then ARTIFACT_PATH="$QF_DIR/$BRANCH_NAME.md"
            else ARTIFACT_PATH="$SPECS_DIR/$BRANCH_NAME/work.md"; fi
            err "[new-branch] retrying with recomputed index: $BRANCH_NAME"
        done
    else
        err "[new-branch] git not detected; scaffolding artifact without a branch"
    fi

    if [[ "$TYPE" == "fix" ]]; then
        # Minimal quickfix record with the year as metadata; a work branch scaffolds nothing.
        mkdir -p "$(dirname "$ARTIFACT_PATH")"
        year="$(date +%Y)"
        printf '# Quickfix: %s\n\n**Created**: %s - **Branch**: `%s` - **Year**: %s\n' \
            "$SLUG" "$(date +%Y-%m-%d)" "$BRANCH_NAME" "$year" > "$ARTIFACT_PATH"
    fi
fi

# Emit the JSON contract to stdout only.
if [[ "$JSON" == true ]]; then
    printf '{"BRANCH_NAME":"%s","NUMBER":"%s","TYPE":"%s","ARTIFACT_PATH":"%s","HAS_GIT":%s,"SWITCHED":%s}\n' \
        "$BRANCH_NAME" "$FEATURE_NUM" "$TYPE" "$ARTIFACT_PATH" "$HAS_GIT" "$SWITCHED"
else
    printf 'BRANCH_NAME: %s\nNUMBER: %s\nTYPE: %s\nARTIFACT_PATH: %s\nSWITCHED: %s\n' \
        "$BRANCH_NAME" "$FEATURE_NUM" "$TYPE" "$ARTIFACT_PATH" "$SWITCHED"
fi
