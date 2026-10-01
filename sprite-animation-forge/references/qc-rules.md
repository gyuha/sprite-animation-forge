# QC rules and recovery

`process` writes `qc-report.json` and prints `qc: {status, failed: [...], recommendations: [...]}`.
`status` is `pass`, `warn` (acceptable, report it) or `fail`. QC failure still exits 0. `score =
max(0, 100 - 25*fails - 8*warns)`.

| ID | Check | fail | warn |
|---|---|---|---|
| QC-01 | boundary: raw cell crossing/near cell border, or output frame overflow/touching the cell edge | any | - |
| QC-02 | scale drift `(max h - min h)/median h` | > 0.10 | > 0.05 |
| QC-03 | anchor drift (feet line, px) | > 3 | > 2 |
| QC-04 | center drift | - | > 0.08 x cell width |
| QC-05 | empty frame (foreground area < 0.5%) | any | - |
| QC-06 | duplicate adjacent frames | - | hash distance <= 2 |
| QC-07 | `median h / profile.body_height` | < 0.85 | < 0.92 or > 1.20 |
| QC-08 | reference consistency | not run in the CLI | - |
| QC-09 | background key color mismatch | - | > 60 |

Profiles: locomotion (idle/walk/run), action (attack/shoot/cast/hurt: QC-02 warn only > 0.20, QC-04 info),
airborne (jump/fall: no QC-02/07), terminal (death: no QC-02/03/04/07). QC-07 needs a scale profile; the
reference action itself is not checked (no profile yet). Known limit: a raised weapon can hide a shrunken
body in bbox height; compare idle and attack visually if the user cares.

## Reading `qc.recommendations`
Take the FIRST item (ordered by `priority`). Fields: `type`/`action` (`reprocess` | `regenerate` |
`force_accept`), `code`, `set` (reprocess only), `attempt` (force_accept only), `reason`, `qc_id`, `cost`.

| Failure | First recommendation | Command |
|---|---|---|
| QC-05 empty | regenerate `empty_frame` | `generate <cid> <a> --recovery empty_frame` then `process` |
| QC-01 raw border | regenerate `edge_touch` | `generate ... --recovery edge_touch` |
| QC-07 small, fit | reprocess `use_preserve` (`scale_strategy=preserve`) | `process <cid> <a> --set scale_strategy=preserve` |
| QC-07 small, preserve | regenerate `character_small`, then `fx_in_body` | `generate ... --recovery character_small` |
| QC-01 overflow, preserve | regenerate `fx_in_body`, then reprocess `use_fit` | |
| QC-02 drift | regenerate `scale_drift` | `generate ... --recovery scale_drift` |
| QC-03 anchor | reprocess `anchor_bottom` (`anchor=bottom`), then `tighter_merge` (halve `merge_gap_px`) | `process ... --set anchor=bottom` |
| QC-09 / QC-06 | warn only; no automatic action unless QC-01/05 also fail (QC-09) | |

`process --set` keys: anchor (feet|bottom|center), x_anchor (mass|feet|bbox), scale_strategy (fit|preserve),
components (largest|all), merge_gap_px, min_area_px, edge_band_px, margin_top/side/bottom, t_in, t_out,
despill, key_color (#RRGGBB). Reprocessing re-runs the latest (or `--attempt`) attempt in place.

## Budget (Skill mode)
Per action: at most 2 reprocesses (`process --set`) and 2 regenerations (attempts beyond the first). When
both are spent and failures remain, the only recommendation is `force_accept` with the best-score attempt
(ties: smaller QC-02, then newest). Run `accept <cid> <a> --attempt <that attempt>`; the accept is recorded
with `forced: true` and listed in `manifest.json` and the root `qc-report.json` as `forced_accepts`.
Mention every forced accept and its failed checks in the final report.
