#!/bin/sh
set -eu
# Runs inside a temp repo the runner assembles, so the suite copy is beside us
# at run time but absent at lint time — SC1091 is expected here and nowhere else.
# shellcheck source=/dev/null
# shellcheck disable=SC1091
. reflect-hooks/quality-record.sh
_QR_DECLARED=0
_QR_RECORDED=0

declare_check "true" "true"
if true; then
    rc=0
else
    rc=$?
fi
record "true" "true" "$rc"
finish_checks

if (
    _QR_DECLARED=0
    _QR_RECORDED=0
    declare_check "one" "true"
    declare_check "missing" "true"
    record "one" "true" 0 >/dev/null
    finish_checks
) 2>/dev/null; then
    exit 1
fi
printf '%s\n' "quality-record example ok"
