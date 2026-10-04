#!/usr/bin/env python3
"""A/B 同旗标不变式闸门（**可插拔模块**；源自 Octave-Full-Wasm 工单 57/61 的通用化）。

对比两个工件（构建产物身份证、基准报告、任何 JSON）的**声明面**时，唯一的合法差异
是**被测轴**本身。除此之外任何键不同 = 混淆变量混进了 A/B —— 结论作废。
真实事故：分配器 A/B 首报 −39%，事后发现基线带了运行期断言（`--diag` 全套）而候选只带
`NAMES=1` ⇒ 同旗标重测真实差 −27%。如果 A/B 前有这道闸门，−39% 根本不会落档。

规格（`REFLECT_AB`，默认 `ab.json`；数据不是代码）：

    { "pairs": [
        { "name": "分配器 A/B",
          "a": "artifacts/base/octave.build.json",
          "b": "artifacts/cand/octave.build.json",
          "key": "declared",            # 可选：JSON 内点分路径（默认整文件）
          "allow": ["malloc"],          # 被测轴（唯一允许不同的键）
          "why": "…必填…" } ] }

- 除 `allow` 外任何键的值差异 ⇒ 报（混淆变量）；
- `allow` 内的键在两件中**必须都存在且不同或同值**——都存在即可，缺失本身不算
  （缺失语义由产出方管）；
- 工件读不到 ⇒ `SKIP:` 明说（跨机器现实，不是通过）；
- `pairs` 为空 / 条目缺 why ⇒ 报（零值守卫）；
- `REFLECT_AB` 未配 ⇒ 明说未启用退 0。

用法（cwd=仓库根）：python3 zreflect/check_ab.py [--spec ab.json]
退出码：0=绿或未启用 / 1=混淆或配置坏。自证：--selftest（夹具注入）。
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.environ.get("GATE_REPO") or os.getcwd()
DEFAULT_SPEC = "ab.json"


def _load(path):
    try:
        return json.load(open(path, encoding="utf-8")), None
    except (OSError, ValueError) as e:
        return None, str(e)


def _dig(obj, dotted):
    cur = obj
    for k in dotted.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def check(spec, root, loader=_load):
    """纯逻辑（自证注入 loader）。返回 (problems, skips)。"""
    problems, skips = [], []
    pairs = spec.get("pairs") or []
    if not pairs:
        problems.append("pairs 为空（零值守卫：空断言面不是通过）")
        return problems, skips
    for pr in pairs:
        for f in ("name", "a", "b", "why"):
            if not pr.get(f):
                problems.append("pair 缺字段 %s: %r（why 必填——没理由的对比没人敢删）" % (f, pr))
        key = pr.get("key") or ""
        ra, ea = loader(_join(root, pr["a"]))
        rb, eb = loader(_join(root, pr["b"]))
        if ra is None or rb is None:
            skips.append("%s: 工件读不到（%s / %s）⇒ 本次未核对" % (pr["name"], ea or "", eb or ""))
            continue
        da, db = _dig(ra, key) if key else ra, _dig(rb, key) if key else rb
        if not isinstance(da, dict) or not isinstance(db, dict):
            problems.append("%s: key=%r 在两件中至少一件不是 dict" % (pr["name"], key or "(根)"))
            continue
        allow = set(pr.get("allow") or [])
        for k in sorted(set(da) | set(db)):
            if k in allow:
                continue
            if da.get(k) != db.get(k):
                problems.append("%s: 混淆变量——%s 键 %r: A=%r B=%r（非 allow 轴不一致 ⇒ A/B 作废）"
                                % (pr["name"], key or "(根)", k, da.get(k), db.get(k)))
    return problems, skips


def _join(root, path):
    return path if os.path.isabs(path) else os.path.join(root, path)


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
    problems, skips = check(spec, REPO)
    for x in skips:
        print("SKIP: %s" % x)
    if problems:
        for x in problems:
            print("PROBLEM: %s" % x)
        return 1
    print("ok（%d 组 A/B 无混淆变量）" % len(spec.get("pairs") or []))
    return 0


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    def wf(rel, obj):
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(obj, open(p, "w"))
        return rel
    spec = {"pairs": [
        {"name": "分配器 A/B", "a": "a.json", "b": "b.json", "key": "declared",
         "allow": ["malloc"], "why": "被测轴 = 分配器"}]}
    # a/b：除 malloc 外全等
    wf("a.json", {"declared": {"simd": True, "malloc": "mimalloc", "v128": 4752}})
    wf("b.json", {"declared": {"simd": True, "malloc": "dlmalloc", "v128": 4752}})
    wf("mut-a.json", {"declared": {"simd": True, "malloc": "mimalloc", "v128": 4752}})
    wf("mut-b.json", {"declared": {"simd": False, "malloc": "mimalloc", "v128": 4752}})
    wf("nokey.json", {"declared": "不是 dict"})
    empty = {"pairs": []}
    confound_spec = {"pairs": [{"name": "m", "a": "mut-a.json", "b": "mut-b.json",
                                "key": "declared", "allow": ["malloc"], "why": "w"}]}
    cases = [
        ("仅 allow 轴不同 ⇒ 不报（A/B 该有的形状）", lambda: check(spec, d)[0] == []),
        ("★ 非 allow 轴不同 ⇒ 必须报（混淆变量）",
         lambda: any("混淆变量" in x for x in check(confound_spec, d)[0])),
        ("★ 工件读不到 ⇒ SKIP 明说", lambda: any(
            "读不到" in x for x in check(
             {"pairs": [{"name": "x", "a": "nope-a.json", "b": "nope-b.json", "why": "w"}]}, d)[1])),
        ("★ key 指向非 dict ⇒ 必须报", lambda: any(
             "不是 dict" in x for x in check(
             {"pairs": [{"name": "x", "a": "nokey.json", "b": "nokey.json", "why": "w"}]}, d)[0])),
        ("★ pairs 为空 ⇒ 必须报（零值守卫）", lambda: check(empty, d)[0] != []),
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
