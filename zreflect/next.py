#!/usr/bin/env python3
"""「接着上一轮」的**数据采集器** —— 记忆系统无感化的那一半。

## 它替换掉的是一件人工活

会话压缩之前，人得手工整理「这次干了什么、下一步干什么」。不整理，压缩后
agent 就两手空空：重新提出已经结案的问题，或者从零重新分析一遍。

**「每次都要有人准备压缩」本身就是缺陷** —— 它要求人记得做一件机制该做的事，
而人一旦忘了，代价是整段上下文。

## 采集什么，从哪采

全部从**已经存在的东西**长出来，不新增需要人维护的输入：

    git log HEAD..origin/<branch>   → 未推送的提交（「这一轮做了什么」）
    git status --porcelain          → 未提交的改动 / 未跟踪文件
    FACTS.json                      → 台账条数
    questions/                      → 未结案的悬案

这也是 `collect.py` 的采集器契约（只读持久盘、不引入会自己变的输入）：
`git log` 的结果在同一个提交上稳定，`status` 反映的是**工作区**（本来就该变）。

## 为什么不写进 `FACTS.json`

它**不是测量值** —— 「未推送几个提交」没有复跑契约（每次 `git push` 后就变），
塞进台账会让 `--check` 永不收敛（`collect.py` 原则 2）。它进的是
`STATE.md` 的 `AUTO:NEXT` 块，那块**不参与 `--check` 的逐字节对账**，
每次 Stop 重渲染。

## 诚实边界

  · 它知道「机器看得见的」进度（提交、未提交、悬案），**不知道**「agent 想
    干什么」。后者要人写 —— 但只写一句 `questions/` 里的悬案就够，不需要
    整篇 handoff。
  · 「上一轮」是按**未推送提交**切分的。已经推送的轮次不在里面 ——
    那是历史，而历史不进丈量面（不可复现的东西不占会被判的位置）。
"""
from __future__ import annotations

import os
import subprocess

import doc
from i18n import M                                       # noqa: E402


