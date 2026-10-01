"""Recovery recommendations (docs/06 section 6) and the Skill-mode recovery budget (6.1).

Public API
----------
``recommend(qc_report, process_data, params=None, budget_state=None) -> list[dict]``
    Ordered recommendations for the failed checks of one attempt. Pure and deterministic; it never
    executes anything. ``process_data`` is ``process.json`` (strategy actually used, merge gap);
    ``params`` (``ProcessParams``) supplies the merge gap when given (and the strategy only if
    ``process_data`` lacks ``scale_strategy_used``).
``attach(qc_report, process_data, params=None, budget_state=None) -> qc_report``
    Sets ``qc_report["recommendations"] = recommend(...)`` (``run_qc`` itself stays recommendation-free).
``budget_state(unit_entry, best_attempt=None) -> dict``
    ``{reprocess_used, regenerate_used, reprocess_max, regenerate_max, best_attempt}`` from a manifest
    unit entry: reprocesses are counted in ``unit_entry["reprocess_count"]`` (bumped by ``process --set``),
    regenerations are the attempts beyond the first.

Recommendation (one JSON object)::

    {"type": "reprocess"|"regenerate"|"force_accept", "action": <same as type>, "code": str,
     "set": {param: value}      # reprocess only
     "attempt": "NNN"           # force_accept only
     "reason": str, "qc_id": "QC-xx", "priority": int (1 = do first), "cost": "~2s"|"~90s"|"0s"}

``code``: regenerate -> a docs/04 section 6 recovery code (``prompt.RECOVERY_CODES``); reprocess ->
``use_preserve`` | ``use_fit`` | ``align_per_frame`` | ``anchor_bottom`` | ``tighter_merge``
(regenerate codes added for motion QC: ``loop_closure`` (QC-10), ``identity_drift`` (QC-11/12); QC-13 only warns, so it has no recommendation); force_accept -> ``forced_accept``.

Notes on ambiguous spots
------------------------
* docs/06 4.1 names the field ``type``; the task/docs 11 speak of ``action``. Both are emitted (equal).
* Order follows the docs/06 section 6 table row by row (QC-05, QC-01a, QC-07, QC-01b, QC-02, QC-03, QC-09),
  not a global cheap-first sort: raw-stage failures need a regeneration anyway, so it comes first.
  Inside one row the table's 1st/2nd action order is kept (cheap reprocess before regeneration).
* Only ``fail`` grades trigger recommendations (docs/06 flowchart starts at "fail"); QC-09 warn counts
  only when QC-01 or QC-05 also fail; QC-06 never produces an automatic action.
* QC-01(b) under ``fit`` (output frame touches the cell edge although scale was fitted) is not in the
  table; we recommend regenerating ``edge_touch``.
* Budget: an action type whose budget is used up is dropped from the list. If failures remain and nothing
  is left, the single recommendation is ``force_accept`` of the best-score attempt (``budget_state
  ["best_attempt"]``, chosen by the caller with ``qc.select_best_attempt``); the caller records it in
  ``manifest["forced_accepts"]`` when the accept happens. Web UI manual mode has no budget (pass None).
"""

from __future__ import annotations

REPROCESS_MAX = 2
REGENERATE_MAX = 2
COST = {"reprocess": "~2s", "regenerate": "~90s", "force_accept": "0s"}


def budget_state(unit_entry: dict | None, best_attempt: str | None = None) -> dict:
    entry = unit_entry or {}
    return {
        "reprocess_used": int(entry.get("reprocess_count", 0)),
        "regenerate_used": max(0, len(entry.get("attempts", {})) - 1),
        "reprocess_max": REPROCESS_MAX,
        "regenerate_max": REGENERATE_MAX,
        "best_attempt": best_attempt,
    }


def _regen(code, reason, qc_id):
    return {"type": "regenerate", "code": code, "reason": reason, "qc_id": qc_id}


def _reproc(code, set_, reason, qc_id):
    return {"type": "reprocess", "code": code, "set": set_, "reason": reason, "qc_id": qc_id}


