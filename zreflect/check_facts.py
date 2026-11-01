#!/usr/bin/env python3
"""事实闸门：文档里的块必须与台账一致，正文不许出现裸数字，引用不许指向不存在的键。

三条规则对应三种真实事故：

  · 块与台账不一致 —— 有人手改了块（或者改了台账忘了重渲染）；
  · 正文裸数字 —— 数字被手抄进散文，从这一刻起它就开始腐烂
    （阈值 `REFLECT_NAKED_MIN` 可配；围栏代码块 / 行内代码内豁免 ——
    文档里的复跑命令天然带数字，把它当裸数字是误报，issue #3 ④）；
  · 引用不存在的键 —— 键被改名/删掉，引用原地变成一句没有出处的断言。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import fatal, finish, main_selftest_or, meta, repo  # noqa: E402
from i18n import M, load_pack                             # noqa: E402
from knobs import a_pack_lang                      # noqa: E402
from ledger import facts_of, load, value_of              # noqa: E402
from living import DATED_RECORD   # noqa: E402
from render import BLOCK_BEGIN, BLOCK_END, body_of, prose_of, render_block  # noqa: E402

# 正文引用数字的写法：`[[键名]]`。刻意选一个不可能是自然语言的形状 ——
# 这样「有没有引用」是**可判定的**，不靠正则猜散文。
CITE_RE = re.compile(r"\[\[([A-Za-z_][A-Za-z0-9_]*)\]\]")

BARE_MIN = 100   # 默认裸数字阈值：小于它的整数不查（1/2/3 遍地都是，查了全是噪音）
FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _bare_min():
    """裸数字阈值（issue #3 ④）：`REFLECT_NAKED_MIN` 可配；坏值 ⇒ 默认 + 告警。"""
    raw = os.environ.get("REFLECT_NAKED_MIN", "").strip()
    if not raw:
        return BARE_MIN
    try:
        return int(raw)
    except ValueError:
        print("⚠ %s" % M("facts.bad_bare_min", value=raw, default=BARE_MIN),
              file=sys.stderr)
        return BARE_MIN


