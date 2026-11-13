#!/bin/sh
# quality-record.sh —— 评估器记录模板（issue #41 裁决：② 为主 + ① 的子集）。
#
# 它只提供「记录 + 自检」的形状，宿主无关：record() 输出 TSV 行到 **stdout**，
# 写到哪里（results.tsv / $GITHUB_STEP_SUMMARY）由使用方决定 —— 套件不认任何
# CI 平台的产物格式（host_agnostic）。
#
# 为什么不是各仓手写双数组：names[] / cmds[] 两条平行数组会配对漂移——
# 漏一项 ⇒ 下一项拿到空命令、rc 恒 0 ⇒ **静默假绿** + 畸形摘要行（实测：
# uTLS-Gone 首跑、GitRoll round-3 红测③）。record() 从形状上消除配对：
# 名字、命令、结果在同一行产生，没有第二份清单可以对不齐。
#
# 用法：
#   . reflect-hooks/quality-record.sh
#   declare_check "ruff" "python -m ruff check ."
#   ruff_rc=$(run_check "ruff")
#   record "ruff" "python -m ruff check ." "$ruff_rc"
#   finish_checks        # 两数不等（声明 vs 记录）⇒ 非零退出 —— 假绿在源头被拒
#
# 自证：bash reflect-hooks/quality-record.sh --selftest
#   （三档：正常 / 漏项必红 / 空输入必红 —— selfcert_harness 原则，模板也先证明会红）

# 声明一道检查（名字 + 命令）。与 record() 分开：声明在跑之前，记录在跑之后，
# finish_checks 验两数一致 —— 「声明的都记了，记录的都声明了」。
declare_check() {
    _qr_name=$1
    _qr_cmd=$2
    if [ -z "$_qr_name" ] || [ -z "$_qr_cmd" ]; then
        echo "quality-record: declare_check needs a name and a command" >&2
        return 1
    fi
    _QR_DECLARED=${_QR_DECLARED:-0}
    _QR_DECLARED=$((_QR_DECLARED + 1))
    export _QR_DECLARED
}

# 跑一道已声明的检查并记录。命令重定向到日志（使用方给路径或默认 /tmp）。
run_check() {
    _qr_name=$1
    _qr_log=${QR_LOG_DIR:-/tmp}/"$1.log"
    mkdir -p "${QR_LOG_DIR:-/tmp}"
    eval "$2" > "$_qr_log" 2>&1
    _QR_LAST_RC=$?
    return $_QR_LAST_RC
}

# 记录一行 TSV：name \t command \t rc。rc 必须是 0–255 整数（畸形行当场被拒，
# GitRoll 红测③的 `FAIL (rc=)` 形状从这里就进不来）。
record() {
    _qr_name=$1
    _qr_cmd=$2
    _qr_rc=$3
    case "$_qr_rc" in
        ''|*[!0-9]*) echo "quality-record: rc must be an integer, got '$_qr_rc'" >&2; return 1 ;;
    esac
    if [ "$_qr_rc" -lt 0 ] || [ "$_qr_rc" -gt 255 ]; then
        echo "quality-record: rc out of range 0-255: $_qr_rc" >&2
        return 1
    fi
    if [ -z "$_qr_name" ] || [ -z "$_qr_cmd" ]; then
        echo "quality-record: name and command must be non-empty" >&2
        return 1
    fi
    _QR_RECORDED=${_QR_RECORDED:-0}
    _QR_RECORDED=$((_QR_RECORDED + 1))
    export _QR_RECORDED
    printf '%s\t%s\t%s\n' "$_qr_name" "$_qr_cmd" "$_qr_rc"
}

# 自检：声明数 == 记录数。不等 ⇒ 假绿风险（有声明没记录 = 漏跑；有记录没声明
# = 拼凑），非零退出，**在源头拒绝**而不是等摘要层发现畸形行。
finish_checks() {
    _QR_DECLARED=${_QR_DECLARED:-0}
    _QR_RECORDED=${_QR_RECORDED:-0}
    if [ "$_QR_DECLARED" -ne "$_QR_RECORDED" ]; then
        echo "quality-record: declared $_QR_DECLARED checks but recorded $_QR_RECORDED" \
            "—— the missing ones would have shown up as silent green" >&2
        return 1
    fi
    if [ "$_QR_RECORDED" -eq 0 ]; then
        echo "quality-record: zero checks recorded — an empty check surface is" \
            "not a pass (zero-value guard)" >&2
        return 1
    fi
    return 0
}

# ── 自证 ─────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--selftest" ]; then
    # ⚠️ The tests below re-source this file inside $( ... ): a subshell
    # **inherits the positional parameters**, so "$0" re-entering this file
    # would hit the same --selftest branch again => infinite recursion (fork
    # bomb; observed on the first run). `set --` clears them first.
    set --
    fail=0
    t() { printf '  %s\n' "$1"; }

    # ① 正常：声明 3、记录 3、rc 合法 ⇒ 全过
    out=$( { . "$0"; _QR_DECLARED=0; _QR_RECORDED=0
             declare_check a "true"; declare_check b "true"; declare_check c "true"
             record a "true" 0 && record b "true" 0 && record c "true" 0
             finish_checks; } 2>&1 ) || fail=$((fail + 1))
    t "normal 3-declared 3-recorded => ok: $([ $fail = 0 ] && echo PASS || echo FAIL)"

    # ② 漏项必红：声明 3、记录 2 ⇒ finish_checks 必须非零
    out2=$( { . "$0"; _QR_DECLARED=0; _QR_RECORDED=0
             declare_check a "true"; declare_check b "true"; declare_check c "true"
             record a "true" 0; record b "true" 0
             finish_checks; } 2>&1 ) && fail=$((fail + 1))
    t "missing record (3 declared / 2 recorded) => rejected: $(echo "$out2" | head -1)"

    # ③ 空输入必红：零声明零记录 ⇒ 不是「无事发生」，是说不过去
    out3=$( { . "$0"; _QR_DECLARED=0; _QR_RECORDED=0; finish_checks; } 2>&1 ) \
        && fail=$((fail + 1))
    t "zero checks => rejected (zero-value guard): $(echo "$out3" | head -1)"

    # ④ 畸形 rc 必拒：`FAIL (rc=)` 那种空 rc 从这里就进不来
    out4=$( { . "$0"; _QR_DECLARED=0; _QR_RECORDED=0
             record a "true" ""; } 2>&1 ) && fail=$((fail + 1))
    t "empty rc => rejected: $(echo "$out4" | head -1)"

    # ⑤ rc 越界必拒
    out5=$( { . "$0"; _QR_DECLARED=0; _QR_RECORDED=0
             record a "true" 256; } 2>&1 ) && fail=$((fail + 1))
    t "rc 256 => rejected: $(echo "$out5" | head -1)"

    echo "=== $((5 - fail)) PASS / $fail FAIL ==="
    [ "$fail" = 0 ]
fi