def _candidates(report: dict, data: dict, params) -> list[dict]:
    res = {r["id"]: r for r in report["results"]}

    def failed(qid):
        return res.get(qid, {}).get("grade") == "fail"

    derived = data.get("derived", {})
    strategy = derived.get("scale_strategy_used") or getattr(params, "scale_strategy", None) \
        or data.get("params", {}).get("scale_strategy", "fit")
    out: list[dict] = []

    if failed("QC-05"):
        out.append(_regen("empty_frame", "a cell is (nearly) empty; the model skipped a frame", "QC-05"))
    qc01 = res.get("QC-01", {})
    if failed("QC-01") and qc01.get("raw_frames"):
        out.append(_regen("edge_touch", "character is cut at the cell border; reprocessing cannot restore it", "QC-01"))
    if failed("QC-07"):
        if strategy == "fit":
            out.append(_reproc("use_preserve", {"scale_strategy": "preserve"},
                               "fit shrank the body (weapon widened the bbox); keep the profile scale", "QC-07"))
            out.append(_regen("character_small", "preserve is not enough if the model drew the body small", "QC-07"))
        else:
            out.append(_regen("character_small", "the model drew the character smaller than the profile", "QC-07"))
            out.append(_regen("fx_in_body", "remove effects that may have made the model shrink the body", "QC-07"))
    if failed("QC-01") and qc01.get("output_frames"):
        if strategy == "preserve":
            out.append(_regen("fx_in_body", "weapon/FX is larger than the cell at the preserved scale", "QC-01"))
            out.append(_reproc("use_fit", {"scale_strategy": "fit"}, "fit the cell instead (re-check QC-07)", "QC-01"))
        else:
            out.append(_regen("edge_touch", "output frame touches the cell edge", "QC-01"))
    if failed("QC-02"):
        out.append(_regen("scale_drift", "character size changes between frames; reprocessing keeps the ratio", "QC-02"))
    if failed("QC-10"):
        out.append(_regen("loop_closure", "the last frame does not lead back into the first frame (loop seam)", "QC-10"))
    drift = [q for q in ("QC-11", "QC-12") if failed(q)]
    if drift:
        out.append(_regen("identity_drift", "silhouette or colours jump between frames; match the reference exactly", drift[0]))
    if failed("QC-03"):
        if data.get("params", {}).get("align") == "register":
            out.append(_reproc("align_per_frame", {"align": "per_frame"}, "pin every frame's feet to the baseline instead of sharing one placement", "QC-03"))
        out.append(_reproc("anchor_bottom", {"anchor": "bottom"}, "feet line caught on a cape/weapon tip", "QC-03"))
        gap = getattr(params, "merge_gap_px", None) or data.get("params", {}).get("components", {}).get("merge_gap_px")
        set_ = {"components": "largest"}
        if gap:
            set_["merge_gap_px"] = max(1, round(gap * 0.5))
        out.append(_reproc("tighter_merge", set_, "merge fewer fragments into the body (merge_gap_px x0.5)", "QC-03"))
    if res.get("QC-09", {}).get("grade") == "warn" and (failed("QC-01") or failed("QC-05")):
        out.append(_regen("bg_mismatch", "background differs from the key colour and cells also fail", "QC-09"))
    return out


def recommend(qc_report: dict, process_data: dict, params=None, budget_state: dict | None = None) -> list[dict]:
    cands = _candidates(qc_report, process_data, params)
    if not cands:
        return []
    if budget_state is not None:
        used = {"reprocess": budget_state.get("reprocess_used", 0), "regenerate": budget_state.get("regenerate_used", 0)}
        cap = {"reprocess": budget_state.get("reprocess_max", REPROCESS_MAX),
               "regenerate": budget_state.get("regenerate_max", REGENERATE_MAX)}
        cands = [c for c in cands if used[c["type"]] < cap[c["type"]]]
        if not cands:
            best = budget_state.get("best_attempt") or qc_report.get("attempt")
            return [{"type": "force_accept", "action": "force_accept", "code": "forced_accept", "attempt": best,
                     "reason": "recovery budget exhausted; accept the best-score attempt and report the failure",
                     "qc_id": "budget", "priority": 1, "cost": COST["force_accept"]}]
    seen, out = set(), []
    for c in cands:
        key = (c["type"], c["code"])
        if key in seen:
            continue
        seen.add(key)
        out.append({**c, "action": c["type"], "priority": len(out) + 1, "cost": COST[c["type"]]})
    return out


def attach(qc_report: dict, process_data: dict, params=None, budget_state: dict | None = None) -> dict:
    qc_report["recommendations"] = recommend(qc_report, process_data, params, budget_state)
    return qc_report
