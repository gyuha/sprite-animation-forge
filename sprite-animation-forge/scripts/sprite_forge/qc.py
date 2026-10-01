"""QC engine (docs/06 sections 1-4): items QC-01..QC-07 and QC-09, applicability, score, report.

Public API
----------
``run_qc(process_result_or_data, frames=None, action="walk", params=None, profile=None, *,
attempt=None, loop=None, qc_profile=None) -> dict``
    Returns the ``qc-report.json`` dict. ``process_result_or_data`` is a ``ProcessResult`` or
    its ``process.json`` dict; ``frames`` are the output RGBA frames (taken from the
    ``ProcessResult`` when omitted). ``params`` (``ProcessParams``) optionally overrides
    ``cell_w`` / ``x_anchor`` otherwise read from ``data["params"]``. ``profile`` is a
    ``sprite_forge.pipeline.scale.ScaleProfile`` or dict (``body_height`` is used by QC-07).
    ``qc_profile`` overrides the action -> QC profile mapping (needed for fx or custom names).
``select_best_attempt(reports) -> dict``   docs/06 section 4.2.
``score_for(results) -> int``, ``overall_status(results) -> str``, ``dhash(rgba) -> int``.

Report (schema_version 1)::

    schema_version, action, attempt, status ("pass"|"warn"|"fail"), score, frames,
    checks {edge_touch, scale_variance, anchor_variance, duplicate_frames, empty_frames},
    results [ {id, grade ("pass"|"warn"|"fail"|"info"|"skipped"|"not_run"), value?, limit?,
               reason? (skipped), ...item specifics} ],
    per_frame [ {index, bbox_h, feet_y_strict, x_metric, dhash} ],
    recommendations []     <- recovery.py (later task) attaches here; run_qc always leaves it empty.

The core is deterministic and contains no timestamps (the report has none in docs/06 4.1).

Notes on ambiguous spots
------------------------
* docs/06 grades: the example uses ``not_run`` for QC-08; the task asks for ``skipped`` for
  inapplicable items / QC-07 without profile. We use ``skipped`` (with ``reason``) for those and
  keep ``not_run`` only for QC-08, which is listed but never computed (Phase 2).
* QC-06 for idle: the docs/06 matrix says ``info`` (README conflict #8 only says QC-06 is never
  ``fail``). We follow the matrix: QC-06 is ``info`` for idle and ``warn`` for every other action.
* QC-01(a) is evaluated from ``process.json`` (frame ``bbox`` after the component filter, and
  ``gutter_missing``): a bbox within 2 raw px of the cell border means a foreground pixel
  (alpha >= 64, the measure threshold) is in the band. Components removed by the filter do not count.
* QC-01(b): ``overflow`` from process.json (any side > 0) or an output pixel with
  alpha >= 64 in the outermost row/column of the output frame.
* QC-05: process.json stores no foreground area. Area is estimated from the output frame:
  ``sum(alpha / 255) / scale**2 / raw_cell_area`` (resampling preserves area); empty cells are 0.
* QC-03/QC-04/QC-07 measure the output frames with ``measure_frame`` (empty frames skipped).
  QC-03's B is ``derived.baseline_y``; under align=register QC-03 means foot-contact slip (see ``qc03``). QC-04 uses ``feet_cx`` when x_anchor=mass, else ``mass_cx``.
* QC-02 uses the raw bbox heights from process.json (empty frames skipped).
* QC-06 skips pairs that involve an empty frame (already QC-05). ``loop`` defaults to the docs/02
  table (idle, walk, run, fall loop); a loop adds the last -> first pair when frames >= 3.
* QC-09 is ``skipped`` (reason ``no_background``) for native-alpha sheets (no bg distance).
* ``action`` profile: QC-02 is ``warn`` only above 0.20 (else ``pass``); QC-04 is always ``info``.
"""

from __future__ import annotations

import statistics

import numpy as np
from PIL import Image

from .pipeline.measure import ALPHA_THRESHOLD, measure_frame
from .pipeline.process import ProcessResult
from .pipeline.scale import ScaleProfile

SCHEMA_VERSION = 1

BAND_PX = 2  # QC-01(a) border band in raw px
QC02_WARN, QC02_FAIL, QC02_WARN_ACTION = 0.05, 0.10, 0.20
QC03_WARN, QC03_FAIL = 2, 3
QC04_WARN_FRAC = 0.08
QC05_FAIL = 0.005
QC06_MAX_DISTANCE = 2
QC07_FAIL, QC07_WARN_LOW, QC07_WARN_HIGH = 0.85, 0.92, 1.20
QC09_WARN = 60

