# Evaluation results

- Answer key: `eval/answer_key.json`, SHA-256 `d92be7e74a9eaad5aae2c2ab572388ac8e5b1ce6d8130f01d019781db29cd965`, committed in git (commit "Lock eval answer key…") **before** any evaluation run. `run_eval.py` refuses to run if the hash differs.
- Labels come from the data sources, not from Lifeline's output. "Inside" towns are named in the ICEYE product's own `flooded_cities` attribute. Wrong dates fall outside FEMA's DR-4827 incident window. Ambiguous towns exist in more than one state.
- Official run: `results_v1.json`, live, LLM `gemini-3.5-flash-lite` (same model for Lifeline's Reader and for the baseline). $100 assumed per appeal.

| | LLM alone | Lifeline |
|---|---|---|
| Accuracy (verdict class) | 25.0% (10/40) | **95.0% (38/40)** |
| Unverified appeals it would have paid | 1 ($100) | **0 ($0)** |
| Genuine appeals funded (of 15) | 1 | **13** |
| Red-team attacks stopped | 4/5 | **5/5** |
| Reason code matches expected | n/a | 25/25 |
| Avg check time | 4.05 s | 4.58 s |

**Headline:** the LLM alone would have sent $100 of donor money to an unverified appeal: it marked the lookalike-charity attack (rt-03, "Mana Food Bank Relief") VERIFIED. It also funded only 1 of the 15 genuine appeals, because it answers "UNVERIFIABLE" to almost everything. Lifeline sent $0 to unverified appeals and funded 13 of 15.

By category (Lifeline / LLM alone): inside 13/15 vs 1/15 · outside 10/10 vs 3/10 · wrong date 5/5 vs 0/5 · ambiguous 5/5 vs 5/5 · red team 5/5 vs 1/5 (exact verdict match; the LLM alone stopped 4/5 from being paid).

## Misses (reported, not tuned away)

| Appeal | Expected | Lifeline | Why |
|---|---|---|---|
| in-05 Marion NC | VERIFIED | NOT VERIFIED (NOT_IN_FLOOD_AREA) | The nearest observed flood (Catawba River corridor) is 3.7 km from the Census centre point of Marion, outside the 2.2 km place radius. The rule is conservative: a genuine appeal was refused, but the donor is redirected to verified local charities. |
| in-09 Burnsville NC | VERIFIED | UNVERIFIABLE (NEEDS_HUMAN) | Only 0.009 km² of observed flood near the town centre, so the Skeptic's tiny-overlap check turned green into yellow. |

Both are false negatives (money held, not lost). There were no false positives.

## Changes after the v1 run (before/after)

No rule or threshold was changed after seeing the results. Changes made after v1 and their effect on verdicts:

| Change | Verdicts before | Verdicts after |
|---|---|---|
| Faster geometry projection (affine scale) and cached OFAC fuzzy match | 38/40 | 38/40, all 40 `verdict_sha256` identical (`python verify.py`) |
| Redirect for non-flooded places now points to a charity inside the observed flood area | not part of the verdict | unchanged |
| Judge rule shown inside its own step; explanation prompt given facts only | not part of the verdict | unchanged |

Before v1 (during development, on hand-written test strings rather than the eval set): the Gemini model was switched from the retired `gemini-2.5-flash` to `gemini-3.5-flash-lite`. Place narrowing ("Biltmore Village, Asheville" → Asheville), normalised charity-name matching and lookalike partial matching were added at that stage.

Sample mode (`python run.py --sample`) replays the recorded v1 LLM responses offline and reproduces the same scoreboard.
