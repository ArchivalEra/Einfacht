#!/bin/sh
# Einfacht 闸门入口 —— **给别人的钩子系统调用**，不抢占钩子位置。
#
# 为什么是「暴露一个入口」而不是 `git config core.hooksPath reflect-hooks`：
#
#   `core.hooksPath` 是 git 的**全局覆盖开关** —— 一旦设上，git 就**完全不再看**
#   `.git/hooks/`。实测：设了之后 `.git/hooks/pre-commit` 里的脚本一次都不跑，
#   提交照样成功、没有任何提示。于是：
#
#     · husky / lefthook / pre-commit(Python) / 手写钩子 —— 全装 `.git/hooks/`
#       ⇒ 被 `install.sh` **静默废掉**；
#     · 反过来，它们后来重装 ⇒ reflect-hooks 被静默废掉。
#
#   两边都失败得没有声音 —— 正是本仓立身要消灭的「部署了 ≠ 在跑」。
#
# 所以本仓只**暴露一张口**：任何钩子体系在自己的钩子里调这一行即可。
# 钩子位置、顺序、其它工具，全归你自己 —— 我们只提供判据，不抢座位。
#
# 用法（在任何钩子脚本里，如 `.git/hooks/pre-commit` / husky 钩子 / lefthook run）：
#
#     sh <repo>/reflect-hooks/einfacht-gate.sh commit "$(git rev-parse --show-toplevel)"
#
# pre-push 额外要 stdin（git 的 ref 协议）：
#
#     sh <repo>/reflect-hooks/einfacht-gate.sh push "$(git rev-parse --show-toplevel)"
#
# 两个相位：
#
#     commit  重渲染机器块（并 `git add`）+ 跑 runs_at="commit" 的全部闸门
#     push    只校验不修改：机器块必须新鲜 + 全部闸门 + 三语 README 同批
#
# 退出码：0 = 绿；1 = 判据红（拒）；2 = 环境/配置坏（缺 zreflect 等）。
#
# ⚠️ 本入口**也**可以被既有的 `core.hooksPath reflect-hooks` 用法调用（旧装法
#    仍然可用，`reflect-hooks/pre-commit` 就是本入口的薄壳）—— 不破坏老用户。
# ── 自证 ─────────────────────────────────────────────────────────────────────
# 发现式：registry 扫 reflect-hooks/*.sh 里的自证标记，本脚本被自动收编
# （gates-selftest.sh 的 plugin_selftest 会实跑它）。
if [ "${1:-}" = "--selftest" ]; then
  _bad=0
  _chk() {
    if [ "$2" = "$3" ]; then
      echo "PASS | $1"
    else
      echo "fail | $1（期望「$2」实测「$3」）"
      _bad=$((_bad + 1))
    fi
  }
  _SELF="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/einfacht-gate.sh"
  # ① 正常不报：只打印用法就退 0（无参数）
  _chk "无参数 ⇒ 打印用法" "0" "$(sh "$_SELF" >/dev/null 2>&1; echo $?)"
  # ② 该报的必须报：未知相位 / 不存在的仓根 ⇒ rc=2（配置坏，不是判据红）
  _chk "★ 未知相位 ⇒ rc=2" "2" "$(sh "$_SELF" bogus /tmp >/dev/null 2>&1; echo $?)"
  _chk "★ 不存在的仓根 ⇒ rc=2" "2" "$(sh "$_SELF" commit /nonexistent-xyz >/dev/null 2>&1; echo $?)"
  # ③ 空输入必须报：只给相位不给仓根 ⇒ rc=2
  _chk "★ 缺仓根 ⇒ rc=2" "2" "$(sh "$_SELF" commit >/dev/null 2>&1; echo $?)"
  # ④ 仓里没有 zreflect ⇒ 明说是「不是套件落地的仓库」（rc=2，不是静默 0）
  _t=$(mktemp -d); git init -q "$_t"
  _chk "★ 没有 zreflect/ ⇒ rc=2（不是静默通过）" "2" \
    "$(sh "$_SELF" commit "$_t" >/dev/null 2>&1; echo $?)"
  rm -rf "$_t"
  echo "=== $((5 - _bad)) PASS / $_bad FAIL ==="
  exit "$_bad"
fi


set -e
PHASE=${1:-}
REPO=${2:-}

