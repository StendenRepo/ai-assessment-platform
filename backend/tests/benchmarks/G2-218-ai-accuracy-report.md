# G2-218 — Making the AI assessment more accurate, consistent and reliable

> _As a teacher, I want the AI assessment models to produce more accurate, consistent, and reliable
> results so that suggestions line up with the criteria and I spend less time correcting them._

Short version: I built a way to actually measure how good the AI scoring is, measured it, found a
few real problems, fixed what I could, and wrote down what's left. The numbers and the raw runs are
all in this folder so anyone can re-check them.

## First, what is "the model"?

There isn't a trained model to retrain — "the AI assessment" is really a three-step pipeline:

1. **Find the evidence** — `evidence_matcher.py` uses TF-IDF similarity to pull the 3 most relevant
   evidence chunks for each criterion.
2. **Score it** — `_llm_assess_criterion` in `assessment_draft_core.py` sends that to an on-prem
   Ollama model and gets back a score, a comment and a confidence. If the model is down or returns
   junk, a hand-written `_heuristic_suggestion` fallback fills in instead.
3. **Turn it into a grade** — `_score_to_grade` averages the criteria and maps to a letter.

So "improve the model" really means improving this chain: which model runs, how we prompt it, how we
calibrate the score, and how gracefully it behaves when the model isn't there.

## The benchmark

You can't improve what you can't measure, so the first job was a dataset to measure against:
`assessment_cases.json` — 21 cases I labelled by hand. They're synthetic (no real student data) but
written to look like real rubric work, covering 9 criteria across three difficulty tiers:

- **strong** — evidence clearly shows the student nailed the criterion
- **partial** — it's there but with real gaps
- **weak** — poor evidence, or none at all

Each case carries a "gold" score and grade — what a fair human marker would give. The test suite
checks those gold grades stay consistent with the grading function, so the dataset can't silently
drift.

## How I measure it

`app/eval/benchmark.py` runs the pipeline over the dataset and reports the things that map to the
three words in the story title:

- **accuracy** — mean absolute error vs the gold scores, plus how often the letter grade matches
- **how close** — share of cases within ±1.5 points
- **consistency** — score each case several times and look at the spread (`--runs N`)

It runs two ways. In CI it uses fake scorers so it needs no Ollama at all (8 tests, all green) — that
keeps the dataset and the maths honest. For the real numbers below I ran it `--live` against the
actual Ollama pipeline; every raw run is saved under `results/`.

## What I found before changing anything

The very first live run handed me the biggest problem for free:

> The models the code is configured to use for assessment — `qwen2.5:7b` and `llama3.1:8b` — **aren't
> actually pulled** on this Ollama instance, and the backend container never sets the
> `ASSESSMENT_OLLAMA_*` variables. So in practice **the LLM never ran**. Every assessment quietly
> fell back to the heuristic, and nobody would know.

Here's where that left us (`results/baseline.json`):

| Metric | Baseline |
| --- | --- |
| Score MAE | 1.152 |
| Within ±1.5 | 76.2% |
| Grade exact match | 28.6% |
| Grade within one band | 57.1% |
| MAE by tier (strong / partial / weak) | 1.04 / 0.36 / **2.60** |

Two things jumped out. The fallback scores purely off retrieval confidence, so it literally can't
tell good work from bad work that happens to be on-topic — that's why the **weak** tier is so far
off. And missing evidence was being scored **4.0 out of 10**, when any human would put it near the
bottom.

## What I changed

Everything here is covered by the test suite.

- **Let it fall back to a model that exists.** If the big assessment models aren't installed, the
  chain now drops to the smaller models that *are* (`llama3.2:1b`, `qwen2.5:3b`) instead of giving up
  and using the heuristic. There's a flag (`ASSESSMENT_OLLAMA_FALLBACK_TO_GENERAL`) to turn that off.
- **Make it deterministic.** Assessment calls now pin a seed and run at temperature 0, so the same
  input always gives the same score. The run-to-run spread dropped to **zero** everywhere.
- **Tell the model how to score.** The prompt now spells out the score bands and says, plainly, that
  no evidence means a bottom-band score — don't hedge to a safe middle.
- **Don't trust the model blindly.** Scores are clamped to the valid range, and if the model returns
  unparseable JSON it gets one retry before we fall back.
- **Fix the missing-evidence floor.** The heuristic now scores missing evidence at ~1.5/10 instead of
  4.0.

## What changed in the numbers

Each config below was run live, twice per case. Raw output is in `results/`.

| Configuration | MAE | Within ±1.5 | Grade ≤1 band | Spread | Strong / Partial / Weak |
| --- | --- | --- | --- | --- | --- |
| Baseline (heuristic, as shipped) | 1.152 | 76.2% | 57.1% | 0.0 | 1.04 / 0.36 / 2.60 |
| **Improved heuristic** (the path that runs here) | **0.914** | **85.7%** | 57.1% | 0.0 | 1.04 / 0.36 / **1.60** |
| LLM on `llama3.2:1b` | 1.31 | 76.2% | 61.9% | **0.0** | **0.38** / 1.00 / 3.30 |
| LLM on `qwen2.5:3b` | 2.12 | 38.1% | 47.6% | **0.0** | 2.38 / 2.63 / **0.90** |

What this says:

- **The path that actually runs today got clearly better** — MAE down 21% (1.152 → 0.914), within
  tolerance up from 76% to 86%, almost entirely from finally scoring missing evidence correctly.
- **Consistency is solved.** Every live config now gives identical scores on repeat runs. Before, any
  time a model *was* present it ran at temperature 0.15 — i.e. it could give the same student a
  different score each time. And it no longer fails silently when a model is missing.
- **Accuracy is now limited by the model, not the plumbing.** The two small models I can run have
  opposite personalities: the 1B is great at recognising strong work but over-rates weak work it
  finds relevant; the 3B is great at catching weak work but too harsh on strong work. Neither tiny
  model beats the tuned heuristic overall — which is itself the finding.

## Where I'd take it next

1. **Install the models the code already expects.** The compose file means to pull `qwen2.5:7b` /
   `llama3.1:8b`; they just aren't on this host. A proper 7-8B model is the single biggest accuracy
   win, and the prompt and calibration work here is already set up to use it. Until then,
   `ASSESSMENT_OLLAMA_MODEL=qwen2.5:3b` is the safest small-model default for catching weak work.
2. **Keep the benchmark running.** The offline test already runs without Ollama; a scheduled `--live`
   run would catch the day a model upgrade quietly makes scoring worse. The dataset can grow with
   anonymised real evidence once we agree how to handle that.
3. **Stop using retrieval confidence as a score.** TF-IDF can't tell praise from criticism, so the
   heuristic is blind to whether evidence is good or bad. A real embedding model for retrieval plus
   the LLM for judgement would fix that.
4. **Calibrate the grade bands to real teacher marks.** Grade exact-match sticks around 29% mostly
   because the bands are narrow (half a point each). Once we have real graded data, fit the
   thresholds to it instead of fixed percentages.
5. **Score a few times and take the median** for the LLM path, once determinism is in and a bigger
   model is available — cheap insurance against a single bad generation.

## Running it yourself

```bash
# Offline (CI, no Ollama needed):
docker exec backend python -m pytest tests/test_assessment_benchmark.py -q

# Live, inside the backend container:
docker exec backend python -m app.eval.benchmark --live --runs 2 --json-out /tmp/run.json

# With the recommended small model:
docker exec -e ASSESSMENT_OLLAMA_MODEL=qwen2.5:3b \
  backend python -m app.eval.benchmark --live --runs 2
```
