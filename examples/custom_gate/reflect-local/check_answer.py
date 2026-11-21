import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import main_selftest_or, meta


def correct(value):
    return isinstance(value, int) and not isinstance(value, bool) and value == 42


def run(argv):
    value = int(argv[0]) if argv else 42
    passed = correct(value)
    print("answer-ok" if passed else "DRIFT: answer")
    return 0 if passed else 1


def _cases():
    return [
        ("answer.ok", lambda: correct(42)),
        ("★ answer.wrong", lambda: not correct(41)),
        ("★ answer.empty", lambda: not correct(None)),
    ]


GATE = meta("Answer gate", "demonstrate declaration-based registration in a custom phase", runs_at="lab")


if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "check_answer", _cases, run))
