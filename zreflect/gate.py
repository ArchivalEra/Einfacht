#!/usr/bin/env python3
"""闸门平台：rc 契约 + 零值守卫 + 三档自证。

它解决的**不是**「没有检查」，而是**检查在输入消失时静默变绿**。真实踩过的三种：

  · 三个站点同时缺 `VERSION` ⇒ 一致性闸门报「完全一致」；
  · 声明的集合是空的 ⇒ 出厂核对报 `verdict: "ok"`；
  · 自检脚本 `0/0` ⇒ 算「全部通过」。

所以任何检查器都必须能回答两句话：**输入空了我报吗？**、**该报的我会报吗？**
`require_nonempty()` 答第一句，`selftest()` 的三类用例答第二句。

**rc 契约（本平台的 interface，2026-10-07 起全仓唯一产地）**：

  · `off()`    ⇒ 0，未启用（可插拔闸门的 off 态必须**明说**，不许静默）；
  · `fatal()`  ⇒ 2，配置 / 环境坏（旋钮指向缺失、坏 JSON、规格结构坏、
    仪器本身坏了）—— 配置性失败 ≠ 检查失败，混进 1 会让「发现问题」
    与「配置坏了」不可区分；
  · `finish()` ⇒ 1（有 problems）/ 0（绿）。标题在先、问题行在后，
    问题行统一 stderr —— 此前 13 道闸门各手抄一份、已漂出两派
    （stdout/stderr 混用、标题先后不一），这里收敛成一份。

自证期间纯函数保持安静（print 归 run()/顶层，issue #1 ③）。
"""
import json
import os
import sys

_AST_CACHE = {}

