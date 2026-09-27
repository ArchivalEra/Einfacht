#!/usr/bin/env python3
"""翻案闸门：**已被推翻的断言不许悄悄回来当现状。**

`retractions.json` 每条 = 一条已翻案的断言：
  `text` 特征片段 · `why` 为什么错 · `evidence` 怎么复跑 · `fixed_in` 现在哪里说对了

判据：活状态文档里出现 `text` 的那一行**必须带更正标记**。这是唯一能在「翻过的句子
重新出现」时报警的机制 —— 实测过的代价：一条更正过的断言在**同一个文件**里留了下来，
而且在另一份文档里还有副本。散文靠自觉，这个靠闸门。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import repo, require_nonempty, selftest        # noqa: E402
from ledger import load                                  # noqa: E402

MARKERS = ("已翻案", "更正", "是错的", "误读", "推翻", "曾写", "曾经", "已作废",
           "废弃", "不再成立", "superseded", "retracted")
REQUIRED = ("id", "text", "why", "evidence", "fixed_in")
DOCS = ("STATE.md", "AGENTS.md", "README.md")


def problems(retractions, docs):
    """返回问题清单（纯函数：自证要用）。`docs` = {文件名: 正文}。"""
    out = []
    if retractions is None or "retractions" not in (retractions or {}):
        # 零值守卫：结构都不对，就别谈「没有违规」。
        return ["`retractions.json` 缺 `retractions` 键 —— 结构不对 ≠ 没有问题"]
    if not docs:
        # 零值守卫：一份文档都没扫到 ⇒ 「没发现重现行」是空话。
        return ["一份活状态文档都没扫到 —— 空输入不是通过（零值守卫）"]
    for r in retractions.get("retractions") or []:
        for fld in REQUIRED:
            if not (r.get(fld) if isinstance(r, dict) else None):
                out.append("翻案条目缺 `%s`：%r" % (fld, r.get("id") if isinstance(r, dict) else r))
        text = (r or {}).get("text") or ""
        if not text:
            continue
        for name, body in sorted(docs.items()):
            for i, line in enumerate((body or "").splitlines(), 1):
                if text in line and not any(m in line for m in MARKERS):
                    out.append("%s:%d 出现已被推翻的断言「%s」（%s）：要么删掉，要么带更正标记"
                               % (name, i, text, r.get("id", "?")))
    return out


def run(argv):
    rp = repo("retractions.json")
    if not os.path.exists(rp):
        print("FATAL: 缺 %s" % rp, file=sys.stderr)
        return 2
    docs = {}
    for name in (argv or DOCS):
        p = repo(name)
        if os.path.exists(p):
            docs[name] = open(p, encoding="utf-8", errors="replace").read()
    try:
        require_nonempty("check_retractions", docs, "被扫描的活状态文档")
    except SystemExit as e:
        print("%s" % e, file=sys.stderr)
        return 2
    probs = problems(load(rp), docs)
    for x in probs:
        print("  · %s" % x, file=sys.stderr)
    if probs:
        print("翻案重现检测：%d 个问题" % len(probs), file=sys.stderr)
        return 1
    n = len(load(rp).get("retractions") or [])
    print("翻案重现检测：OK（%d 条翻案，扫了 %d 份文档）" % (n, len(docs)))
    return 0


def _cases():
    ok_r = {"retractions": [{"id": "R-1", "text": "这东西是绿的", "why": "其实红",
                             "evidence": "跑 x", "fixed_in": "文档 y"}]}
    doc_ok = "（记录）这东西是绿的 —— 已翻案，见 R-1\n"
    return [
        # ① 正常不报
        ("带更正标记 ⇒ 不报", lambda: problems(ok_r, {"A.md": doc_ok}) == []),
        ("完全没有这条断言 ⇒ 不报", lambda: problems(ok_r, {"A.md": "干净的文档\n"}) == []),
        ("空翻案列表 + 有文档 ⇒ 不报（还没翻过案是合法状态）",
         lambda: problems({"retractions": []}, {"A.md": "x\n"}) == []),
        # ② 该报的必须报
        ("★ 断言重新出现且无标记 ⇒ 必须报",
         lambda: any("R-1" in x for x in problems(ok_r, {"A.md": "这东西是绿的。\n"}))),
        ("★ 条目缺字段 ⇒ 必须报",
         lambda: any("缺 `evidence`" in x for x in problems(
             {"retractions": [{"id": "R-2", "text": "t", "why": "w", "fixed_in": "f"}]},
             {"A.md": "x\n"}))),
        # ③ 空输入必须报
        ("★ 一份文档都没扫到 ⇒ 必须报", lambda: problems(ok_r, {}) != []),
        ("★ 缺 retractions 键 ⇒ 必须报", lambda: problems({}, {"A.md": "x\n"}) != []),
        ("★ 文件整体为 None ⇒ 必须报", lambda: problems(None, {"A.md": "x\n"}) != []),
    ]


if __name__ == "__main__":
    sys.exit(selftest("check_retractions（翻案重现检测）", _cases())
             if "--selftest" in sys.argv else run(sys.argv[1:]))
