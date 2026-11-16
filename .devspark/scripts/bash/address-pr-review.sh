#!/usr/bin/env bash
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
# Helper script for /devspark.address-pr-review
# --pr-id: parse review file and emit open findings
# --gate:  enforce staged-path isolation for code-only or review-only commits

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PR_ID=""
GATE=""
JSON_OUTPUT=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr-id)
            PR_ID="$2"
            shift 2
            ;;
        --gate)
            GATE="$2"
            shift 2
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
get_staged_paths() {
    git diff --cached --name-only 2>/dev/null || true
}

is_review_path() {
    [[ "$1" =~ ^\.devspark.work/pr-review/pr-.*\.md$ ]]
}

write_gate_failure() {
    local message="$1"
    shift
    printf 'DevSpark: %s\n' "$message" >&2
    if [[ $# -gt 0 ]]; then
        printf 'Offending staged paths:\n' >&2
        for path in "$@"; do
            printf '  - %s\n' "$path" >&2
        done
    fi
    exit 1
}

# ---------------------------------------------------------------------------
# Gate mode
# ---------------------------------------------------------------------------
if [[ -n "$GATE" ]]; then
    # bash 3.2 compatible (macOS system bash lacks mapfile/readarray).
    STAGED=()
    while IFS= read -r staged_line; do
        [[ -n "$staged_line" ]] && STAGED+=("$staged_line")
    done < <(get_staged_paths)

    if [[ "$GATE" == "code-only" ]]; then
        review_staged=()
        for p in "${STAGED[@]:-}"; do
            is_review_path "$p" && review_staged+=("$p") || true
        done
        if [[ ${#review_staged[@]} -gt 0 ]]; then
            write_gate_failure \
                "Code commit gate failed. Review files must not be staged for code-only commits." \
                "${review_staged[@]}"
        fi

    elif [[ "$GATE" == "review-only" ]]; then
        non_review_staged=()
        for p in "${STAGED[@]:-}"; do
            is_review_path "$p" || non_review_staged+=("$p")
        done
        if [[ ${#non_review_staged[@]} -gt 0 ]]; then
            write_gate_failure \
                "Review commit gate failed. Only PR review markdown files may be staged." \
                "${non_review_staged[@]}"
        fi

    else
        printf 'DevSpark: Invalid --gate value "%s". Expected code-only or review-only.\n' "$GATE" >&2
        exit 1
    fi

    "$JSON_OUTPUT" && printf '{"gate":"%s","passed":true}\n' "$GATE" || printf "Gate '%s' passed.\n" "$GATE"
    exit 0
fi

# ---------------------------------------------------------------------------
# PR findings mode
# ---------------------------------------------------------------------------
if [[ -z "$PR_ID" ]]; then
    printf 'DevSpark: Provide --pr-id <N> or --gate <code-only|review-only>.\n' >&2
    exit 1
fi

# Strip leading #
NORMALIZED="${PR_ID#\#}"
if ! [[ "$NORMALIZED" =~ ^[0-9]+$ ]]; then
    printf 'DevSpark: Invalid PR id "%s". Expected a positive integer.\n' "$PR_ID" >&2
    exit 1
fi

REPO_ROOT="$(get_repo_root)"
REVIEW_FILE="$REPO_ROOT/.devspark.work/pr-review/pr-${NORMALIZED}.md"

if [[ ! -f "$REVIEW_FILE" ]]; then
    printf 'DevSpark: Review file not found: %s\n' "$REVIEW_FILE" >&2
    exit 1
fi

STATE_ENGINE="$SCRIPT_DIR/../pr-review-state.py"
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
fi
HAS_MODERN_STATE=false
grep -Eq '^review_state[[:space:]]*:' "$REVIEW_FILE" && HAS_MODERN_STATE=true || true
PYTHON_READY=false
if [[ -n "$PYTHON" ]]; then
    if probe_output="$("$PYTHON" -c 'import yaml' 2>&1)"; then
        PYTHON_READY=true
    elif [[ "$probe_output" == *"No module named"* && "$probe_output" == *"yaml"* ]]; then
        if [[ "$HAS_MODERN_STATE" == "true" ]]; then
            printf '{"ok":false,"issues":[{"code":"missing-prerequisite","message":"Structured review inspection requires Python with PyYAML.","location":"review_state","recovery":"Install or select the existing Python/PyYAML runtime, then retry."}]}\n'
            exit 1
        fi
    else
        printf 'DevSpark: Python inspection prerequisite check failed: %s\n' "$probe_output" >&2
        exit 1
    fi
elif [[ "$HAS_MODERN_STATE" == "true" ]]; then
    printf '{"ok":false,"issues":[{"code":"missing-prerequisite","message":"Structured review inspection requires Python 3.11+ and PyYAML.","location":"review_state","recovery":"Install or select the existing Python/PyYAML runtime, then retry."}]}\n'
    exit 1
fi

if [[ "$PYTHON_READY" == "true" ]]; then
    "$PYTHON" "$STATE_ENGINE" inspect "$REVIEW_FILE" --pr-id "$NORMALIZED" --json
    exit $?
fi

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

native_error() {
    printf '{"ok":false,"issues":[{"code":"%s","message":"%s","location":"%s","recovery":"%s"}]}\n' \
        "$1" "$(json_escape "$2")" "$(json_escape "$3")" "$(json_escape "$4")"
    exit 1
}

native_section_blocking() {
    local normalized
    normalized="$(lower "$1")"
    if [[ "$normalized" == *non-blocking* || "$normalized" == *nonblocking* ||
          "$normalized" == *recommended\ improvement* || "$normalized" == *suggestion* ||
          "$normalized" == *low\ priority\ improvement* ]]; then
        printf 'false'
    elif [[ "$normalized" == *blocking* || "$normalized" == *immediate\ action* ]]; then
        printf 'true'
    fi
}

native_add() {
    local id="$1" aliases="$2" status="$3" description="$4" expected="$5"
    local section="$6" line="$7" number="$8" basis="$9"
    local blocking
    local evidence="${10:-}"
    local i alias
    blocking="$(native_section_blocking "$section")"
    for ((i=0; i<${#native_ids[@]}; i++)); do
        if [[ "${native_ids[i]}" == "$id" ]]; then
            if [[ "${native_statuses[i]}" != "$status" ]]; then
                native_error contradictory-legacy-status "Finding $id has conflicting action/table status." \
                    "line $number" "Resolve conflicting legacy status without inferring closure."
            fi
            if [[ -n "$blocking" && -n "${native_blockings[i]}" && "${native_blockings[i]}" != "$blocking" ]]; then
                native_error contradictory-legacy-blocking "Finding $id has conflicting blocking classifications." \
                    "line $number" "Use Python recover-legacy with an authorized, evidence-based interpretation."
            fi
            [[ -n "$blocking" ]] && native_blockings[i]="$blocking"
            [[ -n "$aliases" ]] && native_aliases[i]="$aliases"
            ((${#description} > ${#native_descriptions[i]})) && native_descriptions[i]="$description"
            [[ -n "$expected" ]] && native_expected[i]="$expected"
            [[ -n "$evidence" ]] && native_evidences[i]="$evidence"
            [[ "$status" == resolved && "$basis" != "checked action item" ]] && native_bases[i]="$basis"
            return 0
        fi
    done
    if [[ -n "$aliases" ]]; then
        IFS=',' read -r -a incoming <<< "$aliases"
        for alias in "${incoming[@]}"; do
            for ((i=0; i<${#native_ids[@]}; i++)); do
                [[ "${native_ids[i]}" == "$alias" ]] &&
                    native_error alias-conflict "Alias $alias conflicts with a canonical finding." "line $number" "Choose a unique canonical owner."
                [[ ",${native_aliases[i]}," == *",$alias,"* ]] &&
                    native_error alias-conflict "Alias $alias belongs to multiple findings." "line $number" "Choose the canonical finding that owns this alias."
            done
        done
    fi
    native_ids+=("$id")
    native_aliases+=("$aliases")
    native_statuses+=("$status")
    native_descriptions+=("$description")
    native_expected+=("$expected")
    native_evidences+=("$evidence")
    native_sections+=("$section")
    native_blockings+=("$blocking")
    native_lines+=("$line")
    native_numbers+=("$number")
    native_bases+=("$basis")
}

native_ids_from() {
    local value="$1" allow_alias="$2" slash_count
    mapfile -t native_parsed_ids < <(grep -oE '(CON|PRD[0-9]+|C|H|M|L)-[0-9]{2,}' <<< "$value" || true)
    ((${#native_parsed_ids[@]} > 0)) ||
        native_error malformed-finding "Finding-like entry has no supported identifier." "$3" \
            "Correct the identifier or resolve the unsupported entry."
    native_parsed_aliases=""
    if [[ "$allow_alias" == true && "$value" == *"/"* ]]; then
        slash_count=$(( $(grep -o '/' <<< "$value" | wc -l) + 1 ))
        ((${#native_parsed_ids[@]} == slash_count)) ||
            native_error malformed-finding "Combined finding identifier is malformed." "$3" \
                "Correct the explicit alias pair or resolve the entry manually."
        native_parsed_aliases="$(IFS=,; echo "${native_parsed_ids[*]:1}")"
    fi
}

if [[ "$PYTHON_READY" != "true" ]]; then
    declare -a native_ids=() native_aliases=() native_statuses=() native_descriptions=()
    declare -a native_expected=() native_evidences=() native_sections=() native_blockings=()
    declare -a native_lines=() native_numbers=() native_bases=()
    declare -a native_parsed_ids=() table_headers=()
    section=""
    in_table=false
    fenced=false
    line_num=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        line_num=$((line_num + 1))
        if [[ "$line" =~ ^[[:space:]]*\`\`\` ]]; then
            [[ "$fenced" == true ]] && fenced=false || fenced=true
            continue
        fi
        [[ "$fenced" == true ]] && continue
        if [[ "$line" =~ ^#+[[:space:]]+(.*)$ ]]; then
            section="${BASH_REMATCH[1]}"
            table_headers=()
            in_table=false
            continue
        fi
        action_re='^[[:space:]]*-[[:space:]]+\[([ xX])\][[:space:]]+\*\*([^*]+)\*\*[[:space:]]*(.*)$'
        if [[ "$line" =~ $action_re ]]; then
            checked="${BASH_REMATCH[1]}"
            label="${BASH_REMATCH[2]}"
            rest="${BASH_REMATCH[3]}"
            native_ids_from "$label" true "line $line_num"
            native_status=open
            [[ "$checked" =~ [xX] ]] && native_status=resolved
            action_basis="unchecked action item"
            [[ "$native_status" == resolved ]] && action_basis="checked action item"
            native_add "${native_parsed_ids[0]^^}" "$native_parsed_aliases" "$native_status" \
                "$rest" "" "$section" "$line" "$line_num" "$action_basis"
        fi
        if [[ "$line" == *"|"* ]]; then
            table_line="$(trim "$line")"
            table_line="${table_line#|}"
            table_line="${table_line%|}"
            IFS='|' read -r -a cells <<< "$table_line"
            for i in "${!cells[@]}"; do cells[i]="$(trim "${cells[i]}")"; done
            if ((${#table_headers[@]} == 0)) && ((${#cells[@]} > 0)); then
                header="$(lower "${cells[0]}")"
                if [[ "$header" == id || "$header" == finding || "$header" == "finding id" ]]; then
                    for cell in "${cells[@]}"; do table_headers+=("$(lower "$cell")"); done
                    in_table=true
                    continue
                fi
            fi
            if [[ "$line" =~ ^[[:space:]]*\|([[:space:]]*:?-{2,}:?[[:space:]]*\|)+[[:space:]]*$ ]]; then continue; fi
            if [[ "$in_table" == true ]] && ((${#cells[@]} >= 2)); then
                native_ids_from "${cells[0]}" true "line $line_num"
                status_cell=""
                issue=""
                fix=""
                evidence=""
                for i in "${!table_headers[@]}"; do
                    [[ $i -lt ${#cells[@]} ]] || continue
                    case "${table_headers[i]}" in
                        status) status_cell="${cells[i]}" ;;
                        issue|description) issue="${cells[i]}" ;;
                        fix|action) fix="${cells[i]}" ;;
                        principle|file:line|file)
                            [[ -n "${cells[i]}" ]] && evidence+="${cells[i]}"$'\n'
                            ;;
                    esac
                done
                native_status=open
                [[ "$(lower "$status_cell")" =~ (resolved|closed|withdrawn|legacy[[:space:]]+resolved) ]] && native_status=resolved
                native_add "${native_parsed_ids[0]^^}" "$native_parsed_aliases" "$native_status" \
                    "$issue" "$fix" "$section" "$line" "$line_num" "${status_cell:-detail table}" "$evidence"
            fi
        elif [[ "$in_table" == true && -n "${line//[[:space:]]/}" ]]; then
            table_headers=()
            in_table=false
        fi
    done < "$REVIEW_FILE"

    native_all='['
    native_open='['
    all_first=true
    open_first=true
    native_open_count=0
    native_auto_count=0
    native_blocker_count=0
    native_text=""
    for ((i=0; i<${#native_ids[@]}; i++)); do
        fid="${native_ids[i]}"
        prefix="${fid%%-*}"
        severity_code="$prefix"
        [[ "$prefix" == PRD* ]] && severity_code=PRD
        case "$severity_code" in
            C) severity=critical ;; H) severity=high ;; M) severity=medium ;; L) severity=low ;;
            *) severity=medium ;;
        esac
        category=null
        [[ "$prefix" == PRD* ]] && category="\"$prefix\""
        [[ "$prefix" == CON ]] && category='"constitution"'
        blocking="${native_blockings[i]}"
        [[ -n "$blocking" ]] || native_error ambiguous-legacy-blocking \
            "Finding $fid has no explicit blocking classification." "line ${native_numbers[i]}" \
            "Install Python/PyYAML and use recover-legacy with a complete interpretation and named authorized reviewer."
        status="${native_statuses[i]}"
        legacy_nonauto=false
        if [[ "${native_descriptions[i]}" =~ (accepted|deferred|waived|withdrawn|wontfix|won\'t[[:space:]]+fix|already[[:space:]]+fixed[[:space:]]+upstream) ]]; then
            legacy_nonauto=true
        fi
        eligible=false
        route=report
        if [[ "$prefix" == CON ]]; then
            route=evolve-constitution
            reason='Constitution findings route to /devspark-evolve-constitution, not to product code.'
        elif [[ "$status" == resolved ]]; then
            reason="Status is closed; a human decides whether it still needs work."
        elif [[ "$legacy_nonauto" == true ]]; then
            reason='The legacy report records an accepted, deferred or withdrawn disposition.'
        elif [[ "$blocking" == true && ( "$severity" == critical || "$severity" == high || "$severity_code" == PRD ) ]]; then
            eligible=true
            route=auto
            if [[ "$severity" == critical || "$severity" == high ]]; then reason="Open ${severity^} finding."
            else reason='Open blocking PR-delta finding.'; fi
        elif [[ "$severity_code" == PRD ]]; then reason='PR-delta finding without blocking evidence.'
        else reason='Ordinary Medium or Low findings are report-only.'; fi
        aliases_json='['
        if [[ -n "${native_aliases[i]}" ]]; then
            IFS=',' read -r -a aliases <<< "${native_aliases[i]}"
            for alias in "${aliases[@]}"; do
                [[ "$aliases_json" == '[' ]] || aliases_json+=,
                aliases_json+="\"$alias\""
            done
        fi
        aliases_json+=']'
        evidence_json='['
        while IFS= read -r evidence_item || [[ -n "$evidence_item" ]]; do
            [[ -n "$evidence_item" ]] || continue
            [[ "$evidence_json" == '[' ]] || evidence_json+=,
            evidence_json+="\"$(json_escape "$evidence_item")\""
        done <<< "${native_evidences[i]}"
        evidence_json+=']'
        outcome=""
        [[ "$status" == resolved ]] && outcome='Legacy resolved'
        [[ "$all_first" == true ]] || native_all+=,
        all_first=false
        native_all+="{\"finding_id\":\"$fid\",\"aliases\":$aliases_json,\"severity\":\"$severity\",\"category\":$category,\"blocking\":$blocking,\"description\":\"$(json_escape "${native_descriptions[i]}")\",\"expected_outcome\":\"$(json_escape "${native_expected[i]}")\",\"evidence\":$evidence_json,\"recommended_action\":\"$(json_escape "${native_expected[i]}")\",\"execution_mode\":\"manual\",\"status\":\"$status\",\"outcome\":\"$outcome\",\"provenance\":{\"kind\":\"legacy\",\"location\":\"line ${native_numbers[i]}\",\"section\":\"$(json_escape "${native_sections[i]}")\",\"line\":\"$(json_escape "${native_lines[i]}")\",\"basis\":\"$(json_escape "${native_bases[i]}")\"},\"remediation\":null,\"verification\":null,\"disposition\":null,\"reopen_reason\":null}"
        if [[ "$status" != resolved ]]; then
            [[ "$open_first" == true ]] || native_open+=,
            open_first=false
            native_open_count=$((native_open_count + 1))
            [[ "$eligible" == true ]] && native_auto_count=$((native_auto_count + 1))
            [[ "$blocking" == true ]] && native_blocker_count=$((native_blocker_count + 1))
            native_open+="{\"id\":\"$fid\",\"severity\":\"$severity_code\",\"severity_level\":\"$severity\",\"category\":$category,\"aliases\":$aliases_json,\"line_number\":${native_numbers[i]},\"line\":\"$(json_escape "${native_lines[i]}")\",\"section\":\"$(json_escape "${native_sections[i]}")\",\"status\":\"open\",\"lifecycle_state\":\"open\",\"blocking\":$blocking,\"auto_eligible\":$eligible,\"route\":\"$route\",\"reason\":\"$(json_escape "$reason")\"}"
            native_text+="- $fid [$route]"$'\n'
        fi
    done
    native_all+=']'
    native_open+=']'
    native_recommendation=approve
    (( native_blocker_count == 0 )) || native_recommendation=request-changes
    native_record="{\"format_version\":1,\"findings\":$native_all,\"conditions\":[],\"last_change\":{\"operation\":\"legacy-read\"}}"
    if "$JSON_OUTPUT"; then
        printf '{"ok":true,"pr_id":%s,"review_file":"%s","record":%s,"findings":%s,"open_findings":%s,"open_count":%s,"auto_eligible_count":%s,"historical_count":%s,"pending_verification":[],"pending_verification_count":0,"unresolved_blockers":%s,"recommendation":"%s","diagnostics":[]}\n' \
            "$NORMALIZED" "$(json_escape "$REVIEW_FILE")" "$native_record" "$native_all" "$native_open" \
            "$native_open_count" "$native_auto_count" "${#native_ids[@]}" "$native_blocker_count" "$native_recommendation"
    else
        printf 'Review file: %s\nOpen findings: %s\nAuto-eligible findings: %s\n%s' \
            "$REVIEW_FILE" "$native_open_count" "$native_auto_count" "$native_text"
    fi
    exit 0
fi
