# Einfacht

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

每一句「现在如此」都必须可以被复跑。Einfacht 是让这句话在一个 agent 参与开发的
仓里成立的装置：五个载体盛放「下一轮不该靠猜」的东西，而一条断言一旦漂离了能
证明它的那个东西，闸门就会报出来。

**语言：** [English](README.md) · **简体中文**（本文件） · [Deutsch](README.de.md)

## 它盛放什么

agent 的上下文随会话消失。下一轮从冷的开始，能活下来的只有写下来的部分。
Einfacht 让那部分**可验证**，并把每一类陈述的居所钉死：

| 载体 | 盛放 | 谁证明它 |
|---|---|---|
| `STATE.md` | 此刻为真的东西：测出来的数字 | 从台账渲染；`facts.py --check` 逐字节比对 |
| `PRINCIPLES.md` | 规矩 | 每行带一条真能跑的命令（`check_facts_replay`） |
| `questions/` | 还没解决的东西 | 每条未决悬案必须带一个能给出两种可区分结果的 settler |
| `HISTORY.md` | 一条规矩为什么存在 | 必须存在，且必须不在任何扫描面上（`check_history`） |
| `AGENTS.md` | 去哪找、跑什么 | 设计上就是散文；它做路由，不做断言 |

其中四个受判据管；第五个是走进那四个的地图。一条陈述若哪个都装不下，就是
这套装置存在的理由本身。

承重的是**最后一列**。没有判据的载体只是一个文件夹；`STATE.md` 可靠不是因为
数字被写在那里，而是因为一次全新渲染必须与它逐字节相等，且每个数字都带着一条
能把它重新打印出来的命令。其余三个是同一形状：一条规矩是一行每次提交都真跑
命令的表格行；一个悬案是一个两种结果带不同退出码的 settler；而 `HISTORY.md`
从**反面**守着 —— 判据证明它**不被扫**，否则「当时如此」的行会被当成活状态，
永久变红。

## 用它

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <你的仓>/
cd <你的仓>
python3 zreflect/facts.py --init                  # 生成骨架文档，不覆盖已有文件
python3 zreflect/facts.py                         # 量一遍
python3 zreflect/facts.py --render-doc            # 渲染状态文档
python3 reflect-hooks/install.py --chain          # 链进你已有的 git 钩子
```

`--init` 会写出骨架文档（`STATE.md`、`PRINCIPLES.md`、`AGENTS.md`、`README.md`）、
`retractions.json` 与 `questions/`。登记表默认值直接匹配这套单 README 骨架；
需要自定义旋钮的仓库可在仓根放一份可选的 `knobs.json`（钩子、CLI 与 CI 读同一份）：

```json
{
  "REFLECT_MEASURE_MODULE": "my_measure"
}
```

它自身不需要安装步骤：就是几个脚本加一份配置文件，`install.py --chain` 把它的
行加进仓里已有的钩子，而不是替换掉它们。不往仓外写任何东西。

之后的用法 —— 旋钮、输出、每个退出码是什么意思 —— 见
[skills/einfacht/SKILL.md](skills/einfacht/SKILL.md)，那是唯一入口。

## 什么时候跑什么

```
开工前      facts.py --check           文档与台账一致
            doctor.py                  活性：那些服务还活着吗
提交时      registry.py --run commit   全部 commit 相位闸门，聚合上报
                                       （ran / off / failed / fatal 分列；
                                        off 不算通过）
推送时      同一判据，外加三语 README 同批更新
```

每道闸门在自己的 `GATE = meta(...)` 声明行里写相位；名录从声明发现，从不 glob。
能把自己关掉的闸门必须说明理由，它的 `OFF:` 行会被报出来，而不计入绿。

三个相位差的是**频率**，不是严格程度，而频率是声明字段而不是命名约定。
`doctor.py` 查的是会死的东西 —— 重启过的机器、消失的容器、被别人占掉的端口
—— 所以它在提交频率上是错的、在开工前是对的。其余的都便宜到能每次提交跑，
而这正是它们可信的唯一理由：一道「谁记得谁跑」的判据，报出的是那个人的记性。

## 一道闸门要先能红，才值得信

每道闸门自带 `--selftest`。跑它证明里面的判据还能红；一条只会通过的判据被当作
装饰，不是证据。`harness.py` 跑全部，然后把每个名字类旋钮换成一个别的名字再跑
一遍 —— 依赖本仓文件名的判据，到了你的仓里就不是判据。

由此有两个后果，都是付过代价换来的。第一，判据必须能说出它**拒了什么**：只报
「发现若干问题」而不给文件与行号，等于让读者去猜，而猜测正是这套装置反对的事。
第二，「明显能用」的闸门也必须自证 —— 明显能用的那些，恰恰是判据悄悄变成恒真
比较的那些，所以 `harness.py` 不接受一道自身证明无法变红的闸门。

## 为什么散文被限在一处

散文会烂：一句话写下时是真的，代码动了之后它看起来还是真的，而没有任何东西拿它
和别的东西对账。所以叙述只有一个居所，它的来历记在
[HISTORY.md](HISTORY.md)。

## 文档地图

主文档是 `STATE.md`（数字）、`PRINCIPLES.md`（规矩）、`HISTORY.md`（来历）、
`questions/`（未决）与 `AGENTS.md`（路由）。可运行示范在
[examples/README.md](examples/README.md)；语言包见
[docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md)。给 agent 的指令是
[skills/einfacht/SKILL.md](skills/einfacht/SKILL.md)。

本文件 README.zh.md 是三语组的简体中文成员 —— 三语组：
[README.md](README.md) · [README.de.md](README.de.md) —— 三份被当作同一条断言来查。

## License

MIT