# 被检查的仓库根：默认是本包的上一级，可用 GATE_REPO 覆盖（测试夹具靠它）。
GATE_REPO = os.environ.get("GATE_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo(*parts):
    """拼一个指向被检查仓库的绝对路径。"""
    return os.path.join(GATE_REPO, *parts)


def require_nonempty(name, seq, what=None):
    """零值守卫：收集阶段什么都没收到 ⇒ 报错，**不许当「干净」**。

    这是本包最重要的一行。绝大多数「闸门假装通过」的事故，根因都是这里没守：
    遍历一个不存在的目录得到空集，然后「没有发现违规」——两句都是真的，结论是错的。

    `what` = 被收集物的称呼（默认走语言包 `gate.input_label`）。
    """
    import i18n                                          # noqa: PLC0415
    if what is None:
        what = i18n.M("gate.input_label")
    items = list(seq)
    if not items:
        # `FATAL:` 是机器契约前缀 —— 在**发射点**字面量（不进语言包）。
        # `what` 可能是调用方给的 Message（如 `M("stale.scanned_docs")`）：
        # 先 str() 拍平，否则 null 包里会渲染成嵌套的 `repr(Message)`。
        raise SystemExit("FATAL: %s" % i18n.M("gate.require_nonempty",
                                              name=name, what=str(what)))
    return items


def guard_nonempty(name, seq, what=None):
    """`require_nonempty` 的 rc 版：空 ⇒ 打印 FATAL、返回 2；非空 ⇒ None。

    给「直接跑」的检查器用（它们要的是退出码，不是异常）。
    """
    try:
        require_nonempty(name, seq, what)
        return None
    except SystemExit as e:
        print("%s" % e, file=sys.stderr)
        return 2


def off(notice):
    """未启用：明说 + 退 0。

    ⚠️ **off 与「真跑通过」必须可区分**（C2）：两者 rc 都是 0（off 不是失败，
    hooks 的 `|| exit` 不该把它当红），但 off 在 stdout 打一行机器可读标记
    `OFF: …` —— 执行面（`gate.run_phase`）据此把闸门分成 ran / off / failed
    三档，而不是把「没跑」算进「绿」。此前 off 只打 stderr 的自由文本，
    「全部闸门绿」实为「N 道通过 + M 道从未运行」不可见（本仓实测 8/13 道
    off —— 与本仓立身要消灭的假绿同形）。
    """
    print("OFF: %s" % notice)
    _maybe_hint()
    return 0


def fatal(msg):
    """配置 / 环境坏：FATAL + 退 2。"""
    print("FATAL: %s" % msg, file=sys.stderr)
    return 2


def load_spec(path):
    """读 JSON 规格，返回 (spec, 错误句)。错误句非 None ⇒ 调用方 `fatal()`。

    返回错误而不是 raise：调用方要把旋钮名 / 路径放进自己的 FATAL 措辞。
    """
    import i18n                                          # noqa: PLC0415
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as e:
        return None, i18n.M("gate.spec_unreadable", path=path, error=e)


def finish(name, problems, ok):
    """问题循环 + OK 行 —— rc 契约（1 = 发现问题 / 0 = 绿）的唯一产地。"""
    import i18n                                          # noqa: PLC0415
    if problems:
        print(i18n.M("gate.problems_header",
                     name=name, count=len(problems)), file=sys.stderr)
        for p in problems:
            print("  · " + p, file=sys.stderr)
        _maybe_hint()
        return 1
    print(ok)
    _maybe_hint()
    return 0


def _maybe_hint():
    """把 env 提示打到 stderr（**绝不进 stdout** —— 那里有机器契约）。

    `REFLECT_ENV_HINT=off` 可整体关闭（本仓「不喜欢提示的仓」的出口；
    提示本身是**人性化**，不是判据）。
    """
    if os.environ.get("REFLECT_ENV_HINT", "").strip().lower() == "off":
        return
    h = env_hint()
    if h:
        print("ℹ %s" % h, file=sys.stderr)


def env_carrier():
    """仓里的 Einfacht.env 载体路径（钩子目录优先、仓库根次之），没有 ⇒ None。"""
    name = (os.environ.get("REFLECT_ENV_FILE", "Einfacht.env").strip()
            or "Einfacht.env")
    for d in (repo("reflect-hooks"), repo()):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def gate_knobs(module=None):
    """调用方模块声明的 `GATE = meta(…, knobs=…)`（拿不到 ⇒ 空）。

    让 `env_hint()` 不必每个入口手写旋钮名 —— 声明已经有一份（单一产地）。
    """
    import sys as _sys                                   # noqa: PLC0415
    mod = module if module is not None else _sys.modules.get("__main__")
    decl = getattr(mod, "GATE", None)
    if isinstance(decl, dict):
        return tuple(decl.get("knobs") or ())
    return ()


def env_hint(consumed=(), module=None):
    """**人性化提示**：喂了 env 的入口，在「带了 env 却没生效」时该怎么跑。

    `consumed` = 这个入口实际读的旋钮名（如 `("REFLECT_FACTS",)`）。
    返回一行提示字符串，或 None（无需提示）。

    什么时候提示（三类，都只在对用户**有帮助**时出现）：

      1. 仓里**有** Einfacht.env，但本轮进程**一个旋钮都没设**（`consumed`
         全不在环境里）—— 典型的手工裸跑：`python3 zreflect/check_x.py`
         ⇒ 判据全部回落默认名，结果可能与钩子语境不同，而且**没有任何东西
         会告诉用户**（issue #20② / #15 都栽在这上面）。
      2. 仓里**有** Einfacht.env 且当前设置与它**不一致**？—— 不查（要看值
         才能判，而值依赖 shell 语义）；只查「有没有设」，保持判据廉价可靠。
      3. 仓里**没有** Einfacht.env ⇒ **不提示**（这类仓裸跑是正常用法，提示
         只会变成噪音 —— 本仓「会误报的闸门最终被整闸关掉」的教训）。

    提示语集中在这里（一处措辞），各入口调它 —— 不再各写一份。
    """
    carrier = env_carrier()
    if not carrier:
        return None                      # 无载体的仓：裸跑是正常用法，不吵
    if not consumed:
        consumed = gate_knobs(module)     # 声明里的旋钮清单（零手写）
    if not consumed:
        return None
    if any(os.environ.get(k, "").strip() for k in consumed):
        return None                      # 至少设了一个旋钮 ⇒ 认为是有意配置
    rel = os.path.relpath(carrier, GATE_REPO)
    import i18n                                          # noqa: PLC0415
    return i18n.M("gate.env_hint", file=rel)


def meta(name, desc, knobs=(), name_dependent=False, runs_at="commit",
         off_reason=None):
    """闸门声明行（registry 的 ast 提取目标）：名字 + 一句话 + 消费的旋钮。

    声明即登记 —— 手写名录会漂，这里只许写事实。

    · `name_dependent=True` 标给「默认输入被换名自证改名」的闸门
      （gates-selftest 的跨仓库节里必须红的那批）：标了会被两头拦 ——
      夹具要求它真红，registry.problems 要求它真消费改名的默认名。
    · `runs_at`（C1）**正面声明频率**：`"commit"`（每次提交跑，进 hooks /
      CI）或 `"start-of-work"`（开工前手动跑 —— doctor 那种「查会死的东西」，
      挂 pre-commit 频率错）。此前频率只能靠「文件名不叫 check_」这种**否定式
      命名意外**表达，且执行面 glob 与它无关 ⇒ 改个名就把 doctor 变成每次
      提交探测活进程的闸门，无人拦。现在频率是声明里的一个字段，执行面
      （gate.run_phase）按它过滤 —— 名字不再是承重的。

    registry 从这些声明派生：执行清单（按 runs_at 过滤）、叙述
    （AUTO:GATES）、红名单、自证清单。名字只用于 `check_*.py` 的文件约定
    （描述性），不再承载语义。
    """
    return {"name": name, "desc": desc, "knobs": tuple(knobs),
            "name_dependent": bool(name_dependent),
            "runs_at": str(runs_at),
            # `off_reason`（第 12 轮）：本闸门**为什么会未启用**。会调 `off()`
            # 的闸门必须写 —— 否则「off」就没有理由，「永久 off 的闸门」与
            # 「本仓不用这套机制」不可区分（本仓真的有过 8/13 道 off 而「全绿」
            # 不可见的历史）。理由必须 ≥8 字（同 `PINNED:` 的纪律）。
            "off_reason": (None if off_reason is None else str(off_reason))}


def module_meta(name, desc, selftest=True):
    """平台模块声明行（C5）：registry 的 ast 提取目标。

    闸门用 `GATE = meta(…)` 声明；**平台模块**（gate / runner / knobs /
    registry / guard / ledger / render / facts …）用 `MODULE = module_meta(…)`
    声明自己的存在与「有没有自证义务」。此前「该有自证」只能靠**文本猜测**
    （扫 `_cases` 字面量）——「一个模块该有自证却没写」无人问；现在它是声明里
    的一个字段：`selftest=True` ⇒ registry 要求它真能 `--selftest` 且被实跑。
    """
    return {"name": name, "desc": desc, "selftest": bool(selftest)}


def raises(fn):
    """「该报错的必须报错」—— 反向断言用。返回 True 表示它确实报了 SystemExit。"""
    try:
        fn()
    except SystemExit:
        return True
    return False



def _ast_for(fname):
    """整文件 AST（按文件名缓存）。读不到 / 解析不了 ⇒ False（缓存负结果）。"""
    import ast as _ast                                   # noqa: PLC0415
    import linecache                                     # noqa: PLC0415
    tree = _AST_CACHE.get((fname,))
    if tree is not None:
        return tree
    try:
        tree = _ast.parse("".join(linecache.getlines(fname)))
    except (OSError, SyntaxError):
        tree = False
    _AST_CACHE[(fname,)] = tree
    return tree


def _lambda_nodes(tree, lineno):
    """起始行 == lineno 的**全部** Lambda 节点（按 col_offset 升序）。

    ⚠️ 为什么返回列表而不是单个：**同一行里可以有多条 lambda**（`return
    [("a", lambda: …), ("b", lambda: …)]` 全在一行）—— 这时 code object 的
    `co_firstlineno` 相同、`co_positions()` 也只给外层位置，**无法区分**是哪
    一条。取 col_offset 最小的那条会让同行的其它断言全部按第一条判定
    （实测踩到：`lambda: 1 == 2` 被同行的 `lambda: … or True` 带累判成恒真）。

    因此返回同行全部候选；调用方对**每一条**都扫一遍，任一条恒真即报 ——
    「同行内任一条断言恒真」本来就该被抓，多报不算误伤。
    """
    import ast as _ast                                   # noqa: PLC0415
    nodes = [n for n in _ast.walk(tree)
             if isinstance(n, _ast.Lambda) and n.lineno == lineno]
    return sorted(nodes, key=lambda n: n.col_offset)


def _const_truthy(node):
    """这个常量节点恒为真吗（`or True` / `or 1` 的右操作数形状）。"""
    import ast as _ast                                   # noqa: PLC0415
    if not isinstance(node, _ast.Constant) or node.value is None:
        return False
    return node.value is not False and bool(node.value) is True


def _const_falsy(node):
    """这个常量节点恒为假吗（`and False` / `and 0` 的右操作数形状）。"""
    import ast as _ast                                   # noqa: PLC0415
    if not isinstance(node, _ast.Constant) or node.value is None:
        return False
    return node.value is False or node.value == 0


def _short_circuit_reason(node):
    """这个 AST 节点构成恒真短路吗 ⇒ 原因消息；否则 None。"""
    import ast as _ast                                   # noqa: PLC0415
    import i18n                                          # noqa: PLC0415
    if isinstance(node, _ast.BoolOp):
        if isinstance(node.op, _ast.Or) and any(
                _const_truthy(o) for o in node.values):
            return i18n.M("gate.never_falsifiable_or")
        if isinstance(node.op, _ast.And) and any(
                _const_falsy(o) for o in node.values):
            return i18n.M("gate.never_falsifiable_and")
    if isinstance(node, _ast.Compare) and len(node.comparators) == 1:
        left, right = node.left, node.comparators[0]
        # 排除裸函数调用两次的**合法**纯函数性检验
        # （`render_gates(gs) == render_gates(gs)` 证明渲染确定性）。
        if isinstance(left, _ast.Call) and isinstance(right, _ast.Call):
            return None
        if _ast.dump(left) == _ast.dump(right) and isinstance(
                node.ops[0], (_ast.Eq, _ast.LtE, _ast.GtE)):
            return i18n.M("gate.never_falsifiable_self_compare")
    return None


def never_falsifiable(fn):
    """**恒真断言探测**（issue #23）：这条自证用例有证伪能力吗？

    下游实测的事故：一条 `or True` 的断言在 `--selftest` 里永远是 PASS ——
    `gates-selftest` 判的是「返回 0 + 打摘要行」，真断言与恒真断言在这个面上
    完全同形。`AGENTS.md` 纪律 4 说「断言要能证伪」，但此前没有机器判据。

    判据（AST，零执行、零副作用）：**整文件解析 + 按 co_firstlineno 定位**
    lambda 节点（不用 inspect.getsourcelines —— 它对列表里的 lambda 只给首行，
    重建脆弱，实测三次失明）。找到节点后扫恒真短路：

      · `or <真值常量>` / `and <假值常量>` —— 布尔被常量短路，永远 PASS/fail；
      · `x == x` 型自我比较（**排除**裸函数调用两次的合法纯函数性检验）。

    返回原因字符串（不可证伪）或 None（看起来有牙）。

    诚实边界：静态形状判据 —— 抓得到显式短路与自我比较，抓不到更隐蔽的恒真
    （同一变量换写法）。更强的保证是变异测试（每条断言注入破坏器），代价过大；
    见 issue #23 的讨论。本判据的价值：把已知的几种无意识写法从「人工复查才
    发现」变成「自证当场红」。
    """
    import ast as _ast                                   # noqa: PLC0415
    import i18n                                          # noqa: PLC0415
    code = getattr(fn, "__code__", None)
    if code is None:
        return None                                      # 非 Python 函数 ⇒ 不猜
    tree = _ast_for(code.co_filename)
    if not tree:
        return None                                      # 读不到 / 解析不了 ⇒ 不猜
    nodes = _lambda_nodes(tree, code.co_firstlineno)
    if not nodes:
        return None                                      # 定位不到 ⇒ 不猜
    if len(nodes) > 1:
        # 同一行有多条 lambda：code object 无法告诉我们是哪一条（co_firstlineno
        # 相同、co_positions 只给外层位置）。**不确定就不猜** —— 与「读不到就
        # 明说」同一条纪律：这里宁可漏报也不误伤（本仓 99% 的断言都独占一行，
        # 这个退化只影响把多条断言挤一行的写法）。
        return None
    # ⚠️ **纯委托**（lambda 体就是一次 Call）⇒ 断言逻辑住在被调用函数里，
    # 本判据**看不见**它。此前这种情况返回 None（与「扫过且干净」不可区分），
    # 于是「提取成 helper」就成了关掉恒真检测的合法手段（实测：helper 改成
    # `return True` 后自证 26 PASS / 0 FAIL 全绿）。
    # 现在把它**明说成未审计**，而不是假装干净 —— 与「读不到就明说」同一条纪律。
    # 只看「委托给**自己写的**函数」：`any(... for …)` / `all(...)` / `bool(x)`
    # 这类内建是**在 lambda 里内联逻辑**，不是委托 —— 它们的生成器/实参就在
    # 这个 AST 里，恒真检测照样能扫（把内建也判成委托会误伤一半的断言，
    # 实测 6 条假阳性）。
    _BUILTIN_OK = {"any", "all", "bool", "len", "sorted", "sum", "min", "max",
                   "isinstance", "getattr", "hasattr", "str", "int", "set",
                   "list", "tuple", "dict", "repr"}
    for node in nodes:
        if isinstance(node.body, _ast.Call):
            f = node.body.func
            fname = getattr(f, "id", None) or getattr(f, "attr", None)
            if fname not in _BUILTIN_OK:
                return i18n.M("gate.never_falsifiable_delegated")
        for n in _ast.walk(node):
            reason = _short_circuit_reason(n)
            if reason:
                return reason
    return None


def _is_delegated(why):
    """这条 `why` 是不是「委托断言」判据（而不是恒真短路）。

    ⚠️ 必须看 `.code`，不能看 `str(why)`：`why` 是一个 `Message`，它的 str 值
    已被**当前语言**渲染 —— 在 `zh` 下变成中文，按英文 code 匹配就永远落空，
    于是委托断言被当成恒真短路报出去（实测：`KeyError: 'label'`）。
    """
    return getattr(why, "code", None) == "gate.never_falsifiable_delegated"


def selftest(name, cases):
    """跑三档用例。每个 case = (标签, callable) -> bool。

    必须写齐三类：
      ① 正常不报（阳性对照 —— 否则「总是报错」也能骗过自证）
      ② 该报的必须报（反向断言 —— 否则这个检查器可能是装饰）
      ③ 空输入必须报（零值守卫）
    """
    import i18n                                          # noqa: PLC0415
    if not cases:
        # 0/0 洞（本文件开头记载的第三种事故）：空用例清单的自证什么都没查，
        # 却打印「0 PASS / 0 FAIL」绿着退场 —— runner 的 grep 照样认它。
        # 空清单是写自证时的形状错误，当场响，不许绿。
        raise SystemExit("FATAL: %s"
                         % i18n.M("gate.selftest_empty_cases", name=name))
    bad = 0
    delegated = 0
    for label, fn in cases:
        # issue #23：恒真断言探测 —— 一条 `or True` 的断言与真断言
        # 在「返回 0 + 打摘要行」这个面上同形，必须单独判。
        why = never_falsifiable(fn)
        # 「委托」是可接受但**必须可见**的状态：断言体在 helper 里（搭临时夹具
        # 的场景没法内联）。允许它，但下一行打成 `note |`（机器可读），
        # 并在摘要里单列计数 —— 不许静默当干净（此前返回 None，与「扫过且
        # 干净」不可区分，于是提取 helper 就成了关掉恒真检测的合法手段）。
        if why and _is_delegated(why):
            delegated += 1
            print("note | %s | delegated" % label)
            why = None
        if why:
            # `fail | ` 是自证机器行前缀 —— 发射点字面量，不进语言包
            print("fail | %s" % i18n.M("gate.case_unfalsifiable",
                                       label=label, why=why))
            bad += 1
            continue
        try:
            ok = bool(fn())
        except SystemExit as e:
            print("fail | %s" % i18n.M("gate.case_unexpected_systemexit",
                                       label=label, error=e))
            bad += 1
            continue
        except Exception as e:                      # noqa: BLE001
            print("fail | %s" % i18n.M("gate.case_raised",
                                       label=label, error=e))
            bad += 1
            continue
        print("%s | %s" % ("PASS" if ok else "fail", label))
        bad += 0 if ok else 1
    # 人读摘要行。`=== ` 前缀与收尾 ` ===` 都是机器行形状 —— 两侧留在
    # **发射点**字面量（语言包值不许以 `^===` 开头，见 i18n._validate）。
    if delegated:
        # 摘要里**单列**：委托断言有多少条。它们不是失败，但也不是「扫过且干净」
        # —— 静默把它们算进 PASS 就是本仓最痛恨的假绿。
        print("=== %s ===" % i18n.M("gate.selftest_delegated",
                                    name=name, count=delegated))
    print("=== %s ===" % i18n.M("gate.selftest_summary",
                                name=name, passed=len(cases) - bad,
                                failed=bad))
    # 机器摘要行（issue #3 ③）：与检查器名无关的固定格式，runner/CI 直接
    # grep；gates-selftest.sh 会校验每个自证都有这一行（缺了 ⇒ 红）。
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def activate_or_fatal():
    """进程级语言包激活点。成功返回 0；装配失败打印 FATAL 并返回 2。

    **必须在 `--selftest` 之前调用**（issue #26 复盘）：此前 `main_selftest_or`
    先判 `--selftest` 再 `activate()`，于是 `REFLECT_LANG=zh <gate> --selftest`
    把消息按 null 包渲染成裸 code，而 `REFLECT_LANG=de <gate> --selftest` 对一个
    **不存在的包静默 rc=0** —— 与「设了但包不在 ⇒ FATAL rc 2，不静默回落」直接
    矛盾（实测：render / ledger / runner / registry 四条入口全中）。

    收起成函数是为了让**不走 `main_selftest_or` 的入口**（render/ledger 的
    `_selftest()`、registry 的 `__main__`、gate 自己的 `__main__`）不必各抄一份
    activate+FATAL（此前 registry 抄了一份，gate 自己那份干脆没有 FATAL，
    直接裸 traceback 退 1）。
    """
    import i18n                                          # noqa: PLC0415
    try:
        i18n.activate()
    except Exception as e:                               # noqa: BLE001
        # 装配失败时进程默认仍是上一档 `Catalog`（通常是 null 包）⇒ M() 照样
        # 渲染得出来（`MissingPack` 的 `str()` 本身就是 null 形状的 code）。
        print("FATAL: %s" % i18n.M("gate.pack_assembly_failed", error=e),
              file=sys.stderr)
        return 2
    return 0


def main_selftest_or(args, name, cases, run):
    """`--selftest` 走自证，否则走 `run(args)`。每个检查器都用它收尾。

    `cases` 可以是清单，也可以是**工厂 callable**（需要搭临时夹具的
    自证 —— ab/locks/pins 体例 —— 传函数，由这里调用）。

    **这里是语言包的进程级激活点**（issue #26）：`REFLECT_LANG` 未设 ⇒ null 包
    （本体零语言）；设了但包不在 ⇒ `MissingPack` ⇒ FATAL rc 2（不做「没装就
    回落」）。每个闸门都经这里 ⇒ 一处接线，全部受益。激活**先于** `--selftest`
    分流，理由见 `activate_or_fatal`。
    """
    rc = activate_or_fatal()
    if rc:
        return rc
    if "--selftest" in args:
        return selftest(name, cases() if callable(cases) else cases)
    return run([a for a in args if a != "--selftest"])


def default_runner(f, repo_root=None):
    """默认执行器：跑一个闸门文件，返回 `(rc, 合并后的输出)`。

    ⚠️ **stdout 与 stderr 必须合并**：本仓约定「问题行统一 stderr」，于是
    rc=2 的闸门 stdout 可能是**空的**（原因全在 stderr）。只回 `p.stdout`
    ⇒ 聚合方拿到 (2, "")，既不知道哪个文件坏了也不知道为什么
    （实测：`REFLECT_SNAPSHOT_ROOT=/nonexistent` ⇒ stdout=''）。
    """
    import subprocess                                    # noqa: PLC0415
    p = subprocess.run([sys.executable, f], capture_output=True, text=True,
                       cwd=repo_root or GATE_REPO)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_phase(phase, gates, runner=None, repo_root=None):
    """按相位跑一组闸门并**聚合 ran / off / failed**（C1+C2 的执行面）。

    这是 hooks / CI / runner 的**唯一执行入口** —— 取代此前散在 6 处的
    `for g in zreflect/check_*.py` glob。`gates` = registry 派生的
    (file, runs_at) 清单（调用方按 `phase` 过滤，或传全集由这里过滤）。

    为什么聚合三档而不是只看 rc：off 与「跑过且通过」rc 都是 0，只看 rc
    会把「没跑」算进「绿」（本仓实测 8/13 道 off）。这里读子进程 stdout 的
    `OFF:` 机器标记把 off 单列，于是「全绿」永远附带「其中 N 道 off（没查）」。
    `runner` 可注入（自证用假执行器）。

    返回 `{ran, off, failed, fatal, off_list, fail_list, fatal_list}`。

    ⚠️ **rc=2 与 rc=1 必须分开**：本平台的 rc 契约明写「配置性失败 ≠ 检查失败，
    混进 1 会让『发现问题』与『配置坏了』不可区分」。此前这里把所有 rc≠0 塞进
    同一个 `failed`，聚合结果看不出「有三道闸门报了真实问题」还是「有一道闸门
    配置坏了」—— 修复动作完全不同（改配置 vs 修问题）。
    """
    run = runner or (lambda f: default_runner(f, repo_root))
    res = {"ran": 0, "off": 0, "failed": 0, "fatal": 0, "error": 0,
           "off_list": [], "fail_list": [], "fatal_list": [], "error_list": []}
    for item in gates:
        f = item["file"] if isinstance(item, dict) else item
        if isinstance(item, dict) and item.get("runs_at") not in (None, phase):
            continue
        rc, out = run(f)
        if rc == 2:
            # 配置 / 环境坏：不是「检查发现的问题」，单列（见 docstring）
            res["fatal"] += 1
            res["fatal_list"].append(f)
        elif rc < 0 or rc > 2:
            # ⚠️ rc<0（被信号杀掉）/ rc>2（脚本用了未约定的码）既不是「判据红」
            # 也不是「配置坏」——它们是**执行器层面坏了**。此前一律塞进 failed，
            # 于是「闸门报了个问题」与「闸门被 SIGKILL」不可区分（review 实测
            # rc=3 / rc=-9 都落进 failed）。单列成 error 档。
            res["error"] += 1
            res["error_list"].append(f)
        elif rc != 0:
            res["failed"] += 1
            res["fail_list"].append(f)
        elif any(ln.startswith("OFF:") for ln in (out or "").splitlines()):
            res["off"] += 1
            res["off_list"].append(f)
        else:
            res["ran"] += 1
    return res


MODULE = module_meta("闸门平台", "rc 契约 + 零值守卫 + 三档自证 + 相位执行器（提供 selftest，自己不消费）", selftest=False)


if __name__ == "__main__":
    import i18n                                          # noqa: PLC0415
    # 此前这里裸 `i18n.activate()`：包不在 ⇒ MissingPack **traceback rc=1**，
    # 而不是 rc 契约的 FATAL rc=2（实测踩到）。走同一个激活入口。
    rc = activate_or_fatal()
    if rc:
        sys.exit(rc)
    print(i18n.M("gate.platform_root", root=GATE_REPO))
    print(i18n.M("gate.platform_usage"))
    sys.exit(0)
