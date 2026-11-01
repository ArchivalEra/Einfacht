#!/usr/bin/env python3
"""上游/派生树 pin 一致性闸门（**可插拔模块**；源自 Octave-Full-Wasm 仓库架构批的通用化）。

一个仓库挂 N 个上游 fork/submodule 时的新缺口：**submodule 指针 bump 了、
派生副本（容器里的供给树/部署目录）还在用旧内容**——这种漂移不在任何 git 视图里。
机制：供给方（build 脚本）把派生树复制的**同时**写一个 stamp 文件
（约定内容：`<name> <branch> <commit> <dirty-count>`），本闸门每提交把 stamp
与 worktree 的 HEAD 对读——三条断言：commit 一致 / 派生树干净 / 版本串匹配。

规格（`REFLECT_PINS`，默认 `pins.json`；数据不是代码）：

    { "pins": [
        { "name": "octave", "kind": "tree",
          "worktree": "upstream/octave",                  # 宿主 git 工作树
          "stamp_read": "sudo -E docker exec ctr cat /x/.upstream-pin" },
        { "name": "emsdk", "kind": "version",
          "worktree": "upstream/emsdk",
          "version_read": "sudo -E docker exec ctr emcc --version",
          "expect_version": "5.0.7" } ] }

- `tree`：派生副本 ↔ worktree HEAD。commit 不一致（供给后指针 bump）与
  dirty≠0（有人手改派生树）都报——与「声明了却没检查」同族的「复制了却没钉」。
- `version`：命令输出首行必须含 `expect_version`（portable 工具链那种无法整树
  入 git 的上游，钉版本串）。
- 读不到命令输出 ⇒ `SKIP:`（明说未核对，不是通过——换了机器不是错）；
  空 pins ⇒ 报（零值守卫）；`REFLECT_PINS` 未配 ⇒ 明说未启用退 0；
  显式指定（--spec / 旋钮）而文件不在 ⇒ FATAL 退 2。

与 `check_invariants`（#7）正交：那边守**仓库文件文本**，这边守**派生副本的活性身份**。
与 `doctor`（#10）正交：doctor 问「活着吗」，本闸门问「是钉住的那个吗」。

用法（cwd=仓库根）：python3 zreflect/check_pins.py [--spec pins.json]
（规格名解析：--spec 显式 > `REFLECT_PINS` 旋钮 > 默认 `pins.json`）
退出码：0=绿或未启用 / 1=发现问题 / 2=配置坏。自证：--selftest（runner 注入，不碰真 docker）。
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import fatal, finish, load_spec, main_selftest_or, meta, off  # noqa: E402
from gate import repo                                     # noqa: E402
from i18n import M                                        # noqa: E402

DEFAULT_SPEC = "pins.json"


def resolve_spec(argv, knob=""):
    """规格名解析：--spec 显式 > REFLECT_PINS 旋钮 > 默认名（纯函数，自证要用）。

    返回 (规格名, 是否显式指定)。显式指定（argv / 旋钮）而文件不在 ⇒ 调用方
    必须 FATAL（配置了却不存在的规格是「部署了 ≠ 在跑」家族，静默当「未启用」
    会掩盖坏配置）；默认名不在 ⇒ 未启用退 0。docstring 承诺过的旋钮必须
    真实现：只写在文档里、代码不读的旋钮是幻影，配了静默无效，比没有更坏。
    """
    for i, a in enumerate(argv):
        if a == "--spec":
            return argv[i + 1], True
    k = (knob or "").strip()
    if k:
        return k, True
    return DEFAULT_SPEC, False


def _run(cmd):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def _required_field_problems(p):
    """pin 条目必填字段（name / worktree）缺失 ⇒ 报（why/name 必填的家族规矩）。"""
    return [M("pins.pin_missing_field", field=f, entry=p)
            for f in ("name", "worktree") if not p.get(f)]


def _resolve_worktree(root, p):
    """worktree 相对仓库根解析（绝对路径原样用）。"""
    return p["worktree"] if os.path.isabs(p["worktree"]) else os.path.join(root, p["worktree"])


def _head_problems(p, root, run):
    """读 worktree HEAD。返回 (问题清单, head 或 None)；None ⇒ 本 pin 到此为止。"""
    wt = _resolve_worktree(root, p)
    if not os.path.isdir(wt):
        return [M("pins.worktree_missing", name=p["name"],
                  path=p["worktree"])], None
    rc, head = run("git -C %s rev-parse HEAD" % wt)
    if rc != 0:
        return [M("pins.head_unreadable", name=p["name"])], None
    return [], head


def _tree_pin_problems(p, head, run):
    """kind=tree：派生副本 ↔ worktree HEAD（commit 一致 / 派生树干净）。

    返回 (problems, skips)。
    """
    problems, skips = [], []
    rc, out = run(p["stamp_read"])
    if rc != 0 or not out:
        skips.append(M("pins.stamp_unreadable", name=p["name"]))
        return problems, skips
    parts = out.split()
    if len(parts) < 3:
        problems.append(M("pins.stamp_malformed", name=p["name"], actual=out[:40]))
        return problems, skips
    if parts[2] != head:
        problems.append(M("pins.commit_mismatch", name=p["name"],
                          declared=parts[2][:12], actual=head[:12]))
    if len(parts) > 3 and parts[3] not in ("0", ""):
        problems.append(M("pins.dirty", name=p["name"], count=parts[3]))
    return problems, skips


def _version_pin_problems(p, run):
    """kind=version：命令输出首行必须含 expect_version。返回 (problems, skips)。"""
    problems, skips = [], []
    rc, out = run(p.get("version_read", ""))
    first = out.splitlines()[0] if out else ""
    if rc != 0 or not first:
        skips.append(M("pins.version_unreadable", name=p["name"]))
        return problems, skips
    if p.get("expect_version") and p["expect_version"] not in first:
        problems.append(M("pins.version_drift", name=p["name"],
                          declared=p["expect_version"], actual=first[:48]))
    return problems, skips


def _pin_problems(p, root, run):
    """单个 pin 的三条断言（字段 / HEAD / kind 分派）。返回 (problems, skips)。"""
    problems, skips = _required_field_problems(p), []
    if problems:
        # 必填字段缺失 ⇒ 到此为止（后面的 HEAD / kind 读取都要 name/worktree，
        # 缺字段本身就是要报的事，别让它退化成 KeyError）。
        return problems, skips
    head_probs, head = _head_problems(p, root, run)
    problems += head_probs
    if head is None:
        return problems, skips
    kind = p.get("kind")
    if kind == "tree":
        tree_probs, tree_skips = _tree_pin_problems(p, head, run)
    elif kind == "version":
        tree_probs, tree_skips = _version_pin_problems(p, run)
    else:
        tree_probs = [M("pins.unknown_kind", name=p["name"], field=kind)]
        tree_skips = []
    return problems + tree_probs, skips + tree_skips


def check(spec, run=_run, root=None):
    """纯逻辑（自证注入 run）。返回 (problems, skips)。

    `root` = 相对 worktree 的锚（默认被检查仓库根；自证传夹具目录）。
    """
    root = repo() if root is None else root
    pins = spec.get("pins") or []
    if not pins:
        return [M("pins.empty")], []
    problems, skips = [], []
    for p in pins:
        probs, sks = _pin_problems(p, root, run)
        problems += probs
        skips += sks
    return problems, skips


def main(argv):
    spec_path, explicit = resolve_spec(argv, os.environ.get("REFLECT_PINS", ""))
    path = spec_path if os.path.isabs(spec_path) else repo(spec_path)
    if not os.path.isfile(path):
        if explicit:
            return fatal(M("pins.explicit_spec_missing", name=spec_path))
        return off(M("pins.off", name=spec_path))
    spec, err = load_spec(path)
    if err:
        return fatal(M("pins.spec_broken", name=spec_path, error=err))
    problems, skips = check(spec)
    for x in skips:
        print("SKIP: %s" % x, file=sys.stderr)   # 契约前缀在发射点字面量
    return finish(M("pins.title"), problems,
                  M("pins.ok", count=len(spec.get("pins") or [])))


def _cases():
    import atexit                                        # noqa: PLC0415
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    os.makedirs(os.path.join(d, "wt"))

    def _git(*_a):
        subprocess.run(["git", "init", "-q", os.path.join(d, "wt")], check=True)
        open(os.path.join(d, "wt", "f"), "w").write("x")
        subprocess.run(["git", "-C", os.path.join(d, "wt"), "add", "f"], check=True)
        subprocess.run(["git", "-C", os.path.join(d, "wt"), "-c", "user.name=t", "-c",
                        "user.email=t@t", "commit", "-qm", "base"], check=True)
        return subprocess.run(["git", "-C", os.path.join(d, "wt"), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    head = _git()
    # worktree 用**绝对路径**（引擎按仓库根/abs 解析；夹具树在临时目录）
    wt = os.path.join(d, "wt")
    spec = {"pins": [
        {"name": "octave", "kind": "tree", "worktree": wt,
         "stamp_read": "echo octave wasm/11.3.0 %s 0" % head},
        {"name": "emsdk", "kind": "version", "worktree": wt,
         "version_read": "echo emcc 5.0.7", "expect_version": "5.0.7"}]}
    bad_spec = {"pins": [{"name": "octave", "kind": "tree", "worktree": wt,
                          "stamp_read": "echo octave wasm/11.3.0 %s 0" % ("d" * 40)}]}
    dirty_spec = {"pins": [{"name": "octave", "kind": "tree", "worktree": wt,
                            "stamp_read": "echo octave wasm/11.3.0 %s 3" % head}]}
    ver_spec = {"pins": [{"name": "emsdk", "kind": "version", "worktree": wt,
                          "version_read": "echo emcc 6.0.10", "expect_version": "5.0.7"}]}
    skip_spec = {"pins": [{"name": "octave", "kind": "tree", "worktree": wt,
                           "stamp_read": "false"}]}
    nopin_spec = {"pins": []}
    return [
        ("pins.resolve_spec",
         lambda: resolve_spec(["--spec", "x.json"], "K.json") == ("x.json", True)
         and resolve_spec([], "K.json") == ("K.json", True)
         and resolve_spec([], "") == ("pins.json", False)),
        # ① 正常不报
        ("pins.ok", lambda: check(spec, run=_run, root=d) == ([], [])),
        # ② 该报的必须报
        ("★ pins.commit_mismatch",
         lambda: [p.code for p in check(bad_spec, run=_run, root=d)[0]]
         == ["pins.commit_mismatch"]),
        ("★ pins.dirty",
         lambda: [p.code for p in check(dirty_spec, run=_run, root=d)[0]]
         == ["pins.dirty"]),
        ("★ pins.version_drift",
         lambda: [p.code for p in check(ver_spec, run=_run, root=d)[0]]
         == ["pins.version_drift"]),
        ("★ pins.stamp_unreadable",
         lambda: [p.code for p in check(skip_spec, run=_run, root=d)[1]]
         == ["pins.stamp_unreadable"]),
        ("★ pins.worktree_missing",
         lambda: [p.code for p in check(
             {"pins": [{"name": "x", "kind": "tree", "worktree": "nope",
                        "stamp_read": "true"}]}, run=_run, root=d)[0]]
         == ["pins.worktree_missing"]),
        ("★ pins.pin_missing_field",
         lambda: [p.code for p in check(
             {"pins": [{"name": "x", "kind": "tree", "stamp_read": "true"}]},
             run=_run, root=d)[0]] == ["pins.pin_missing_field"]),
        ("★ pins.unknown_kind",
         lambda: [p.code for p in check(
             {"pins": [{"name": "x", "kind": "weird", "worktree": wt}]},
             run=_run, root=d)[0]] == ["pins.unknown_kind"]),
        # ③ 空输入必须报
        ("★ pins.empty",
         lambda: [p.code for p in check(nopin_spec, root=d)[0]] == ["pins.empty"]),
    ]


GATE = meta("pin 闸门", "派生树 pin 一致性（stamp commit / dirty / 版本串对读）",
            knobs=("REFLECT_PINS",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "check_pins", _cases, main))
