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
  空 pins ⇒ 报（零值守卫）；`REFLECT_PINS` 未配 ⇒ 明说未启用退 0。

与 `check_invariants`（#7）正交：那边守**仓库文件文本**，这边守**派生副本的活性身份**。
与 `doctor`（#10）正交：doctor 问「活着吗」，本闸门问「是钉住的那个吗」。

用法（cwd=仓库根）：python3 zreflect/check_pins.py [--spec pins.json]
（规格名解析：--spec 显式 > `REFLECT_PINS` 旋钮 > 默认 `pins.json`）
退出码：0=绿或未启用 / 1=发现问题 / 2=配置坏。自证：--selftest（runner 注入，不碰真 docker）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.environ.get("GATE_REPO") or os.getcwd()
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


def check(spec, run=_run):
    """纯逻辑（自证注入 run）。返回 (problems, skips)。"""
    problems, skips = [], []
    pins = spec.get("pins") or []
    if not pins:
        problems.append("pins 为空（零值守卫：空断言面不是通过）")
        return problems, skips
    for p in pins:
        for f in ("name", "worktree"):
            if not p.get(f):
                problems.append("pin 缺字段 %s: %r（why/name 必填的家族规矩）" % (f, p))
        wt = os.path.join(REPO, p["worktree"]) if not os.path.isabs(p["worktree"]) else p["worktree"]
        head = ""
        if os.path.isdir(wt):
            rc, head = run("git -C %s rev-parse HEAD" % wt)
            if rc != 0:
                problems.append("%s: worktree HEAD 读不到（不是 git 树？）" % p["name"])
                continue
        else:
            problems.append("%s: worktree %s 不存在（指针在、树不在）" % (p["name"], p["worktree"]))
            continue
        if p.get("kind") == "tree":
            rc, out = run(p["stamp_read"])
            if rc != 0 or not out:
                skips.append("%s: stamp 读不到（未供给？）" % p["name"])
                continue
            parts = out.split()
            if len(parts) < 3:
                problems.append("%s: stamp 形态坏（要 name/branch/commit/dirty）: %r" % (p["name"], out[:40]))
                continue
            if parts[2] != head:
                problems.append("%s: 派生副本 commit %s ≠ worktree HEAD %s（供给后指针 bump 了？）"
                                % (p["name"], parts[2][:12], head[:12]))
            if len(parts) > 3 and parts[3] not in ("0", ""):
                problems.append("%s: 派生副本带本地改动（dirty=%s）" % (p["name"], parts[3]))
        elif p.get("kind") == "version":
            rc, out = run(p.get("version_read", ""))
            first = out.splitlines()[0] if out else ""
            if rc != 0 or not first:
                skips.append("%s: 版本命令读不到" % p["name"])
                continue
            if p.get("expect_version") and p["expect_version"] not in first:
                problems.append("%s: 版本漂移（期望 %s，实测 %s）"
                                % (p["name"], p["expect_version"], first[:48]))
        else:
            problems.append("%s: 未知 kind %r（tree | version）" % (p["name"], p.get("kind")))
    return problems, skips


def main(argv):
    spec_path, explicit = resolve_spec(argv, os.environ.get("REFLECT_PINS", ""))
    path = os.path.join(REPO, spec_path) if not os.path.isabs(spec_path) else spec_path
    if not os.path.isfile(path):
        if explicit:
            print("FATAL: 显式指定的规格 %s 不存在（--spec / REFLECT_PINS）—— "
                  "先写规格（或撤掉指定）" % spec_path, file=sys.stderr)
            return 2
        print("未启用（%s 不存在 ⇒ 明说未启用退 0，可插拔）" % spec_path)
        return 0
    try:
        spec = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("配置坏：读不了 %s：%s" % (spec_path, e))
        return 2
    problems, skips = check(spec)
    for x in skips:
        print("SKIP: %s" % x)
    if problems:
        for x in problems:
            print("PROBLEM: %s" % x)
        return 1
    print("ok（%d 个 pin 全部一致）" % len(spec.get("pins") or []))
    return 0


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "wt"))
    def _git(*a):
        subprocess.run(["git", "init", "-q", os.path.join(d, "wt")], check=True)
        open(os.path.join(d, "wt", "f"), "w").write("x")
        subprocess.run(["git", "-C", os.path.join(d, "wt"), "add", "f"], check=True)
        subprocess.run(["git", "-C", os.path.join(d, "wt"), "-c", "user.name=t", "-c",
                        "user.email=t@t", "commit", "-qm", "base"], check=True)
        return subprocess.run(["git", "-C", os.path.join(d, "wt"), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    head = _git()
    # worktree 用**绝对路径**（引擎按 GATE_REPO/abs 解析；夹具树在临时目录）
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
    cases = [
        ("规格名解析：--spec > 旋钮 > 默认名（显式带回 True）",
         lambda: resolve_spec(["--spec", "x.json"], "K.json") == ("x.json", True)
         and resolve_spec([], "K.json") == ("K.json", True)
         and resolve_spec([], "") == ("pins.json", False)),
        ("stamp/版本全一致 ⇒ 不报", lambda: check(spec, run=_run) == ([], [])),
        ("★ 派生副本 commit ≠ HEAD ⇒ 必须报（供给后指针 bump）",
         lambda: any("≠" in x for x in check(bad_spec, run=_run)[0])),
        ("★ 派生副本 dirty ⇒ 必须报（手改派生树）",
         lambda: any("dirty" in x for x in check(dirty_spec, run=_run)[0])),
        ("★ 版本漂移 ⇒ 必须报", lambda: any("版本漂移" in x for x in check(ver_spec, run=_run)[0])),
        ("★ stamp 读不到 ⇒ SKIP（明说，不是通过）",
         lambda: any("SKIP" in x or "读不到" in x for x in check(skip_spec, run=_run)[1])),
        ("★ pins 为空 ⇒ 必须报（零值守卫）", lambda: check(nopin_spec)[0] != []),
        ("★ worktree 不存在 ⇒ 必须报（指针在、树不在）",
         lambda: any("不存在" in x for x in check(
             {"pins": [{"name": "x", "kind": "tree", "worktree": "nope",
                        "stamp_read": "true"}]}, run=_run)[0])),
    ]
    import shutil
    bad = 0
    for name, fn in cases:
        ok = bool(fn())
        print("%s | %s" % ("PASS" if ok else "fail", name))
        bad += 0 if ok else 1
    shutil.rmtree(d, ignore_errors=True)
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
