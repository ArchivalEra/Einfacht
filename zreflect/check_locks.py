#!/usr/bin/env python3
"""锁定源清单闸门（**可插拔模块**；源自 Octave-Full-Wasm 仓库架构批的通用化）。

不是每个上游都有可 git 化的官方仓（netlib 的 f2c/lapack 老版、freedesktop 的 glu、
sourceforge 的 qrupdate…）。对它们，"钉版"只能退而求其次：**URL + 文件 + sha256**
的锁定清单。本闸门核对这份清单：

    { "locked": [
        { "name": "glpk", "version": "5.0",
          "url": "https://ftp.gnu.org/gnu/glpk/glpk-5.0.tar.gz",
          "file": "third_party/glpk-5.0.tar.gz",      # 相对 GATE_REPO 或绝对
          "sha256": "…" },                             # 文件形态必填；目录形态可省
        { "name": "lapack", "version": "3.4.2", "file": "…/lapack-3.4.2",
          "form": "dir", "optional": true } ] }

- 文件形态：**sha256 必填且必须匹配**（缺失/不符都报——这是"钉版"的全部含义）；
- 目录形态：只查存在（目录无单值哈希；`optional: true` 的条目在本机缺席 ⇒ SKIP
  明说，不是通过——跨机器构建的仓库需要这个口子）；
- `locked` 为空 / 条目缺 name/url ⇒ 报（零值守卫；没有理由的锁定条目是僵尸）。

与 `check_invariants`（#7）正交：那边守"文件该长什么样（文本）"，这边守
"外部工件的**内容指纹**"——它们共同把"上游"从散装 tarball 变成可查事实。

**边界（不藏）**：sha256 只证明"还是那份字节"，不证明"那份字节是对的"——
URL 与版本的对应关系是清单作者的主张，闸门不做网络验证（重取是 build 脚本的事）。

用法（cwd=仓库根）：python3 zreflect/check_locks.py [--spec upstream-lock.json]
退出码：0=绿或未启用 / 1=问题 / 2=配置坏。自证：--selftest。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

REPO = os.environ.get("GATE_REPO") or os.getcwd()
DEFAULT_SPEC = "upstream-lock.json"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(spec, hasher=_sha):
    """纯逻辑（自证注入 hasher）。返回 (problems, skips)。"""
    problems, skips = [], []
    locked = spec.get("locked") or spec.get("sources") or []
    if not locked:
        problems.append("locked 清单为空（零值守卫：空断言面不是通过）")
        return problems, skips
    for s in locked:
        for f in ("name", "url", "file"):
            if not s.get(f):
                problems.append("锁定条目缺字段 %s: %r（没有理由的锁定是僵尸）" % (f, s))
        if problems and problems[-1].startswith("锁定条目缺字段"):
            continue
        path = s["file"]
        if not os.path.isabs(path):
            path = os.path.join(REPO, path)
        if not os.path.exists(path):
            if s.get("optional"):
                skips.append("%s: 本机缺席（optional ⇒ 明说，不是通过）" % s["name"])
            else:
                problems.append("%s: 锁定的文件/目录不存在：%s" % (s["name"], path))
            continue
        want = s.get("sha256")
        if not want:
            if (s.get("form") or "file") == "dir":
                continue                      # 目录形态：只查存在
            problems.append("%s: 文件形态的锁定条目没有 sha256（那不叫钉版）" % s["name"])
            continue
        got = hasher(path)
        if got != want:
            problems.append("%s: sha256 不符（清单 %s… 实测 %s…）⇒ 上游字节漂了"
                            % (s["name"], want[:12], got[:12]))
    return problems, skips


def main(argv):
    spec_path = DEFAULT_SPEC
    for i, a in enumerate(argv):
        if a == "--spec":
            spec_path = argv[i + 1]
    path = spec_path if os.path.isabs(spec_path) else os.path.join(REPO, spec_path)
    if not os.path.isfile(path):
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
    print("ok（%d 个锁定源全部一致）" % len(spec.get("locked") or spec.get("sources") or []))
    return 0


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    payload = b"UPSTREAM-FIXTURE"
    good = hashlib.sha256(payload).hexdigest()
    open(os.path.join(d, "glpk.tar.gz"), "wb").write(payload)
    os.makedirs(os.path.join(d, "lapack-3.4.2"))
    # 夹具用**绝对路径**（引擎按 GATE_REPO 解析相对路径；夹具树在临时目录）
    g = os.path.join(d, "glpk.tar.gz")
    lp = os.path.join(d, "lapack-3.4.2")
    spec = {"locked": [
        {"name": "glpk", "version": "5.0", "url": "u", "file": g, "sha256": good},
        {"name": "lapack", "version": "3.4.2", "url": "u", "file": lp, "form": "dir"},
        {"name": "mesa", "version": "x", "url": "u", "file": "nope.tar.xz", "optional": True},
    ]}
    bad_hash = {"locked": [{"name": "glpk", "version": "5.0", "url": "u",
                            "file": g, "sha256": "0" * 64}]}
    missing = {"locked": [{"name": "glpk", "version": "5.0", "url": "u", "file": "nope.tar.gz",
                           "sha256": good}]}
    no_sha = {"locked": [{"name": "glpk", "version": "5.0", "url": "u", "file": g}]}
    empty = {"locked": []}
    cases = [
        ("锁定一致/目录形态/optional 缺席 ⇒ 不报", lambda: check(spec)[0] == [] and check(spec)[1] != []),
        ("★ sha256 不符 ⇒ 必须报（字节漂了）",
         lambda: any("sha256 不符" in x for x in check(bad_hash)[0])),
        ("★ 锁定文件缺席（非 optional）⇒ 必须报",
         lambda: any("不存在" in x for x in check(missing)[0])),
        ("★ 文件形态没有 sha256 ⇒ 必须报（那不叫钉版）",
         lambda: any("没有 sha256" in x for x in check(no_sha)[0])),
        ("★ locked 为空 ⇒ 必须报（零值守卫）", lambda: check(empty)[0] != []),
    ]
    bad = 0
    for name, fn in cases:
        ok = bool(fn())
        print("%s | %s" % ("PASS" if ok else "fail", name))
        bad += 0 if ok else 1
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv[1:]))