def _number_lines(doc_text):
    """裸数字判据要扫的行（issue #3 ④）：**围栏代码块与行内代码豁免**。

    返回 [(行号, 去掉行内代码后的行)]；行号保持**原文编号** ——
    诊断要对得上人读的文档。围栏的开/关行本身不扫。
    """
    prose = prose_of(doc_text)
    in_fence = False
    out = []
    for i, line in enumerate(prose.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append((i, INLINE_CODE_RE.sub("", line)))
    return out



# 形状白名单（issue #24）：这些形状的数字**不是**「手抄的测量值」，不该报。
# 反向判据（白名单式）若不排除它们，正文立刻被版本号/端口/日期刷屏，
# 最后被一律 --accept 掉 —— 比不做更糟（本仓反复踩过的「会误报的闸门
# 最终被整闸关掉」）。
_SHAPE_PATTERNS = (
    r"\d+\.\d+(\.\d+)*",          # 版本串 11.3.0 / 1.2
    r"[A-Za-z_]\w*\d+\w*",           # 标识符里的数字 sha256 / utf8 / v128
    r"\d{4}-\d{2}-\d{2}",            # ISO 日期
    r"\d{2}:\d{2}(:\d{2})?",         # 时刻
    r"0x[0-9a-fA-F]+",                 # 十六进制
    r"\d+%",                           # 百分比
    r"\d+[KMG]i?B",                    # 容量 74MB / 32MiB
    r"[\w./-]+/\d+",                  # 路径段 /113/
)


def _shape_exempt(token):
    """这个数字**出现的位置**是否属于形状白名单（版本/标识符/日期/路径…）。"""
    for pat in _SHAPE_PATTERNS:
        if re.fullmatch(pat, token):
            return True
    return False


_SHA_NEAR = re.compile(r"sha|hash|校验|指纹|commit", re.I)


def _known_values(facts):
    """台账里出现过的整数值集（抄了但没引用的黑名单判据已单独查）。"""
    known = set()
    for entry in facts.values():
        v = value_of(entry)
        if isinstance(v, int) and not isinstance(v, bool):
            known.add(v)
    return known


def _has_provenance(token, line):
    """token 在（已剥形状串的）`line` 里是否有出处。

    形状白名单 / 带 sha 上下文的裸 sha / 同行 `[[键名]]`，任一命中即有出处。
    """
    if _shape_exempt(token):
        return True
    # 裸 sha：只在该行有 sha/hash/commit 上下文时放行（那是 check_stale
    # 的活；无上下文的 8 位数字是测量值，不是 sha —— 实测踩到：
    # 99887766 被纯十六进制白名单误放）。
    if (re.fullmatch(r"[0-9a-f]{7,64}", token)
            and _SHA_NEAR.search(line)):
        return True
    return bool(CITE_RE.search(line))    # 同行有 [[键名]] ⇒ 视为引用式出处


def _unaccounted_numbers(doc_text, facts, bare_min, nlines):
    """反向判据（issue #24）：正文里**没有出处**的 ≥阈值数字。

    此前只查「台账里的值被手抄了」——一个**从未进过台账**的数字，闸门不知道
    要拦（`AGENTS.md` 说「check_facts 会拦正文里的裸数字」，无保留表述）。
    下游实测：v4 协议文档手抄 21 个数字全绿，人工复查发现至少 3 个是错的。

    判据（白名单式）：扫正文（围栏/行内代码外，`_number_lines` 已剥），
    每个 ≥ bare_min 的整数 token 必须有**出处**之一，否则报：

      · 紧跟 `[[键名]]`（同行）—— 引用式出处；
      · 命中形状白名单（版本串 / 标识符 / 日期 / 路径 / 裸 sha / 百分比 / 容量）；
      · 同行带明确出处标记（`DATED_RECORD` 型交付名或反引号 sha）；
      · 该值**恰好等于**某条台账事实的值（黑名单判据已单独查「抄了但没引用」，
        这里不重复报）。
    """
    known = _known_values(facts)
    out = []
    # 先整行剥掉「形状串」（日期/时刻/版本/容量/百分比/路径/标识符）——
    # 否则 `2026-10-31` 会被切出 `2026` 这个假 token（`-` 不在 \w 里，
    # 逐 token 匹配挡不住；实测踩到）。
    strip_re = re.compile("|".join(_SHAPE_PATTERNS))
    for lineno, line in nlines:
        if DATED_RECORD.search(line):
            continue                     # 带明确出处的记录行整行豁免（同 stale 的口径）
        line = strip_re.sub(" ", line)
        for token in re.findall(r"(?<![\w.])\d+(?![\w.])", line):
            try:
                val = int(token)
            except ValueError:
                continue
            if val < bare_min or val in known:
                continue
            if _has_provenance(token, line):
                continue
            out.append(M("facts.bare_number_unaccounted",
                         line=lineno, number=token))
    return out


def _cite_problems(prose, facts):
    """正文里引用了不存在键的 `[[键名]]`。"""
    out = []
    for i, line in enumerate(prose.splitlines(), 1):
        for k in CITE_RE.findall(line):
            if k not in facts:
                out.append(M("facts.missing_key_cite", line=i, key=k))
    return out


def _copied_fact_problems(facts, nlines, bare_min):
    """黑名单判据：台账里的值被手抄进正文，却没在同一行写 `[[键名]]`。"""
    out = []
    for k, entry in sorted(facts.items()):
        v = value_of(entry)
        if isinstance(v, bool) or not isinstance(v, int) or v < bare_min:
            continue
        for i, line in nlines:
            if str(v) in line and ("[[%s]]" % k) not in line:
                out.append(M("facts.copied_value", line=i, value=v, key=k))
    return out


def problems(ledger, doc_text, bare_min=None):
    """返回问题清单（纯函数：自证要用）。空列表 = 通过。

    `bare_min` 覆盖裸数字阈值（自证显式传）；默认读 `REFLECT_NAKED_MIN`。
    """
    bm = _bare_min() if bare_min is None else bare_min
    f = facts_of(ledger)
    if not f:
        # 零值守卫：台账空着不是「没有违规」，是「什么都没量」。
        return [M("facts.empty_ledger")]
    if BLOCK_BEGIN not in doc_text or BLOCK_END not in doc_text:
        return [M("facts.no_block_markers",
                  begin=BLOCK_BEGIN, end=BLOCK_END)]

    out = []
    if body_of(doc_text).strip() != body_of(render_block(ledger)).strip():
        out.append(M("facts.block_mismatch"))

    out += _cite_problems(prose_of(doc_text), f)

    nlines = _number_lines(doc_text)
    out += _copied_fact_problems(f, nlines, bm)
    # 反向判据（issue #24）：从没进过台账的数字也要有出处。
    out += _unaccounted_numbers(doc_text, f, bm, nlines)
    return out


def run(argv):
    doc = argv[0] if argv else os.environ.get("REFLECT_DOC", "STATE.md")
    p = doc if os.path.isabs(doc) else repo(doc)
    if not os.path.exists(p):
        return fatal(M("facts.doc_missing", path=p))
    facts_name = os.environ.get("REFLECT_FACTS", "FACTS.json")
    led_path = repo(facts_name)
    if not os.path.exists(led_path):
        return fatal(M("facts.ledger_missing", name=facts_name))
    led = load(led_path)
    probs = problems(led, open(p, encoding="utf-8").read())
    return finish(M("facts.title"), probs,
                  M("facts.ok", count=len(facts_of(led))))


LED = {"facts": {"count": {"value": 4752, "cmd": "c"}}}




def _cases():
    # 夹具的文档正文用**英文**（它们是被扫描的输入，不是本体的输出 —— 「速度是
    # 4752 次」这类中文样本会让零语言闸门把夹具当消息）。判据本身与语言无关：
    # 裸数字 / 引用 / 形状白名单都只看 token 形态。
    good = "no bare numbers here.\n" + render_block(LED)
    numberless = {"facts": {"n": {"value": 3, "cmd": "c"}}}
    fifty = {"facts": {"n": {"value": 50, "cmd": "c"}}}

    def codes(ledger, doc, **kw):
        return [p.code for p in problems(ledger, doc, **kw)]

    # 「诊断话必须说清怎么修」这类判据在 null 包里验不了（null 包只有 code +
    # 参数）。所以读**磁盘上真实发布的 zh 包** —— 注入假表只能证明「我写的模板
    # 渲染得出我写的话」（循环论证）；读真包才把「迁移没丢语义」变成可证伪的
    # 断言（zh 包按契约存的是逐字的被移除文本）。
    # ⚠️ **不能写死 `zh`**：下游仓可能只装一个包（正是产品主场景「从一堆包里
    # 挑一个」）。此前硬写 zh，`REFLECT_I18N=<只有 en 的目录>` 下这条自证直接红
    # （实测 17 PASS / 1 FAIL）—— 判据是「渲染保真」，语言是谁不重要。
    # 一个包都没装 ⇒ 这些用例无从成立（零包是**合法态**：用户没挑语言），
    # `a_pack_lang()` 返回 None ⇒ 下面的真包判据走**条件短路**（真空成立，
    # 装了包就必须完整 —— 装坏包仍会红，已实测）。
    pack_lang = a_pack_lang()
    real_pack = load_pack(pack_lang) if pack_lang else {}

    def pack_placeholders(code):
        """该包里某条 code 的占位名集合（缺条目 ⇒ 空集，断言当场红）。"""
        import re                                        # noqa: PLC0415
        return set(re.findall(r"%\((\w+)\)", real_pack.get(code, "")))

    return [
        # ① 正常不报
        ("facts.block_ok",
         lambda: problems(LED, good) == []),
        ("facts.live_cite_ok",
         lambda: problems(LED, "see [[count]]\n" + render_block(LED)) == []),
        ("facts.small_int_exempt",
         lambda: problems(numberless, "there are 3\n"
                          + render_block(numberless)) == []),
        # ② 该报的必须报
        ("★ facts.block_mismatch",
         lambda: codes(LED, "x\n" + render_block({"facts": {}}))
         == ["facts.block_mismatch"]),
        ("★ facts.copied_value",
         lambda: codes(LED, "speed is 4752 times\n" + render_block(LED))
         == ["facts.copied_value"]),
        ("★ facts.missing_key_cite",
         lambda: codes(LED, "see [[nope]]\n" + render_block(LED))
         == ["facts.missing_key_cite"]),
        # ② 反向判据（issue #24）：从没进过台账的数字也要有出处
        ("★ facts.bare_number_unaccounted",
         lambda: codes(LED, "measured 99887766 but not in ledger.\n"
                        + render_block(LED))
         == ["facts.bare_number_unaccounted"]
         and any("99887766" in str(p) for p in problems(
             LED, "measured 99887766 but not in ledger.\n" + render_block(LED))),
         ),
        ("facts.cite_counts_as_provenance",
         lambda: problems(LED, "see [[count]] = 99887766\n"
                          + render_block(LED)) == []),
        ("facts.pack_entry_wired",
         # 真实包里「无出处」这条必须存在、且**接收该 code 实际发的那两个参数**
         # （删掉这条 code / 改坏占位名 ⇒ 这条红）。断言只用 ASCII 锚点（code 名 +
         # 占位名）—— 中文锚点会把自己变成「本体里的自然语言」，正是零语言闸门
         # 要消灭的形状；语义是否仍说「怎么修」由包 diff 审查承担。
         # **条件判据**：装了包就必须完整（删条目 / 改坏占位名 ⇒ 这条红）；
         # 零包（合法态：用户没装任何语言）⇒ 无对象可验，理据真空成立。
         # 真仓永远有包，所以这条在真环境里必然真考。
         lambda: not pack_lang or
         pack_placeholders("facts.bare_number_unaccounted")
         == {"line", "number"}),
        ("facts.shape_whitelist",
         lambda: problems(LED, "v11.3.0 and sha256 and 2026-10-31\n"
                          + render_block(LED)) == []),
        ("★ facts.bare_sha_needs_context",
         lambda: codes(LED, "just wrote 99887766\n" + render_block(LED))
         == ["facts.bare_number_unaccounted"]),
        # ③ 空输入必须报
        ("★ facts.empty_ledger",
         lambda: codes({"facts": {}}, good) == ["facts.empty_ledger"]),
        ("★ facts.no_block_markers",
         lambda: codes(LED, "a document with no block at all")
         == ["facts.no_block_markers"]),
        # ④ 裸数字判据扩展（issue #3 ④）
        ("facts.fenced_exempt",
         lambda: problems(LED, "```\nspeed is 4752 times\n```\n"
                          + render_block(LED)) == []),
        ("facts.inline_code_exempt",
         lambda: problems(LED, "see `4752` times\n" + render_block(LED)) == []),
        ("facts.below_threshold_exempt",
         lambda: problems(fifty, "there are 50\n" + render_block(fifty)) == []),
        ("★ facts.threshold_knob",
         lambda: codes(fifty, "there are 50\n" + render_block(fifty), bare_min=10)
         == ["facts.copied_value"]
         and "50" in str(problems(fifty, "there are 50\n" + render_block(fifty),
                                  bare_min=10)[0])),
        ("★ facts.bare_number_outside_fence",
         lambda: codes(LED, "```\n4752\n```\nspeed is 4752 times\n"
                        + render_block(LED)) == ["facts.copied_value"]),
    ]


GATE = meta("事实闸门", "块一致性 / 裸数字 / 坏引用",
            knobs=("REFLECT_FACTS", "REFLECT_DOC", "REFLECT_NAKED_MIN"), name_dependent=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.facts"),
                              _cases, run))