def _git(repo, *args):
    """跑一条 git 命令；失败返回 None（**不编空值** —— 见 collect.py 原则 3）。"""
    try:
        p = subprocess.run(["git", "-C", repo, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout


def unpublished_commits(repo):
    """未推送的提交标题。取不到 ⇒ None（**不是空表**）。

    ⚠️ 命令必须带 `HEAD`：`git log --oneline --not --remotes`（**没有起点**）
    会**静默返回 0 行** —— 看着像「全都推送了」，实际是「没给起点，git 走了
    另一条默认路径」。实测：同一个仓，带 `HEAD` 得 26 行，不带得 0 行。
    这是本仓最恨的那种失败：**不报错、答案是错的**。
    """
    branch = (_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    if not branch or branch == "HEAD":
        return None
    # 顺序也重要：`HEAD` 在前，`--not --remotes` 在后（`git log` 的起点
    # 必须在 rev 列表里，不能只靠 `--not`）。
    out = _git(repo, "log", "--oneline", "HEAD", "--not", "--remotes")
    if out is None:
        return None
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def working_tree(repo):
    """未提交的改动：返回 (改动文件数, 未跟踪文件数)。"""
    out = _git(repo, "status", "--porcelain")
    if out is None:
        return None
    changed = untracked = 0
    for ln in out.splitlines():
        if not ln.strip():
            continue
        if ln.startswith("??"):
            untracked += 1
        else:
            changed += 1
    return changed, untracked



def collect(repo):
    """采集「接着上一轮」的输入。返回 `(last_turn, pending)` 两个字符串列表。

    两者都可能是空表 —— 空**不是**通过，渲染时会明说「没有记录」。

    ⚠️ 这些行是**用户可见文本**（`SessionStart` 注入进 agent 上下文，人也读
    `STATE.md`）⇒ 一律走 `M()`，与 `gate.finish` 的问题行同一类。

    此前这里写的是裸中文 + 一句 PINNED，理由是「它进 STATE.md 被 --check 逐字节
    对账」——**那句是假的**：`AUTO:NEXT` 被 `facts._is_rechecked` 明确排除在
    `--check` 之外（它每轮都变）。拿一个不成立的理由去豁免，正是本仓在
    `machine_vocab_ok` 上抓过的同一个错。
    """
    last = []
    pending = []

    commits = unpublished_commits(repo)
    if commits is None:
        last.append(M("next.commits_unreadable"))
    elif not commits:
        last.append(M("next.commits_none"))
    else:
        last.append(M("next.commits_count", count=len(commits)))
        for c in commits[:5]:
            last.append("  `%s`" % c)
        if len(commits) > 5:
            last.append("  " + M("next.commits_more", count=len(commits) - 5))

    wt = working_tree(repo)
    if wt is None:
        last.append(M("next.tree_unreadable"))
    else:
        changed, untracked = wt
        last.append(M("next.tree_state", changed=changed, untracked=untracked))
        if changed or untracked:
            pending.append(M("next.tree_dirty"))

    # **未结案的悬案 = 下一步**。此前这里刻意留空（理由是「`inject-state.py`
    # 已有悬案段，两处都列会重复」）—— 但那个段只报「有几条未结案」，
    # 不报「它们是什么」，而压缩后 agent 最需要的正是**名字**。
    # 现在这里给名字，那段给状态，各司其职。
    for q in _open_question_names(repo):
        pending.append(M("next.open_question", name=q))

    return last, pending


def _open_question_names(repo):
    """`questions/` 里未结案的悬案文件名（按名字排序，最多 5 个）。

    读不到目录 ⇒ 返回空表（不是报错）：那是「这个仓不用悬案」的正常形态，
    `inject-state.py` 会明说「读不到」。
    """
    import os                                            # noqa: PLC0415
    d = os.path.join(repo, os.environ.get("REFLECT_QUESTIONS", "").strip()
                     or "questions")
    if not os.path.isdir(d):
        return []
    out = []
    for n in sorted(os.listdir(d)):
        if not n.endswith(".md"):
            continue
        try:
            text = open(os.path.join(d, n), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            continue
        status = ""
        for ln in text.splitlines():
            if ln.strip().lower().startswith("**status:**"):
                status = ln.split(":", 1)[1].strip().lower()
                break
        if status != "resolved":
            out.append(n)
    return out[:5]


NEXT_BEGIN = "<!-- AUTO:NEXT -->"
NEXT_END = "<!-- /AUTO:NEXT -->"


def render(repo):
    """渲染 `AUTO:NEXT` 块（含首尾标记）。**纯函数**：同 repo 状态两次结果相同。

    注入进 agent 上下文的用户可见文本 ⇒ 全部走 `M()`（null 包下是裸 code，
    那是诚实的：没装语言包就说 code）。
    """
    last, pending = collect(repo)
    return render_with(last, pending)


def render_with(last, pending):
    """`render` 的零 I/O 版本（自证用：不碰 git）。"""
    lines = [NEXT_BEGIN,
             str(M("doc.next_block_intro")),
             str(M("doc.next_block_why")),
             ""]
    lines.append(str(M("doc.next_last_turn")) if last
                 else str(M("doc.next_last_turn_none")))
    lines.extend("- %s" % ln for ln in (last or []))
    lines.append("")
    lines.append(str(M("doc.next_pending")) if pending
                 else str(M("doc.next_pending_none")))
    lines.extend("- %s" % ln for ln in (pending or []))
    lines.append(NEXT_END)
    return "\n".join(lines)


def main(argv=None):
    """`python3 zreflect/next.py <repo>` → 打印块（供 Stop 钩子拼进文档）。"""
    import sys
    repo = (argv or sys.argv[1:] or ["."])[0]
    sys.stdout.write(render(os.path.abspath(repo)) + "\n")
    return 0


# ── 自证 ──────────────────────────────────────────────────────────────────────
#
# 本模块**有**自证入口（`selftest=True`）：它的判据是「采集器读不到东西时
# 会不会假装读到了」—— 那是本仓最痛的那类事故，必须能当场证伪。

def _cases():
    """每条都造出**能让它红**的输入（夹具仓，零依赖真仓）。"""
    import tempfile                                      # noqa: PLC0415

    return [
        # ① 正常不报：一个真 git 仓，干净工作区 ⇒ 采集器说得出来
        ("next.collects_from_real_git", lambda: _real_git_case()),
        # ② 该报的必须报 —— **读不到不许编 0**
        ("★ next.missing_repo_is_loud_not_zero",
         lambda: _missing_repo_loud()),
        # 渲染的确定性：同输入两次逐字节相同（它是纯函数）
        ("★ next.render_is_deterministic", lambda: _render_deterministic()),
        # 空待办必须**明说**「若你认为应该有 —— 那是记录的缺口」
        ("★ next.empty_pending_is_explicit", lambda: _empty_pending_explicit()),
        # `git log` 的起点不能省：没有 `HEAD` 时它静默返回 0 行
        # （实测：同一个仓 26 vs 0）。这条钉住「命令形状」而不是结果 ——
        # 结果依赖真仓状态，形状不依赖。
        ("★ next.log_command_has_start_point",
         lambda: _log_command_shape_ok()),
        # ③ 空输入必须报：一个不存在的仓根
        ("★ next.nonexistent_root_is_loud",
         lambda: _nonexistent_root_loud()),
    ]


def _real_git_case():
    import tempfile, shutil, subprocess                   # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "a@b"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "a"],
                       check=True, capture_output=True)
        open(os.path.join(d, "x"), "w").write("x")
        subprocess.run(["git", "-C", d, "add", "x"], check=True)
        subprocess.run(["git", "-C", d, "commit", "-qm", "c"], check=True,
                       capture_output=True)
        last, pending = collect(d)
        # 夹具里的中文用码点（本仓纪律；字面量会让 check_i18n 红）
        # ⚠️ 按 **code** 判，不按渲染文本 —— null 包下渲染成 `next.tree_state(...)`，
        # 断言「文本里有某个词」等于断言「语言包装了」，那是另一件事。
        return any("next.tree_" in getattr(ln, "code", str(ln)) for ln in last)
    except Exception:                                    # noqa: BLE001
        return False
    finally:
        shutil.rmtree(d, True)


def _missing_repo_loud():
    """不存在的仓 ⇒ `unpublished_commits` 返回 None，而不是 `[]`。"""
    return unpublished_commits("/nonexistent-xyz") is None


def _no_questions_loud():
    return open_questions("/nonexistent-xyz") is None


def _render_deterministic():
    import tempfile, shutil                               # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        return render(d) == render(d)
    finally:
        shutil.rmtree(d, True)


def _empty_pending_explicit():
    """没有待办 ⇒ 必须**明说**（`doc.next_pending_none`），不许只是一行空。

    按 code 判（null 包下渲染成 `doc.next_pending_none`，不是句子）。
    """
    import i18n                                          # noqa: PLC0415
    with i18n.bind(i18n.NULL):
        block = render_with(["only last"], [])
    return "doc.next_pending_none" in block


def _nonexistent_root_loud():
    """没有上一轮记录 ⇒ 必须明说（`doc.next_last_turn_none`），不许静默空着。"""
    import i18n                                          # noqa: PLC0415
    with i18n.bind(i18n.NULL):
        block = render_with(None, None)
    return "doc.next_last_turn_none" in block


def _log_command_shape_ok():
    """`unpublished_commits` 用的 git 命令**必须带起点**。

    从源码里读那条命令的参数（不执行 git）—— 判据是形状的，所以夹具无关、
    真仓状态无关。
    """
    import inspect                                       # noqa: PLC0415
    src = inspect.getsource(unpublished_commits)
    # 找 `_git(repo, "log", ...)` 那一行
    for line in src.splitlines():
        if '"log"' in line:
            # 起点必须在 --not 之前出现
            if '"HEAD"' not in line:
                return False
            return line.index('"HEAD"') < line.index("--not")
    return False


def _selftest():
    import sys                                           # noqa: PLC0415
    from gate import main_selftest_or                    # noqa: PLC0415
    from i18n import M                                   # noqa: PLC0415
    return main_selftest_or(sys.argv[1:], M("gate.title.next"), _cases,
                            lambda a: 0)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    if "--selftest" in sys.argv:
        import next as _mod                              # noqa: PLC0415
        sys.exit(_mod._selftest())
    sys.exit(main())

from gate import module_meta                             # noqa: E402

MODULE = module_meta(
    "接着上一轮",
    "记忆系统无感化的数据采集：未推送提交 / 工作区 ⇒ AUTO:NEXT 块"
    "（由 Stop 钩子每轮重渲染，不参与 --check 逐字节对账）",
    selftest=True)