if [ -z "$PHASE" ]; then
  # 无参数 ⇒ 打印用法、退 0（这是自证的「正常不报」档：求帮助不是错误）
  echo "用法: sh einfacht-gate.sh <commit|push> <仓库根>" >&2
  exit 0
fi
if [ -z "$REPO" ]; then
  echo "einfacht-gate: 缺少仓库根（第二个参数必须是绝对路径）" >&2
  exit 2
fi
case "$PHASE" in
  commit|push) ;;
  *) echo "einfacht-gate: 未知相位 '$PHASE'（只认 commit / push）" >&2; exit 2 ;;
esac

if [ ! -d "$REPO" ]; then
  echo "einfacht-gate: 仓库根 '$REPO' 不存在（第二个参数必须是绝对路径）" >&2
  exit 2
fi

# 工具自己的目录（einfacht-env.sh 与 zreflect/ 都在这里或上一级）
TOOL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# 可拔插件（issue #8）：repo-local REFLECT_* 载体 = Einfacht.env。
# 载体与工具目录的关系是「同一个套件」，所以先把工具目录告诉插件。
[ -f "$TOOL_DIR/einfacht-env.sh" ] && . "$TOOL_DIR/einfacht-env.sh"

cd "$REPO"

if [ ! -d zreflect ]; then
  echo "einfacht-gate: '$REPO' 里没有 zreflect/ —— 不是套件落地的仓库，或 GATE_REPO 指错了" >&2
  exit 2
fi

DOC=${REFLECT_DOC:-STATE.md}

if [ "$PHASE" = "commit" ]; then
  # ① 机器块重渲染（**只渲染，不重测** —— 重测由人负责，issue #4 ③）
  if [ -f "$DOC" ]; then
    python3 zreflect/facts.py --render-doc "$DOC"
    git add "$DOC"
  fi
else
  # ①' pre-push **不改文件、不动历史**：不新鲜就直接拒
  if [ -f "$DOC" ]; then
    python3 zreflect/facts.py --check "$DOC"
  fi
fi

# ② 全部闸门：执行面唯一产地（C1）—— 跑 runs_at="commit" 的闸门并把
#    ran / off / failed 聚合（off 不是通过，单列出来）。
python3 zreflect/registry.py --run commit || exit 1

if [ "$PHASE" = "push" ]; then
  # ③ 三语 README 同批（判据住在 check_readme_sync.py 的 --changed 模式；
  #    这里只做 git 的簿记：从 stdin 的 ref 协议算出「这次要推的改动文件集」）。
  ZERO=0000000000000000000000000000000000000000
  CHANGED=$(mktemp)
  trap 'rm -f "$CHANGED"' EXIT
  refs_checked=0
  while read -r lref lsha rref rsha; do
    [ -n "${lref:-}" ] || continue
    case "$lref" in refs/tags/*) continue ;; esac        # tag 不携带新内容
    [ "$lsha" = "$ZERO" ] && continue                    # 删分支
    if [ "$rsha" = "$ZERO" ]; then
      revs=$(git rev-list "$lsha" --not --remotes 2>/dev/null || true)
    else
      revs="$rsha..$lsha"
      git rev-list $revs >/dev/null 2>&1 || revs="$lsha"
    fi
    if [ -z "$revs" ]; then
      echo "einfacht-gate: $lref 没有要发布的新内容 ⇒ 三语判据对其无事可查（明说，不假装查过）" >&2
      refs_checked=$((refs_checked + 1))
      continue
    fi
    git log --name-only --pretty=format: $revs 2>/dev/null | sed '/^[[:space:]]*$/d' > "$CHANGED" || true
    if ! python3 zreflect/check_readme_sync.py --changed "$CHANGED"; then
      echo "einfacht-gate 拒绝：$lref 这批推送没把三语 README **同批**更新" >&2
      echo "           （CI 跑同一条判据；--no-verify 只躲得过本地）。名单可配：REFLECT_READMES。" >&2
      exit 1
    fi
    refs_checked=$((refs_checked + 1))
  done
  if [ "$refs_checked" -eq 0 ]; then
    echo "einfacht-gate: 没有携带内容的分支推送（tag/删除）⇒ 三语判据无事可查（明说，不假装查过）" >&2
  fi
fi
