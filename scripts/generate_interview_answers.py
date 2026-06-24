#!/usr/bin/env python3
"""
Generate 200 interview answer markdown files from docs/interview_questions_agent_dev.md.

Loads substantive answer content from interview_answer_bank.py (sibling module).

Usage:
    python scripts/generate_interview_answers.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_MD = ROOT / "docs" / "interview_questions_agent_dev.md"
ANSWERS_DIR = ROOT / "docs" / "interview" / "answers"
README_PATH = ROOT / "docs" / "interview" / "README.md"


@dataclass
class Question:
    id: int
    category: str
    difficulty: int  # 1-3 stars
    text: str
    slug: str


# ── Slug map (short Chinese label per question) ──────────────────────────────

SLUGS: dict[int, str] = {
    1: "项目介绍", 2: "运行时评估必要性", 3: "过程与结果质量", 4: "六维选型", 5: "与观测工具对比",
    6: "单调性基准解释", 7: "Wiki-Agent角色", 8: "为何选LangGraph", 9: "为何选FastAPI",
    10: "LLM选型与可比性", 11: "Milvus选型", 12: "Vue前端选型",
    13: "轨迹驱动评估", 14: "评估边界与数据流", 15: "分布式轨迹汇聚", 16: "ActionType粒度",
    17: "tool-call-result分离", 18: "think-node-decision", 19: "evidence与retrieval",
    20: "第三方框架适配", 21: "context与Memory", 22: "轨迹token超限",
    23: "多轮与子任务", 24: "HITL轨迹记录",
    25: "两套collector对比", 26: "finish与离线缓冲", 27: "EVAL_BATCH_SIZE",
    28: "上报失败重试", 29: "线程安全", 30: "低侵入埋点",
    31: "LangGraph包装", 32: "Callback映射", 33: "LLM-Proxy幂等",
    34: "手动collector上报", 35: "显式vs自动埋点", 36: "轨迹不完整",
    37: "伪造轨迹检测", 38: "observation序列化", 39: "step-number语义",
    40: "评估工作流", 41: "评估图State", 42: "串行图与并行gather",
    43: "EVAL_PARALLEL切换", 44: "State合并冲突", 45: "真并行State改造",
    46: "Wiki-Agent节点", 47: "AsyncSqliteSaver", 48: "decide-HITL",
    49: "知识提取流程", 50: "StateGraph区别", 51: "条件边", 52: "Subgraph",
    53: "interrupt机制", 54: "LLM-as-Judge", 55: "temperature为零",
    56: "自评偏见", 57: "JSON-fallback-50分", 58: "JSON抽取漏洞",
    59: "Structured-Output", 60: "consensus-std-score",
    61: "Planning-prompt", 62: "中英文prompt", 63: "few-shot", 64: "分数与feedback不一致",
    65: "Prompt-Injection", 66: "prompt版本管理", 67: "token成本", 68: "成本追踪",
    69: "并行优化瓶颈", 70: "评估缓存", 71: "部分维度复用",
    72: "Planning四子维", 73: "Planning权重", 74: "无plan零分", 75: "granularity定义",
    76: "Tactical排除plan", 77: "Tactical例子", 78: "工具错Tactical打分",
    79: "ToolUse三子维", 80: "参数JSON错误", 81: "result-utilization",
    82: "Memory三子维", 83: "key-facts可靠性", 84: "无memory动作", 85: "长短期记忆",
    86: "无replan满分", 87: "trigger-appropriateness", 88: "failure与replan",
    89: "Replan评估缺口", 90: "Retrieval三子维", 91: "retrieved-docs结构",
    92: "无retrieval零分", 93: "幻觉评估", 94: "coverage低建议",
    95: "六维overall权重", 96: "两级加权", 97: "单维异常零分",
    98: "分块策略", 99: "标题层级", 100: "代码块分块",
    101: "增量索引", 102: "BGE选型", 103: "零向量降级", 104: "Milvus-schema",
    105: "Milvus降级BM25", 106: "RRF公式", 107: "RRF-vs加权", 108: "jieba-BM25",
    109: "path去重", 110: "top-k调参", 111: "record-retrieval",
    112: "检索好生成差", 113: "RAG-ground-truth", 114: "Wiki完整链路",
    115: "Chat-SSE", 116: "SYSTEM-PROMPT", 117: "自动提取", 118: "reject提取",
    119: "CRUD索引同步", 120: "history-rollback", 121: "EvaluationTrace",
    122: "EVAL_AUTO_RUN", 123: "零侵入SDK", 124: "adapter路径",
    125: "LangGraph兼容性", 126: "同步异步节点", 127: "state-diff截断",
    128: "SDK独立安装", 129: "非LangChain接入", 130: "ActionType同步",
    131: "单调性基准", 132: "合成轨迹", 133: "容差0.05", 134: "逆序定位",
    135: "eval-evaluator-accuracy", 136: "真实轨迹补充", 137: "评估准确率",
    138: "多模型benchmark", 139: "POST-evaluations-202", 140: "SSE事件格式",
    141: "SSE-replay", 142: "任务状态机", 143: "PENDING与RUNNING",
    144: "async-session", 145: "SQLite-PostgreSQL", 146: "AUTH_ENABLED",
    147: "双health端点", 148: "10万次日评估", 149: "Celery队列",
    150: "多租户workspace", 151: "评估版本化", 152: "AB测试",
    153: "Judge重试429", 154: "DB一致性", 155: "双索引不一致",
    156: "评估幂等", 157: "PII脱敏", 158: "Wiki-XSS", 159: "WEBHOOK安全",
    160: "平台观测", 161: "Judge监控", 162: "Planning低分排查",
    163: "overall高分争议", 164: "Retrieval零分", 165: "benchmark失败定位",
    166: "Wiki不引用知识库", 167: "Milvus不可用", 168: "Dashboard为空",
    169: "SSE断开恢复", 170: "JSON-parse错误", 171: "extract-tool-calls",
    172: "evaluate-parallel", 173: "instrument-langgraph", 174: "RRF手算",
    175: "新增Safety维", 176: "效率Evaluator", 177: "采样率上报",
    178: "gzip上报", 179: "可执行性子维", 180: "评估diff-API",
    181: "评估流水线2.0", 182: "联邦评估", 183: "在线评估", 184: "MCP封装",
    185: "黄金数据集", 186: "Agent趋势", 187: "Multi-Agent评估",
    188: "可解释与可评估", 189: "RLHF-vs-prompt", 190: "长上下文挑战",
    191: "个人负责模块", 192: "Judge人工不一致", 193: "架构重做", 194: "技术债",
    195: "评估vs Agent优先", 196: "推广轨迹规范", 197: "评估与KPI冲突",
    198: "CI-benchmark", 199: "领域专家协作", 200: "单一数字概括",
}


def parse_questions(md_path: Path) -> list[Question]:
    """Parse numbered questions from the interview questions markdown."""
    text = md_path.read_text(encoding="utf-8")
    current_category = ""
    in_toc = False
    questions: list[Question] = []
    seen_ids: set[int] = set()

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## 附录"):
            break

        if stripped == "## 目录":
            in_toc = True
            continue
        if in_toc:
            if stripped.startswith("## ") and not stripped.startswith("## 目录"):
                in_toc = False
            else:
                continue

        cat_match = re.match(r"^## (\d+)\.\s+(.+)$", stripped)
        if cat_match:
            current_category = cat_match.group(2).strip()
            continue

        q_match = re.match(r"^(\d+)\.\s+(?:\*\*)?([★]+)?(?:\*\*)?\s*(.+)$", stripped)
        if not q_match:
            continue

        qtext = q_match.group(3).strip()
        if re.search(r"\]\(#", qtext):  # skip TOC links
            continue

        qid = int(q_match.group(1))
        if qid in seen_ids or qid < 1 or qid > 200:
            continue

        stars_raw = q_match.group(2) or ""
        qtext = re.sub(r"^\*\*|\*\*$", "", qtext).strip()

        difficulty = min(3, max(1, len(stars_raw) + 1 if stars_raw else 1))
        slug = SLUGS.get(qid, f"Q{qid}")
        seen_ids.add(qid)
        questions.append(
            Question(id=qid, category=current_category, difficulty=difficulty, text=qtext, slug=slug)
        )

    questions.sort(key=lambda q: q.id)
    if len(questions) != 200:
        raise ValueError(f"Expected 200 questions, parsed {len(questions)}")
    return questions


def _stars(n: int) -> str:
    return "★" * n


def _adjacent_links(qid: int) -> str:
    links = []
    if qid > 1:
        prev_slug = SLUGS.get(qid - 1, f"Q{qid-1}")
        links.append(f"- [Q{qid-1:03d}](../answers/Q{qid-1:03d}-{prev_slug}.md)")
    if qid < 200:
        nxt_slug = SLUGS.get(qid + 1, f"Q{qid+1}")
        links.append(f"- [Q{qid+1:03d}](../answers/Q{qid+1:03d}-{nxt_slug}.md)")
    return "\n".join(links)


def _load_answer_bank() -> dict[int, dict]:
    """Load ANSWER_BANK from sibling module interview_answer_bank.py."""
    import importlib.util

    bank_path = Path(__file__).resolve().parent / "interview_answer_bank.py"
    spec = importlib.util.spec_from_file_location("interview_answer_bank", bank_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load answer bank from {bank_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ANSWER_BANK


def _get_answer_bank() -> dict[int, dict]:
    return _load_answer_bank()


def render_answer_md(q: Question) -> str:
    bank = _get_answer_bank()
    data = bank[q.id]
    stars = _stars(q.difficulty)

    followups = "\n\n".join(
        f"**Q: {fq}**\n\nA: {fa}" for fq, fa in data["followups"]
    )
    points = "\n".join(f"- {p}" for p in data["points"])
    refs = "\n".join(f"- `{p}`" for p in data["code_refs"])

    return f"""# Q{q.id}: {q.text}

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q{q.id:03d} |
| 分类 | {q.category} |
| 难度 | {stars} |