PROFILE_BY_ACTION = {
    "idle": "locomotion", "walk": "locomotion", "run": "locomotion",
    "attack": "action", "shoot": "action", "cast": "action", "hurt": "action",
    "jump": "airborne", "fall": "airborne",
    "death": "terminal",
    "fx": "fx",
}
LOOP_ACTIONS = ("idle", "walk", "run", "fall")

# docs/06 section 3. Modes: apply | warn_only (QC-02 action) | info (QC-04 action, QC-06 idle) | skip.
_ALL = {"QC-01": "apply", "QC-05": "apply", "QC-06": "apply", "QC-09": "apply"}
MATRIX = {
    "locomotion": {**_ALL, "QC-02": "apply", "QC-03": "apply", "QC-04": "apply", "QC-07": "apply"},
    "action": {**_ALL, "QC-02": "warn_only", "QC-03": "apply", "QC-04": "info", "QC-07": "apply"},
    "airborne": {**_ALL, "QC-02": "skip", "QC-03": "apply", "QC-04": "apply", "QC-07": "skip"},
    "terminal": {**_ALL, "QC-02": "skip", "QC-03": "skip", "QC-04": "skip", "QC-07": "skip"},
    "fx": {**_ALL, "QC-02": "skip", "QC-03": "skip", "QC-04": "skip", "QC-07": "skip"},
}
# idle is the scale reference, so QC-07 does not apply to it
ACTION_OVERRIDES = {"idle": {"QC-07": "skip", "QC-06": "info"}}


def applicability(action: str, qc_profile: str | None = None) -> dict[str, str]:
    prof = qc_profile or PROFILE_BY_ACTION.get(action)
    if prof not in MATRIX:
        raise ValueError(f"unknown action {action!r} / qc_profile {qc_profile!r}; pass qc_profile explicitly")
    return {**MATRIX[prof], **(ACTION_OVERRIDES.get(action, {}) if qc_profile is None else {})}


# --- helpers ----------------------------------------------------------------------------------

def _r(v, n=4):
    return None if v is None else round(float(v), n)


def _skipped(qid: str, reason: str) -> dict:
    return {"id": qid, "grade": "skipped", "reason": reason}


def _grade_high(value: float, warn: float, fail: float | None) -> str:
    """Strictly greater than the limit trips it (docs: '> 0.10')."""
    if fail is not None and value > fail:
        return "fail"
    return "warn" if value > warn else "pass"


def dhash(rgba: np.ndarray) -> int:
    """docs/06 2.1: gray(128) composite -> grayscale -> BOX 9x8 -> horizontal compare -> 64 bits."""
    a = rgba[..., 3:4].astype(np.float64) / 255.0
    rgb = rgba[..., :3].astype(np.float64) * a + 128.0 * (1.0 - a)
    img = Image.fromarray(np.rint(rgb).astype(np.uint8), "RGB").convert("L").resize((9, 8), Image.BOX)
    px = np.asarray(img, dtype=np.int16)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _edge_touch(frame: np.ndarray) -> bool:
    a = frame[..., 3] >= ALPHA_THRESHOLD
    return bool(a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any())


# --- item evaluation --------------------------------------------------------------------------

def qc01(records, frames) -> dict:
    raw_bad, out_bad = [], []
    for rec, frame in zip(records, frames):
        x0, y0, x1, y1 = rec["cell"]
        bad_raw = bool(rec.get("gutter_missing"))
        bb = rec.get("bbox")
        if bb is not None:
            bad_raw = bad_raw or bb[0] < x0 + BAND_PX or bb[1] < y0 + BAND_PX \
                or bb[2] > x1 - BAND_PX or bb[3] > y1 - BAND_PX
        if bad_raw:
            raw_bad.append(rec["index"])
        over = rec.get("overflow")
        if (over and any(over.values())) or _edge_touch(frame):
            out_bad.append(rec["index"])
    return {"id": "QC-01", "grade": "fail" if raw_bad or out_bad else "pass",
            "raw_frames": raw_bad, "output_frames": out_bad}


