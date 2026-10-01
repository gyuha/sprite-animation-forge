"""Prompt Generator (docs/04): deterministic image-model prompts assembled from plan + profile.

Public API
----------
``PROMPT_TEMPLATE_VERSION``  ``"action_prompt@1"``; bump when any ``prompt_templates/*.txt`` changes
    (docs/04 1). Recorded in ``PromptResult.template_version`` (and so in ``generation.json``).
``build_prompt(plan, profile, action, direction=None, extra=None, recovery=(), *,
               identity_fields=(), margin_pct=8) -> PromptResult``
    ``plan``      animation-plan dict (``plan.build_plan``); ``profile`` character-profile dict or None.
    ``direction`` required when ``plan["directions"]`` has 2+ entries (same rules as
                  ``plan.resolve_unit``; a mirror-derived ``left`` raises ``mirrored_direction``).
    ``extra``     free text for ADDITIONAL DIRECTION, max 500 chars, not translated.
    ``recovery``  iterable of recovery codes (``RECOVERY_CODES``); ``identity_fields`` fills
                  ``identity_drift``'s ``{fields}``. Unknown code -> ``ForgeError(invalid_params)``.
    Raises ``ForgeError`` if the assembled text fails ``validate_prompt``.
``PromptResult(text, template_version, references_needed, warnings)``
    ``references_needed``: ordered list of reference roles the caller must attach:
    ``"character"`` (Image 1, the keyed reference) and, for a non-representative direction of a
    multi-direction plan, ``"direction:<unit>"`` (Image 2), where ``<unit>`` is the unit whose adopted
    sheet to attach (``direction_reference_unit``), e.g. ``"direction:idle/down"``.
``direction_reference_unit(plan) -> str | None``   representative-direction unit (first body action
    in ``order`` that has ``plan["facing"]``), or None for single-direction plans.
``reference_images_needed(plan, action, direction) -> list[str]``   the ``references_needed`` logic.
``build_canonical_prompt(description, *, art_style="clean_hd", view="side", direction=None,
                         key_color="#FF00FF") -> PromptResult``   Case B (docs/04 5).
``validate_prompt(text, *, max_chars=6000) -> list[str]``   docs/04 8 rules; [] means valid.
``RECOVERY_CODES``, ``RECOVERY_PARAM_CHANGES`` (code -> param change the caller applies:
    ``edge_touch`` margin_pct 8 -> 15 (applied here), ``character_small`` scale_strategy=preserve
    (caller/plan side)), ``MOTION_LIBRARY`` (action -> {frames, loop, title, description, poses}).

Notes on ambiguous spots
------------------------
* docs/04 3.4 wants ``Describe all motion relative to the direction the character is facing.`` at the
  head of ACTION, but the 7 walk example (single direction) omits it. We emit it only for plans with
  2+ directions, so the single-direction walk output equals the 7 example byte for byte.
* 3.7 gives no heading for RECOVERY; we use a ``RECOVERY`` heading, one phrase per line.
* 7's example profile has ``accessories: ["leather pouch"]`` in docs/08 but no accessories line; the
  template (3.2) has one, so we print it when non-empty (the snapshot profile has none).
* Multi-direction camera text exists only for topdown (3.4). Other views use ``camera.txt [prefix]``
  + the direction sentence; the same form is used for a single direction that is not the view default.
* Motion-library poses apply only when ``frames`` equals the library default; otherwise the general
  rule (3 4) is used. ``act["poses"]`` always wins, ``act["motion"]`` replaces the description.
  The loop line follows the plan's ``loop``. ``kind=fx`` actions reuse the body template (warning).
* Case B uses ``clean_hd`` wording for ``project_native``/``auto`` (there is no reference to match).
* ``margin_pct`` in the 3.9 GRID RULES is a prompt-only number (plan margins are pixels).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from .errors import ForgeError
from .plan import DIRECTIONS_BY_VIEW, resolve_unit

PROMPT_TEMPLATE_VERSION = "action_prompt@2"
MAX_PROMPT_CHARS = 6000
MAX_EXTRA_CHARS = 500
EDGE_TOUCH_MARGIN_PCT = 15
KEY_NAMES = {"#FF00FF": "magenta", "#00FF00": "pure green"}

HEADINGS = ("REFERENCE IDENTITY", "DIRECTION REFERENCE", "ACTION", "ADDITIONAL DIRECTION", "RECOVERY",
            "CONSISTENCY RULES", "GRID RULES", "BACKGROUND RULE")
REQUIRED_HEADINGS = ("REFERENCE IDENTITY", "ACTION", "CONSISTENCY RULES", "GRID RULES", "BACKGROUND RULE")
FOOTER = "No text. No watermark. No UI."


@dataclass(frozen=True)
class PromptResult:
    text: str
    template_version: str
    references_needed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- template loading

@lru_cache(maxsize=None)
def _template(name: str) -> str:
    return resources.files(__package__).joinpath("prompt_templates", name).read_text(encoding="utf-8").rstrip("\n")


@lru_cache(maxsize=None)
def _sections(name: str) -> dict[str, dict[str, str]]:
    """``[section]`` headers; ``key | value`` rows become a dict, bare lines are stored under ``""``."""
    out: dict[str, dict[str, str]] = {}
    cur = None
    for line in _template(name).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[([^\]]+)\]", line)
        if m:
            cur = out.setdefault(m.group(1), {})
        elif cur is not None and " | " in line:
            key, value = line.split(" | ", 1)
            cur[key] = value
        elif cur is not None:
            cur[""] = (cur[""] + "\n" + line) if "" in cur else line
    return out


BASELINE_LINE = "- The soles of the feet sit on the same horizontal baseline in every cell of a row."


def _baseline_line(plan: dict, action: str) -> str:
    """Airborne actions (jump/fall) must show height changes, so they do not get the shared-baseline rule."""
    from .plan import is_airborne
    act = plan["actions"].get(action, {})
    return "" if is_airborne(act, action) else BASELINE_LINE


def _fill(name: str, **values) -> str:
    """Format a template and drop lines left empty by optional placeholders."""
    text = _template(name).format(**values)
    return "\n".join(ln for ln in text.splitlines() if ln.strip())


@lru_cache(maxsize=None)
def _load_motion_library() -> dict[str, dict]:
    lib: dict[str, dict] = {}
    cur = None
    for line in _template("motion_library.txt").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[(\w+)\] frames=(\d+) loop=(true|false) title=(.+)", line)
        if m:
            name, frames, loop, title = m.groups()
            cur = lib[name] = {"frames": int(frames), "loop": loop == "true", "title": title,
                               "description": None, "poses": []}
        elif cur["description"] is None:
            cur["description"] = line
        else:
            cur["poses"].append(re.sub(r"^\d+\. ", "", line))
    return lib


MOTION_LIBRARY = _load_motion_library()
RECOVERY_CODES = tuple(_sections("recovery.txt")["phrase"])
RECOVERY_PARAM_CHANGES = {
    "edge_touch": {"margin_pct": EDGE_TOUCH_MARGIN_PCT},
    "character_small": {"scale_strategy": "preserve"},
}


# ---------------------------------------------------------------- blocks

def _key_name(key_hex: str) -> str:
    return KEY_NAMES.get(key_hex.upper(), key_hex)


def _identity_block(profile: dict | None) -> str:
    ident = (profile or {}).get("identity", {})

    def text(key):
        return (ident.get(key) or "").strip()

    def items(key):
        return ", ".join(x.strip() for x in ident.get(key) or [] if x.strip())

    def join(*parts):
        return "; ".join(p for p in parts if p)

    def pair(label, value):
        return f"{label}: {value}" if value else ""

    rows = [
        ("silhouette", pair("silhouette", text("silhouette"))),
        ("body", join(pair("body proportions", text("body_ratio")), pair("head-to-body ratio", text("head_ratio")))),
        ("hair", pair("hair", text("hair"))),
        ("face", join(pair("face", text("face")), pair("eyes", text("eyes")))),
        ("clothing", pair("clothing", text("clothing"))),
        ("colors", pair("colors", join(f"primary {items('primary_colors')}" if items("primary_colors") else "",
                                       f"secondary {items('secondary_colors')}" if items("secondary_colors") else ""))),
        ("weapon", pair("weapon", text("weapon"))),
        ("accessories", pair("accessories", items("accessories"))),
        ("style", join(pair("outline", text("outline_style")), pair("shading", text("shading_style")))),
    ]
    bullets = [f"- {value}" for _, value in rows if value]
    sec = _sections("reference_identity.txt")
    lines = ["REFERENCE IDENTITY", sec["intro" if bullets else "intro_empty"][""], *bullets, sec["outro"][""]]
    return "\n".join(lines)


def _camera_block(plan: dict, direction: str) -> str:
    view = plan["view"]
    cam = _sections("camera.txt")
    dirs = plan["directions"]
    if len(dirs) == 1 and direction == DIRECTIONS_BY_VIEW[view][0]:
        return cam["view"][view]
    return f"{cam['prefix'][view]} {cam['direction'][direction]}"


def _sequence(action: str, act: dict, lib: dict | None, frames: int, loop: bool) -> str:
    rules = _sections("action_general_rule.txt")
    poses = act.get("poses")
    if not poses and lib and lib["frames"] == frames:
        poses = lib["poses"]
    if poses:
        return "Frame sequence:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(poses, 1))
    if loop:
        return rules["loop"][""].format(frames=frames, action=action.replace("_", " "))
    if lib:
        return rules["oneshot"][""].format(frames=frames, start_pose=lib["poses"][0], end_pose=lib["poses"][-1])
    return rules["oneshot_custom"][""].format(frames=frames)


def _action_block(plan: dict, profile: dict | None, action: str, multi_direction: bool) -> str:
    act = plan["actions"][action]
    frames, loop = act["frames"], act["loop"]
    lib = MOTION_LIBRARY.get(action)
    weapon = ((profile or {}).get("identity", {}).get("weapon") or "").strip() or "weapon"
    description = act.get("motion") or (lib["description"].format(weapon=weapon) if lib else None)
    if description is None:
        raise ForgeError("invalid_params", f"custom action {action!r} has no motion description")
    loop_rules = _sections("action_loop_line.txt")
    loop_line = loop_rules["loop" if loop else "oneshot"][""].format(frames=frames)
    return _fill(
        "action.txt",
        facing_line=_template("action_facing.txt") if multi_direction else "",
        description=description,
        sequence=_sequence(action, act, lib, frames, loop),
        loop_line=loop_line,
        in_place_line="" if act.get("kind") == "fx" else _template("action_in_place.txt"),
    )


def _recovery_block(codes: list[str], frames: int, key_hex: str, identity_fields) -> str:
    table = _sections("recovery.txt")
    fields = ", ".join(identity_fields)
    phrases = []
    for code in codes:
        if code == "identity_drift" and not fields:
            phrases.append(table["identity_drift_no_fields"][""])
        else:
            phrases.append(table["phrase"][code].format(
                frames=frames, key_name=_key_name(key_hex), key_hex=key_hex, fields=fields))
    return _fill("recovery_block.txt", phrases="\n".join(phrases))


# ---------------------------------------------------------------- references

def direction_reference_unit(plan: dict) -> str | None:
    """Unit whose adopted sheet is the representative-direction reference (docs/02 8.1 step 1)."""
    dirs = plan["directions"]
    if len(dirs) < 2:
        return None
    rep = plan["facing"]
    for action in plan["order"]:
        act = plan["actions"][action]
        if act.get("kind", "body") == "body" and rep in act.get("directions", dirs):
            return f"{action}/{rep}"
    return None


def _needs_direction_reference(plan: dict, direction: str) -> bool:
    return len(plan["directions"]) > 1 and direction != plan["facing"]


def reference_images_needed(plan: dict, action: str, direction: str | None = None) -> list[str]:
    _, direction, _ = resolve_unit(plan, action, direction)
    refs = ["character"]
    if _needs_direction_reference(plan, direction):
        unit = direction_reference_unit(plan)
        if unit is not None:
            refs.append(f"direction:{unit}")
    return refs


# ---------------------------------------------------------------- build

def build_prompt(plan: dict, profile: dict | None, action: str, direction: str | None = None,
                 extra: str | None = None, recovery=(), *, identity_fields=(), margin_pct: int = 8) -> PromptResult:
    _, direction, _ = resolve_unit(plan, action, direction)
    codes = list(dict.fromkeys(recovery or ()))
    for code in codes:
        if code not in RECOVERY_CODES:
            raise ForgeError("invalid_params", f"unknown recovery code {code!r}; choose from {list(RECOVERY_CODES)}")
    extra = (extra or "").strip()
    if len(extra) > MAX_EXTRA_CHARS:
        raise ForgeError("invalid_params", f"extra is {len(extra)} chars; max {MAX_EXTRA_CHARS}")

    act = plan["actions"][action]
    frames = act["frames"]
    rows, cols = (int(x) for x in act["grid"].split("x"))
    key_hex = plan["key_color"].upper()
    multi = len(plan["directions"]) > 1
    if "edge_touch" in codes:
        margin_pct = EDGE_TOUCH_MARGIN_PCT
    lib = MOTION_LIBRARY.get(action)
    title = (lib["title"] if lib else action.replace("_", " "))

    warnings = []
    if act.get("kind") == "fx":
        warnings.append("fx_action_uses_body_template")
    refs = reference_images_needed(plan, action, direction)
    if _needs_direction_reference(plan, direction) and len(refs) == 1:
        warnings.append("no_representative_direction_unit")

    blocks = [
        _fill("header.txt", rows=rows, cols=cols, action_title=title, frames=frames),
        _identity_block(profile),
        _sections("art_style.txt")["style"][plan["art_style"]],
        _camera_block(plan, direction),
    ]
    if len(refs) > 1:
        blocks.append(_template("direction_reference.txt"))
    blocks.append(_action_block(plan, profile, action, multi))
    if extra:
        blocks.append(_fill("additional_direction.txt", extra=extra))
    if codes:
        blocks.append(_recovery_block(codes, frames, key_hex, identity_fields))
    empty = rows * cols - frames
    blocks += [
        _fill("consistency_rules.txt", facing=direction, baseline_line=_baseline_line(plan, action)),
        _fill("grid_rules.txt", rows=rows, cols=cols, cells=rows * cols, margin_pct=margin_pct,
              empty_cells_line=_template("grid_empty_cells.txt").format(frames=frames, empty_cells=empty)
              if empty else ""),
        _fill("background_rule.txt", key_name=_key_name(key_hex), key_hex=key_hex),
        _template("footer.txt"),
    ]
    text = "\n\n".join(blocks) + "\n"
    problems = validate_prompt(text)
    if problems:
        raise ForgeError("invalid_prompt", "; ".join(problems))
    return PromptResult(text, PROMPT_TEMPLATE_VERSION, refs, warnings)


def build_canonical_prompt(description: str, *, art_style: str = "clean_hd", view: str = "side",
                           direction: str | None = None, key_color: str = "#FF00FF") -> PromptResult:
    """Case B canonical reference prompt (docs/04 5): one full-body character, no reference image."""
    description = (description or "").strip()
    if not description:
        raise ForgeError("invalid_params", "character description is empty")
    if view not in DIRECTIONS_BY_VIEW:
        raise ForgeError("invalid_params", f"unknown view {view!r}")
    warnings = []
    if art_style in ("project_native", "auto"):
        warnings.append("art_style_without_reference_uses_clean_hd")
        art_style = "clean_hd"
    styles = _sections("art_style.txt")["style"]
    if art_style not in styles:
        raise ForgeError("invalid_params", f"unknown art_style {art_style!r}")
    cam = _sections("camera.txt")
    if direction is None or direction == DIRECTIONS_BY_VIEW[view][0]:
        camera_line = cam["view"][view]
    else:
        camera_line = f"{cam['prefix'][view]} {cam['direction'][direction]}"
    key_hex = key_color.upper()
    text = _fill("canonical_reference.txt", description=description, art_style_line=styles[art_style],
                 camera_line=camera_line, key_name=_key_name(key_hex), key_hex=key_hex) + "\n"
    return PromptResult(text, PROMPT_TEMPLATE_VERSION, [], warnings)


# ---------------------------------------------------------------- validation (docs/04 8)

_HEADER_RE = re.compile(r"Create a (\d+)x(\d+) sprite animation grid of a 2D game character: .+, (\d+) frames\.")
_GRID_RE = re.compile(r"- (\d+) rows x (\d+) columns = (\d+) equal cells\.")
_MARGIN_RE = re.compile(r"Leave at least (\d+)% empty background margin")
_EMPTY_RE = re.compile(r"- Use only the first (\d+) cells\. Leave the last (\d+) cell\(s\) completely empty")
_BG_RE = re.compile(r"Fill the entire background with flat, solid (.+?) (#[0-9A-Fa-f]{6})\.")
_NOT_USE_RE = re.compile(r"Do not use (.+?) or similar hues")
_FACING_RE = re.compile(r"Same facing direction \((\w[\w-]*)\) in every cell")


def validate_prompt(text: str, *, max_chars: int = MAX_PROMPT_CHARS) -> list[str]:
    """Check an assembled action prompt against docs/04 8; returns problem strings ([] = valid)."""
    problems: list[str] = []
    lines = text.splitlines()

    if len(text) > max_chars:
        problems.append(f"length {len(text)} > {max_chars}")
    # the user's ADDITIONAL DIRECTION block is free text: exclude it from template-integrity checks
    own = re.sub(r"(?m)^ADDITIONAL DIRECTION\n(?:.+\n?)*", "", text)
    if re.search(r"\{[^{}]*\}", own):
        problems.append("unresolved placeholder in text")

    # empty profile field lines: "- hair: " style bullets or dangling separators
    for ln in own.splitlines():
        if ln.startswith("- ") and (re.fullmatch(r"- [\w -]+:\s*", ln) or re.search(r"[:;]\s*;|;\s*$", ln)):
            problems.append(f"empty field line: {ln!r}")

    # blocks present exactly once, in order
    positions = {}
    for h in HEADINGS:
        idx = [i for i, ln in enumerate(lines) if ln == h]
        if len(idx) > 1:
            problems.append(f"heading {h} appears {len(idx)} times")
        if idx:
            positions[h] = idx[0]
    for h in REQUIRED_HEADINGS:
        if h not in positions:
            problems.append(f"missing block {h}")
    present = [h for h in HEADINGS if h in positions]
    if [positions[h] for h in present] != sorted(positions[h] for h in present):
        problems.append("blocks out of order: " + " > ".join(present))
    if lines and not lines[0].startswith("Create a "):
        problems.append("HEADER must be the first line")
    if "REFERENCE IDENTITY" in positions and positions["REFERENCE IDENTITY"] < 1:
        problems.append("HEADER must precede REFERENCE IDENTITY")
    if text.rstrip("\n").splitlines()[-1:] != [FOOTER]:
        problems.append("FOOTER must be the last line")
    if "ADDITIONAL DIRECTION" in positions and "CONSISTENCY RULES" in positions \
            and positions["ADDITIONAL DIRECTION"] > positions["CONSISTENCY RULES"]:
        problems.append("ADDITIONAL DIRECTION must come before CONSISTENCY RULES")

    # grid / frames consistency and the empty-cell rule
    head, grid = _HEADER_RE.search(text), _GRID_RE.search(text)
    if not head or not grid:
        problems.append("HEADER or GRID RULES line malformed")
    else:
        rows, cols, frames = (int(x) for x in head.groups())
        g_rows, g_cols, cells = (int(x) for x in grid.groups())
        if (rows, cols) != (g_rows, g_cols) or cells != rows * cols:
            problems.append("HEADER grid and GRID RULES disagree")
        empty = _EMPTY_RE.search(text)
        if frames > rows * cols:
            problems.append(f"frames {frames} > cells {rows * cols}")
        elif frames < rows * cols:
            if not empty or (int(empty.group(1)), int(empty.group(2))) != (frames, rows * cols - frames):
                problems.append("frames < rows x cols but the empty-cell rule is missing or wrong")
        elif empty:
            problems.append("empty-cell rule present although every cell is used")

    # margin: edge_touch recovery phrase <-> 15%
    margin = _MARGIN_RE.search(text)
    if not margin:
        problems.append("margin rule missing")
    else:
        edge = "The previous attempt crossed cell borders." in text
        want = EDGE_TOUCH_MARGIN_PCT if edge else None
        if want is not None and int(margin.group(1)) != want:
            problems.append(f"edge_touch recovery requires margin {want}%, got {margin.group(1)}%")
        if want is None and int(margin.group(1)) >= EDGE_TOUCH_MARGIN_PCT:
            problems.append("margin >= 15% without edge_touch recovery")

    # contradictions: background key name/hex, facing
    bg, not_use = _BG_RE.search(text), _NOT_USE_RE.search(text)
    if not bg or not not_use:
        problems.append("BACKGROUND RULE malformed")
    else:
        if bg.group(1) != not_use.group(1):
            problems.append("background key name differs from the 'do not use' hue")
        if KEY_NAMES.get(bg.group(2).upper()) not in (None, bg.group(1)):
            problems.append("background key name does not match its hex")
        other = "pure green" if bg.group(1) == "magenta" else "magenta"
        if other in text[bg.start():]:
            problems.append(f"background rule names both {bg.group(1)} and {other}")
    facing = _FACING_RE.search(text)
    cam_facing = re.search(r"character facing (right|left|up|down)\b", text)
    if facing and cam_facing and facing.group(1) != cam_facing.group(1):
        problems.append(f"CONSISTENCY facing {facing.group(1)} contradicts CAMERA facing {cam_facing.group(1)}")
    return problems
