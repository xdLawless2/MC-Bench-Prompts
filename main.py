#!/usr/bin/env python3
"""
generate_mcbench_prompts.py

• Pretty CLI via Rich
• Optional --idea "text"  (or just let it ask interactively)
• Requires:
      pip install --upgrade openai rich regex
• Needs env var OPENAI_API_KEY
"""

import os, regex as re, textwrap, argparse
from collections import Counter
from openai import OpenAI
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

# ───────────────────  CLI  ─────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate MCbench prompts")
parser.add_argument("--idea", "-i", help="Seed idea to weave into prompts", default=None)
parser.add_argument("--temp", "-t",  help="Sampling temperature (keep at 1 for 'o' series models)", type=float, default=1)
args  = parser.parse_args()
idea  = args.idea

console = Console()

if idea is None:
    idea = Prompt.ask("Enter a seed idea to inspire some prompts (leave blank for none)", default="").strip()

# ───────────────────────────────────────────────────────────────────
#  Regex helpers for over-specification
# ───────────────────────────────────────────────────────────────────
NUMERIC   = re.compile(r"\b\d+\b")
SIZING    = re.compile(r"\b(radius|diameter|height|width|depth|×|x)\b", re.I)
COORD     = re.compile(r"\b[xyz]\s*=\s*-?\d+", re.I)
BLOCK_IDS = re.compile(
    r"\b(terracotta|quartz|glass|wool|concrete|prismarine|andesite|stone|"
    r"sandstone|redstone|glowstone|lantern|beacon|piston|cobblestone)\b",
    re.I,
)

def is_over_specified(prompt: str) -> bool:
    return any(r.search(prompt) for r in (NUMERIC, SIZING, COORD, BLOCK_IDS))

# ───────────────────────────────────────────────────────────────────
#  Tag helpers
# ───────────────────────────────────────────────────────────────────
TAGS = {
    "History/Science": {"history", "science"},
    "Myth": {"myth"},
    "Pop": {"pop"},
    "Tech": {"tech"},
    "Arch": {"arch"},
    "Nature": {"nature"},
}
TAG_SUFFIX_RE = re.compile(r"\(([^)]+)\)\s*$")

def extract_tag(prompt: str) -> str | None:
    m = TAG_SUFFIX_RE.search(prompt.lower())
    if not m:
        return None
    key = m.group(1).strip().split("/")[0]
    for canon, keys in TAGS.items():
        if key in keys:
            return canon
    return None

# ─────────────────────────────────────────────────────────────────
#  Build the system prompt
# ───────────────────────────────────────────────────────────────────
idea_clause = ""
if idea:
    idea_clause = textwrap.dedent(f"""
        Human seed idea
        ---------------
        “{idea}”

        Requirement: at least THREE prompts must clearly incorporate or riff on this idea,
        each in a different domain tag (where possible).  Feel free to interpret creatively
        but keep the idea recognisable.
    """)

SYSTEM_PROMPT = textwrap.dedent(f"""
    You are a prompt designer for MCbench (mcbench.ai).

    Objective
    ---------
    Produce TEN Minecraft build prompts that jointly maximise

        G‡ = V×R×S×J×I×(1–O)×C×D
        (V Validity, R Reliability, S Sensitivity, J Judgeability,
         I Iconicity, O Over-specification, C Contextual resonance,
         D Diversity across the batch)

    Domain tags
    -----------
        (History/Science)   – space missions, inventions, historical events
        (Myth)              – legends, religions, literature classics
        (Pop)               – brands, pop culture, modern media
        (Tech)              – gadgets, machines, everyday tech objects
        (Arch)              – architecture, cities, civil engineering
        (Nature)            – natural scenes, phenomena, animals

    Hard rules  (MUST FOLLOW)
    -------------------------
    1  One imperative sentence, ≤ 25 tokens.
    2  NO explicit numbers, dimensions, coordinates, block names, or colours.
    3  Append exactly ONE domain tag from the list in parentheses.
    4  No Markdown, bullets, or quotation marks – raw text only.

    Every tag must appear at least once across the 10 prompts.

    {idea_clause}
""").strip()

# ─────────────────────────────────────────────────────────────────
#  OpenAI call
# ───────────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="o3",
    temperature=args.temp,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": "Generate the ten prompts now."},
    ],
)

raw = response.choices[0].message.content

# ───────────────────────────────────────────────────────────────────
#  Post-process
# ─────────────────────────────────────────────────────────────────
def token_len(s: str) -> int: return len(s.split())

candidates = [line.strip("•*- \t").rstrip()
              for line in raw.splitlines() if line.strip()]

good, seen = [], set()
for cand in candidates:
    tag = extract_tag(cand)
    if not tag or cand.lower() in seen:            continue
    if token_len(cand) > 25:                      continue
    if is_over_specified(cand):                   continue
    good.append(cand)
    seen.add(cand.lower())
    if len(good) == 10: break

tags_present = Counter(extract_tag(p) for p in good)
missing = [t for t in TAGS if t not in tags_present]

# ───────────────────────────────────────────────────────────────────
#  Pretty output with Rich
# ───────────────────────────────────────────────────────────────────
table = Table(title="MCbench Prompt Batch", expand=True, show_lines=True)
table.add_column("#", style="bold cyan", justify="right", no_wrap=True)
table.add_column("Prompt", style="white")
table.add_column("Tag", style="bold magenta")

tag_colors = {
    "History/Science": "green",
    "Myth":            "yellow",
    "Pop":             "bright_blue",
    "Tech":            "cyan",
    "Arch":            "bright_white",
    "Nature":          "bright_green",
}

for idx, prompt in enumerate(good, 1):
    tag  = extract_tag(prompt) or "?"
    text = prompt.removesuffix(f"({tag})").rstrip()
    table.add_row(str(idx), Text(text), Text(tag, style=tag_colors.get(tag, "white")))

console.print(table)

if missing:
    console.print(f"[bold red]WARNING[/]: missing tag(s): {', '.join(missing)}")
if len(good) < 10:
    console.print(f"[bold red]WARNING[/]: only {len(good)} valid prompts produced – regenerate or tweak temperature.")