def qc02(records, mode: str) -> dict:
    heights = [rec["bbox"][3] - rec["bbox"][1] for rec in records if rec.get("bbox")]
    value = (max(heights) - min(heights)) / statistics.median(heights) if len(heights) > 1 else 0.0
    if mode == "warn_only":
        return {"id": "QC-02", "grade": "warn" if value > QC02_WARN_ACTION else "pass",
                "value": _r(value), "limit": {"warn": QC02_WARN_ACTION}}
    return {"id": "QC-02", "grade": _grade_high(value, QC02_WARN, QC02_FAIL), "value": _r(value),
            "limit": {"warn": QC02_WARN, "fail": QC02_FAIL}}


def qc03(measures, baseline: float, align: str = "per_frame", vertical: str = "normalize") -> dict:
    """Anchor drift. per_frame: max |feet_strict - baseline| (every frame is pinned to the baseline, so a deviation
    is an estimator disagreement). register: foot-contact slip - the spread of the strict feet line over the
    lower half of the frames (the ones on the ground), because the shared placement keeps the model's own
    grounding. A register jump/fall (vertical travel preserved) has no ground line to judge: skipped."""
    if align == "register" and vertical == "preserve":
        return _skipped("QC-03", "vertical_preserved")
    if align == "register":
        feet = sorted((m.feet_y_strict for m in measures if m), reverse=True)
        contact = feet[: (len(feet) + 1) // 2]
        value = float(max(contact) - min(contact)) if contact else 0.0
        return {"id": "QC-03", "grade": _grade_high(value, QC03_WARN, QC03_FAIL), "value": _r(value),
                "limit": {"warn": QC03_WARN, "fail": QC03_FAIL}, "mode": "contact_slip"}
    value = max((abs(m.feet_y_strict - baseline) for m in measures if m), default=0.0)
    return {"id": "QC-03", "grade": _grade_high(value, QC03_WARN, QC03_FAIL), "value": _r(value),
            "limit": {"warn": QC03_WARN, "fail": QC03_FAIL}}


def qc04(xs, cell_w: float, mode: str) -> dict:
    value = max((abs(x - statistics.median(xs)) for x in xs), default=0.0)
    if mode == "info":
        return {"id": "QC-04", "grade": "info", "value": _r(value)}
    limit = QC04_WARN_FRAC * cell_w
    return {"id": "QC-04", "grade": "warn" if value > limit else "pass", "value": _r(value),
            "limit": {"warn": _r(limit)}}


def qc05(records, frames, scale: float) -> dict:
    bad, ratios = [], []
    for rec, frame in zip(records, frames):
        x0, y0, x1, y1 = rec["cell"]
        if rec.get("empty"):
            ratio = 0.0
        else:
            area = float((frame[..., 3] / 255.0).sum()) / (scale * scale)
            ratio = area / ((x1 - x0) * (y1 - y0))
        ratios.append(ratio)
        if ratio < QC05_FAIL:
            bad.append(rec["index"])
    return {"id": "QC-05", "grade": "fail" if bad else "pass", "value": _r(min(ratios, default=0.0), 6),
            "limit": {"fail": QC05_FAIL}, "frames": bad}


def qc06(records, hashes, loop: bool, mode: str = "apply") -> dict:
    n = len(hashes)
    pairs = [(i, i + 1) for i in range(n - 1)]
    if loop and n >= 3:
        pairs.append((n - 1, 0))
    dup = [[i, j] for i, j in pairs
           if not records[i].get("empty") and not records[j].get("empty")
           and _hamming(hashes[i], hashes[j]) <= QC06_MAX_DISTANCE]
    grade = ("info" if mode == "info" else "warn") if dup else "pass"
    return {"id": "QC-06", "grade": grade, "limit": {"warn": QC06_MAX_DISTANCE}, "pairs": dup}


def qc07(heights, profile) -> dict:
    if profile is None:
        return _skipped("QC-07", "no_profile")
    if isinstance(profile, dict):
        profile = ScaleProfile.from_dict(profile)
    if not profile.body_height or not heights:
        return _skipped("QC-07", "no_body_height" if not profile.body_height else "no_frames")
    value = statistics.median(heights) / profile.body_height
    if value < QC07_FAIL:
        grade = "fail"
    elif value < QC07_WARN_LOW or value > QC07_WARN_HIGH:
        grade = "warn"
    else:
        grade = "pass"
    return {"id": "QC-07", "grade": grade, "value": _r(value),
            "limit": {"fail": QC07_FAIL, "warn": [QC07_WARN_LOW, QC07_WARN_HIGH]}}


def qc09(bg_distance) -> dict:
    if bg_distance is None:
        return _skipped("QC-09", "no_background")
    return {"id": "QC-09", "grade": "warn" if bg_distance > QC09_WARN else "pass",
            "value": _r(bg_distance), "limit": {"warn": QC09_WARN}}


# --- score / status / report ------------------------------------------------------------------

def score_for(results) -> int:
    fails = sum(r["grade"] == "fail" for r in results)
    warns = sum(r["grade"] == "warn" for r in results)
    return max(0, 100 - 25 * fails - 8 * warns)


def overall_status(results) -> str:
    grades = {r["grade"] for r in results}
    return "fail" if "fail" in grades else "warn" if "warn" in grades else "pass"


def run_qc(process_result_or_data, frames=None, action="walk", params=None, profile=None, *,
           attempt=None, loop=None, qc_profile=None) -> dict:
    if isinstance(process_result_or_data, ProcessResult):
        data = process_result_or_data.data
        frames = process_result_or_data.frames if frames is None else frames
    else:
        data = process_result_or_data
    if frames is None:
        raise ValueError("frames are required when process data is passed without a ProcessResult")
    records = data["derived"]["frames"]
    if len(records) != len(frames):
        raise ValueError(f"{len(records)} process.json frames vs {len(frames)} output frames")

    modes = applicability(action, qc_profile)
    loop = action in LOOP_ACTIONS if loop is None else loop
    cell_w = params.cell_w if params is not None else data["params"]["cell"]["w"]
    x_anchor = params.x_anchor if params is not None else data["params"]["x_anchor"]
    derived = data["derived"]

    measures = [measure_frame(f) for f in frames]
    present = [m for m in measures if m]
    x_key = "feet_cx" if x_anchor == "mass" else "mass_cx"
    xs = [getattr(m, x_key) for m in present]
    hashes = [dhash(f) for f in frames]

    def item(qid, compute):
        return _skipped(qid, "not_applicable") if modes[qid] == "skip" else compute(modes[qid])

    results = [
        item("QC-01", lambda _: qc01(records, frames)),
        item("QC-02", lambda mode: qc02(records, mode)),
        item("QC-03", lambda _: qc03(measures, derived["baseline_y"], data["params"].get("align", "per_frame"), data["params"].get("align_vertical", "normalize"))),
        item("QC-04", lambda mode: qc04(xs, cell_w, mode)),
        item("QC-05", lambda _: qc05(records, frames, derived["scale"])),
        item("QC-06", lambda mode: qc06(records, hashes, loop, mode)),
        item("QC-07", lambda _: qc07([m.h for m in present], profile)),
        {"id": "QC-08", "grade": "not_run"},
        item("QC-09", lambda _: qc09(derived.get("bg_distance_to_key"))),
    ]
    by_id = {r["id"]: r for r in results}

    def val(qid):
        return by_id[qid].get("value")

    return {
        "schema_version": SCHEMA_VERSION,
        "action": action,
        "attempt": attempt,
        "status": overall_status(results),
        "score": score_for(results),
        "frames": len(frames),
        "checks": {
            "edge_touch": None if by_id["QC-01"]["grade"] == "skipped" else by_id["QC-01"]["grade"] == "fail",
            "scale_variance": val("QC-02"),
            "anchor_variance": val("QC-03"),
            "duplicate_frames": by_id["QC-06"].get("pairs", []),
            "empty_frames": by_id["QC-05"].get("frames", []),
        },
        "results": results,
        "per_frame": [
            {
                "index": rec["index"],
                "bbox_h": m.h if m else None,
                "feet_y_strict": m.feet_y_strict if m else None,
                "x_metric": _r(getattr(m, x_key), 2) if m else None,
                "dhash": f"{h:016x}",
            }
            for rec, m, h in zip(records, measures, hashes)
        ],
        # Recovery recommendations (docs/06 section 6) are attached here by recovery.py later.
        "recommendations": [],
    }


def select_best_attempt(reports) -> dict:
    """docs/06 4.2: highest score; tie -> smaller QC-02 value; tie -> latest attempt."""
    def key(indexed):
        pos, rep = indexed
        qc02_value = next((r.get("value") for r in rep["results"] if r["id"] == "QC-02"), None)
        att = rep.get("attempt")
        latest = int(att) if isinstance(att, str) and att.isdigit() else pos
        return (-rep["score"], qc02_value if qc02_value is not None else 0.0, -latest)

    if not reports:
        raise ValueError("no reports to choose from")
    return min(enumerate(reports), key=key)[1]
