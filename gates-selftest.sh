#!/bin/sh
# 闸门自证：**发现**闸门（不靠手写名单）+ 每个闸门必须先证明自己会红。
#
# 为什么是「发现」而不是「清单」：手写名录一定会漂。加新检查器时忘了登记，那个检查器
# 就变成「没人盯着的检查器」—— 而名录本身还绿着告诉你一切正常。实测过：一个自证脚本
# 自己拿某个检查器的 `0/0` bug 当立论依据，而那个检查器至今不在它的名单里。
# 所以这里反过来：**登记是被发现的，不是被记得的。**
#
# 用法：sh gates-selftest.sh          跑全部闸门
#       sh gates-selftest.sh --selftest   证明这个 runner 自己会红（它也需要）
set -u
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

run_gates() {
  # $1 = 仓库根。全绿返回 0；否则返回 1。
  d=$1
  n=0
  bad=0
  for g in "$d"/zreflect/check_*.py; do
    [ -f "$g" ] || continue
    n=$((n + 1))
    rel=${g#"$d"/}
    if ! grep -q -- '--selftest' "$g"; then
      echo "  ❌ $rel 没有 --selftest（未登记的闸门 = 没人盯着的闸门）"
      bad=$((bad + 1))
      continue
    fi
    out=$(GATE_REPO="$d" python3 "$g" --selftest 2>&1)
    if [ $? -ne 0 ]; then
      echo "  ❌ $rel"
      printf '%s\n' "$out" | tail -3 | sed 's/^/      /'
      bad=$((bad + 1))
    else
      echo "  ✅ $rel  $(printf '%s\n' "$out" | tail -1)"
    fi
  done
  if [ "$n" -eq 0 ]; then
    echo "  ❌ 一个闸门都没发现 —— 零值守卫：空输入不是通过"
    return 1
  fi
  if [ "$bad" -ne 0 ]; then
    echo "  ---- 发现 $n 个闸门，其中 $bad 个有问题"
    return 1
  fi
  echo "  ---- 发现 $n 个闸门，全部能红 ✅"
  return 0
}

selftest() {
  t=$(mktemp -d)
  bad=0
  mkdir -p "$t/good/zreflect" "$t/nomark/zreflect" "$t/failing/zreflect" "$t/empty/zreflect"

  # 夹具①：广告了 --selftest 且全过 ⇒ 应该全绿
  cat >"$t/good/zreflect/check_ok.py" <<'EOF'
import sys
print("=== ok 自证：3 PASS / 0 fail ===")
sys.exit(0 if "--selftest" in sys.argv else 0)
EOF
  # 夹具②：没广告 --selftest ⇒ 必须红
  cat >"$t/nomark/zreflect/check_silent.py" <<'EOF'
import sys
sys.exit(0)
EOF
  # 夹具③：广告了但自证失败 ⇒ 必须红
  cat >"$t/failing/zreflect/check_bad.py" <<'EOF'
import sys
print("=== bad 自证：1 PASS / 1 fail ===")
sys.exit(1 if "--selftest" in sys.argv else 0)
EOF
  # 夹具④：一个闸门都没有 ⇒ 必须红（零值守卫）

  show() { printf '%s' "$1" | sed 's/^/      /'; }

  out=$(run_gates "$t/good" 2>&1) && { echo "  PASS | 全绿夹具 ⇒ runner 绿"; } \
    || { echo "  fail | 全绿夹具 ⇒ runner 却是红的（阳性对照失败：runner 可能是'总是红'）"; show "$out"; bad=1; }

  out=$(run_gates "$t/nomark" 2>&1) && { echo "  fail | 缺 --selftest 的闸门 ⇒ runner 竟然绿了"; bad=1; } \
    || echo "  PASS | 缺 --selftest 的闸门 ⇒ runner 红"

  out=$(run_gates "$t/failing" 2>&1) && { echo "  fail | 自证失败的闸门 ⇒ runner 竟然绿了"; bad=1; } \
    || echo "  PASS | 自证失败的闸门 ⇒ runner 红"

  out=$(run_gates "$t/empty" 2>&1) && { echo "  fail | 一个闸门都没有 ⇒ runner 竟然绿了（零值守卫失效）"; bad=1; } \
    || echo "  PASS | 一个闸门都没有 ⇒ runner 红（零值守卫）"

  rm -rf "$t"
  if [ "$bad" -eq 0 ]; then
    echo "=== gates-selftest 自证：4 PASS / 0 fail ==="
    return 0
  fi
  echo "=== gates-selftest 自证：有失败 ==="
  return 1
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
else
  echo "闸门自证（发现式名录）："
  run_gates "$HERE"
fi
