#!/bin/sh
# 把 Einfacht 的闸门接到你的仓库 —— **不抢钩子座位**。
#
# 为什么不再 `git config core.hooksPath reflect-hooks`：
#
#   `core.hooksPath` 是 git 的**全局覆盖开关**，一旦设上，git 就**完全不再看**
#   `.git/hooks/`。实测：设了之后 `.git/hooks/pre-commit` 里的脚本一次都不跑，
#   提交照样成功、**没有任何提示**。于是 husky / lefthook / pre-commit(Python) /
#   手写钩子全被**静默废掉** —— 正是本仓立身要消灭的「部署了 ≠ 在跑」。
#
# 所以本仓只**暴露一个入口**（reflect-hooks/einfacht-gate.sh），钩子位置归你自己。
#
# 三种接入方式，都**可逆**，都不影响你已有的钩子：
#
#   sh reflect-hooks/install.sh             # 只打印接入说明（不写任何文件）
#   sh reflect-hooks/install.sh --chain     # 装成 .git/hooks/ 的**链式** wrapper
#                                           # （已有同名钩子 ⇒ 先跑它，再跑我们）
#   sh reflect-hooks/install.sh --legacy    # 旧装法（core.hooksPath）—— **会覆盖**
#                                           # .git/hooks，只在没有别的钩子时用
#   sh reflect-hooks/install.sh --uninstall # 卸载（两种装法都认）
set -e
MODE=${1:-}
# 第二个参数：**目标仓库根**（默认本仓）。装到别的仓时必须显式给 ——
# 否则会装进工具自己的 .git/hooks（实测踩到：鸠占鹊巢的在场证明）。
TARGET_REPO=${2:-}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=${TARGET_REPO:-$(CDPATH= cd -- "$HERE/.." && pwd)}
if [ -n "$TARGET_REPO" ] && [ ! -d "$TARGET_REPO/.git" ]; then
  echo "install: '$TARGET_REPO' 不是 git 仓库（没找到 .git）" >&2
  exit 2
fi
GATE="$HERE/einfacht-gate.sh"

usage() {
  cat <<'EOF'
用法：sh reflect-hooks/install.sh [--chain | --legacy | --uninstall] [目标仓根]

不给目标仓根 ⇒ 装到本仓（工具所在的仓）。给别人装时务必给：

  （无参数）[目标仓]  打印接入说明，**不写任何文件**（建议先看这个）
                  不给目标仓 ⇒ 说的是本仓
  --chain         装 .git/hooks/{pre-commit,pre-push} 的链式 wrapper：
                  已有同名钩子 ⇒ 先跑它、再跑 Einfacht（不夺位）
  --legacy        旧装法：git config core.hooksPath reflect-hooks
                  ⚠️ 会**完全屏蔽** .git/hooks/ 里的其它钩子 —— 只在没有别的
                  钩子工具时用
  --uninstall     撤销 --chain（恢复原有钩子）与 --legacy（unset hooksPath）
EOF
}

case "$MODE" in
  "")
    cat <<EOF
Einfacht 不抢钩子座位 —— 只暴露一个入口，你的钩子体系自己调它：

  pre-commit 里：sh "$GATE" commit "\$(git rev-parse --show-toplevel)" < /dev/null
  pre-push   里：sh "$GATE" push   "\$(git rev-parse --show-toplevel)"   # stdin 直通

要现成的接入：

  sh reflect-hooks/install.sh --chain      # 链式装进 .git/hooks（不夺位）
  sh reflect-hooks/install.sh --uninstall  # 撤销

为什么不再设 core.hooksPath：它是全局覆盖开关，设了之后 git 完全不看
.git/hooks/ —— husky / lefthook / pre-commit / 手写钩子会被**静默废掉**
（提交照样成功、没有提示）。那是「部署了 ≠ 在跑」的教科书形态。
EOF
    exit 0
    ;;
  --help|-h)
    usage
    exit 0
    ;;
  --chain)
    chmod +x "$GATE"
    HOOKS="$REPO/.git/hooks"
    if [ ! -d "$HOOKS" ]; then
      echo "install: 找不到 $HOOKS（不是 git 仓库？）" >&2
      exit 2
    fi
    for pair in pre-commit:commit pre-push:push; do
      name=${pair%%:*}
      phase=${pair#*:}
      target="$HOOKS/$name"
      prev="$HOOKS/$name.einfacht-prev"
      if [ -f "$target" ] && ! grep -q "einfacht-gate.sh" "$target" 2>/dev/null; then
        # 已有别人的钩子 ⇒ 挪到 .einfacht-prev，wrapper 里先跑它再跑我们
        mv "$target" "$prev"
        echo "install: 保留已有的 $name 为 $name.einfacht-prev（会先于 Einfacht 执行）"
      fi
      cat > "$target" <<WRAPPER
#!/bin/sh
# Einfacht 链式 wrapper（由 reflect-hooks/install.sh --chain 生成）
HERE=\$(CDPATH= cd -- "\$(dirname -- "\$0")" && pwd)
PREV="\$HERE/$name.einfacht-prev"
if [ -x "\$PREV" ]; then
  "\$PREV" "\$@" || exit \$?
fi
exec sh "$GATE" $phase "\$(git rev-parse --show-toplevel)"
WRAPPER
      chmod +x "$target"
      echo "install: 已装 $name（链式）"
    done
    echo
    echo "装了链式 wrapper。撤销：sh reflect-hooks/install.sh --uninstall"
    ;;
  --legacy)
    git -C "$REPO" config core.hooksPath reflect-hooks
    chmod +x "$HERE/pre-commit" "$HERE/pre-push"
    echo "hooks 已挂载（旧装法）：$(git -C "$REPO" config core.hooksPath)"
    echo "⚠️ 这会完全屏蔽 .git/hooks/ —— 其它钩子工具会被静默废掉。"
    echo "（卸载：sh reflect-hooks/install.sh --uninstall）"
    ;;
  --uninstall)
    if git -C "$REPO" config --unset core.hooksPath 2>/dev/null; then
      echo "已撤销 core.hooksPath（旧装法）"
    else
      echo "core.hooksPath 本来就没设"
    fi
    HOOKS="$REPO/.git/hooks"
    for name in pre-commit pre-push; do
      target="$HOOKS/$name"
      prev="$HOOKS/$name.einfacht-prev"
      if [ -f "$target" ] && grep -q "einfacht-gate.sh" "$target" 2>/dev/null; then
        rm -f "$target"
        echo "已移除链式 wrapper：$name"
      fi
      if [ -f "$prev" ]; then
        mv "$prev" "$target"
        echo "已恢复原有钩子：$name"
      fi
    done
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