## 问题

{q.text}

## 参考答案

{data["reference"]}

## 代码依据

{refs}

## 回答要点

{points}

## 常见追问

{followups}

## 相关题目

{_adjacent_links(q.id)}
"""


def generate_readme(questions: list[Question]) -> str:
    lines = [
        "# Agent 开发工程师面试题 — 参考答案索引",
        "",
        "> 本目录由 `scripts/generate_interview_answers.py` 自动生成。",
        "> 问题来源：[interview_questions_agent_dev.md](../interview_questions_agent_dev.md)",
        "",
        f"共 **{len(questions)}** 道题，按分类索引如下。",
        "",
    ]
    current_cat = None
    for q in questions:
        if q.category != current_cat:
            current_cat = q.category
            lines.extend(["", f"## {current_cat}", ""])
        stars = _stars(q.difficulty)
        fname = f"Q{q.id:03d}-{q.slug}.md"
        lines.append(f"- [{stars} Q{q.id:03d}](answers/{fname}) — {q.text}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not QUESTIONS_MD.exists():
        print(f"ERROR: {QUESTIONS_MD} not found", file=sys.stderr)
        return 1

    questions = parse_questions(QUESTIONS_MD)
    bank = _get_answer_bank()
    missing = [q.id for q in questions if q.id not in bank]
    if missing:
        print(f"ERROR: Missing answers for: {missing[:10]}... ({len(missing)} total)", file=sys.stderr)
        return 1

    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    for q in questions:
        path = ANSWERS_DIR / f"Q{q.id:03d}-{q.slug}.md"
        path.write_text(render_answer_md(q), encoding="utf-8")

    README_PATH.parent.mkdir(parents=True, exist_ok=True)
    README_PATH.write_text(generate_readme(questions), encoding="utf-8")

    print(f"Generated {len(questions)} answer files in {ANSWERS_DIR}")
    print(f"Index: {README_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
