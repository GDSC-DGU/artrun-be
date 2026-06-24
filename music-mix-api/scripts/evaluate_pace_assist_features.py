from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.repositories import InMemorySegmentRepository
from app.domain.models import PlaybackContext, RunningContext, Segment
from app.recommendation.pace_assist_selector import pace_assist_candidate_payload
from app.recommendation.scoring import score_segment_for_intention
from scripts.segment_json import load_segments


INTENTION_CONTEXTS: dict[str, RunningContext] = {
    "steady": RunningContext(
        current_pace_sec_per_km=300.0,
        target_pace_sec_per_km=300.0,
        running_mode="steady_run",
        target_cadence_spm=172.0,
    ),
    "pace_up": RunningContext(
        current_pace_sec_per_km=360.0,
        target_pace_sec_per_km=300.0,
        running_mode="pace_up",
        target_cadence_spm=172.0,
    ),
    "sprint_push": RunningContext(
        current_pace_sec_per_km=360.0,
        target_pace_sec_per_km=280.0,
        running_mode="sprint",
        target_cadence_spm=172.0,
    ),
}

DEBUG_FIELDS = [
    "rank",
    "segment_id",
    "track_id",
    "section_type",
    "section_type_signal",
    "section_type_ai",
    "ai_segment_role",
    "recommended_for",
    "avoid_for",
    "corrected_section_type",
    "pace_role_hint",
    "bpm",
    "effective_pulse_value",
    "effective_pulse_relation",
    "energy_score_debug_only",
    "energy_score",
    "pace_push_score",
    "tempo_match_score",
    "cadence_alignment_score",
    "transition_continuity_score",
    "excessive_jump_penalty",
    "beat_salience_score",
    "rhythmic_activity_score",
    "rhythmic_predictability_score",
    "syncopation_score",
    "groove_score",
    "bass_drive_score",
    "static_low_end_penalty",
    "section_role_score",
    "repetition_penalty",
    "ai_perceived_speed_score",
    "ai_flow_momentum_score",
    "ai_pace_push_score",
    "ai_cadence_lock_score",
    "ai_groove_score",
    "ai_bass_drive_score",
    "ai_static_loop_penalty",
    "ai_static_low_end_penalty",
    "ai_chaos_penalty",
    "entry_quality",
    "exit_quality",
    "phrase_confidence",
    "ai_notes",
    "drop_likelihood_score",
    "final_score",
    "reason",
]

SUMMARY_FIELDS = [
    "segment_id",
    "track_id",
    "expected_role",
    "human_pace_push_rating",
    "section_type",
    "section_type_ai",
    "ai_segment_role",
    "corrected_section_type",
    "energy_score",
    "pace_push_score",
    "ai_pace_push_score",
    "ai_flow_momentum_score",
    "ai_static_low_end_penalty",
    "beat_salience_score",
    "rhythmic_activity_score",
    "bass_drive_score",
    "static_low_end_penalty",
    "drop_likelihood_score",
    "pace_role_hint",
    "pass_fail",
    "notes",
]


def meta(segment: Segment, key: str, default: Any = None) -> Any:
    return segment.metadata.get(key, default)


def segment_value(segment: Segment, key: str) -> Any:
    if key == "section_type":
        return segment.section_type.value
    if hasattr(segment, key):
        return getattr(segment, key)
    return meta(segment, key, "")


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def print_table(rows: list[dict], fields: list[str]) -> None:
    if not rows:
        print("(no rows)")
        return
    widths = {
        field: max(len(field), *(len(fmt(row.get(field, ""))) for row in rows))
        for field in fields
    }
    print(" | ".join(field.ljust(widths[field]) for field in fields))
    print("-+-".join("-" * widths[field] for field in fields))
    for row in rows:
        print(" | ".join(fmt(row.get(field, "")).ljust(widths[field]) for field in fields))


def rank_segments(segments: list[Segment], intention: str) -> list[tuple[Segment, Any]]:
    running = INTENTION_CONTEXTS[intention]
    playback = PlaybackContext(
        current_segment_played_sec=45.0,
        seconds_since_last_switch=60.0,
        previous_target_energy=0.35,
    )
    ranked = [
        (
            segment,
            score_segment_for_intention(
                segment,
                running,
                playback,
                current_segment=None,
                intention=intention,
            ),
        )
        for segment in segments
        if segment.is_good_entry and 20.0 <= segment.duration_sec <= 120.0
    ]
    return sorted(ranked, key=lambda item: item[1].final_score, reverse=True)


def rank_lookup(rankings: dict[str, list[tuple[Segment, Any]]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for intention, ranked in rankings.items():
        out[intention] = {segment.segment_id: idx for idx, (segment, _) in enumerate(ranked, start=1)}
    return out


def is_groove_or_pulse_candidate(segment: Segment) -> bool:
    section = segment.section_type.value
    corrected = str(meta(segment, "corrected_section_type", section))
    role = str(meta(segment, "pace_role_hint", ""))
    ai_role = str(meta(segment, "ai_segment_role", ""))
    groove_fit = float(meta(segment, "groove_syncopation_fit", 0.0))
    predictability = float(meta(segment, "rhythmic_predictability_score", 0.0))
    return (
        section == "groove"
        and corrected == "groove"
        and (role == "pace_up" or ai_role in {"steady_to_pace_up_bridge", "fast_light_control", "pace_up"} or groove_fit >= 0.55)
        and predictability >= 0.60
    )


def evaluate_case(
    case: dict,
    segment: Segment,
    segment_by_id: dict[str, Segment],
    ranks: dict[str, dict[str, int]],
) -> tuple[str, list[str]]:
    failures: list[str] = []

    for intention in case.get("should_not_rank_for", []):
        rank = ranks.get(intention, {}).get(segment.segment_id, 999)
        if rank <= 5:
            failures.append(f"{intention}_rank={rank}")

    should_rank_for = case.get("should_rank_for", [])
    if should_rank_for:
        max_rank = int(case.get("max_rank", 5))
        observed = {
            intention: ranks.get(intention, {}).get(segment.segment_id, 999)
            for intention in should_rank_for
        }
        if all(rank > max_rank for rank in observed.values()):
            failures.append(
                f"not_top{max_rank}_for_any_of_"
                + ",".join(f"{intention}={rank}" for intention, rank in observed.items())
            )

    if segment.segment_id == "track1_seg_003":
        track6 = segment_by_id.get("track6_seg_004")
        if float(meta(segment, "drop_likelihood_score", 0.0)) >= 0.45:
            failures.append("drop_likelihood_high")
        if float(meta(segment, "ai_pace_push_score", meta(segment, "pace_push_score", 0.0))) >= 0.55:
            failures.append("ai_pace_push_high")
        if float(meta(segment, "ai_static_low_end_penalty", meta(segment, "static_low_end_penalty", 0.0))) < 0.45:
            failures.append("static_low_end_penalty_low")
        avoid_for = set(meta(segment, "avoid_for", []))
        if "pace_up" not in avoid_for or "sprint_push" not in avoid_for:
            failures.append("missing_avoid_for_pace_up_or_sprint")
        if track6 and float(meta(segment, "pace_push_score", 0.0)) >= float(meta(track6, "pace_push_score", 0.0)):
            failures.append("pace_push_not_below_track6_seg_004")

    if segment.segment_id == "track6_seg_004":
        track1 = segment_by_id.get("track1_seg_003")
        if track1 and float(meta(segment, "ai_pace_push_score", 0.0)) <= float(meta(track1, "ai_pace_push_score", 0.0)):
            failures.append("ai_pace_push_not_above_track1_seg_003")
        if track1 and float(meta(segment, "ai_flow_momentum_score", 0.0)) <= float(meta(track1, "ai_flow_momentum_score", 0.0)):
            failures.append("ai_flow_not_above_track1_seg_003")
        recommended_for = set(meta(segment, "recommended_for", []))
        if not ({"steady", "pace_up"} & recommended_for):
            failures.append("missing_recommended_for_steady_or_pace_up")
        if "sprint_push" not in set(meta(segment, "avoid_for", [])):
            failures.append("missing_avoid_for_sprint_push")
        if track1:
            pace_up_rank = ranks.get("pace_up", {}).get(segment.segment_id, 999)
            track1_pace_up_rank = ranks.get("pace_up", {}).get(track1.segment_id, 999)
            steady_rank = ranks.get("steady", {}).get(segment.segment_id, 999)
            track1_steady_rank = ranks.get("steady", {}).get(track1.segment_id, 999)
            if pace_up_rank >= track1_pace_up_rank and steady_rank >= track1_steady_rank:
                failures.append(
                    f"not_ranked_above_track1_seg_003 pace_up={pace_up_rank}/{track1_pace_up_rank} "
                    f"steady={steady_rank}/{track1_steady_rank}"
                )
        if not is_groove_or_pulse_candidate(segment):
            failures.append("not_groove_or_pulse_candidate")

    return ("PASS" if not failures else "FAIL"), failures


def evaluate_global_regressions(rankings: dict[str, list[tuple[Segment, Any]]]) -> list[str]:
    failures: list[str] = []
    sprint_ranked = rankings.get("sprint_push", [])
    best_track4_rank = next(
        (idx for idx, (segment, _) in enumerate(sprint_ranked, start=1) if segment.track_id == "track4"),
        999,
    )
    best_track6_rank = next(
        (idx for idx, (segment, _) in enumerate(sprint_ranked, start=1) if segment.track_id == "track6"),
        999,
    )
    if best_track4_rank >= best_track6_rank:
        failures.append(f"sprint_track4_not_above_track6 track4={best_track4_rank} track6={best_track6_rank}")
    return failures


def build_summary_rows(
    cases: list[dict],
    segment_by_id: dict[str, Segment],
    ranks: dict[str, dict[str, int]],
) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    failed = False
    for case in cases:
        segment = segment_by_id.get(case["segment_id"])
        if segment is None:
            failed = True
            rows.append(
                {
                    **case,
                    "section_type": "missing",
                    "corrected_section_type": "missing",
                    "pass_fail": "FAIL: missing_segment",
                }
            )
            continue

        status, failures = evaluate_case(case, segment, segment_by_id, ranks)
        failed = failed or status == "FAIL"
        row = {
            "segment_id": segment.segment_id,
            "track_id": segment.track_id,
            "expected_role": case.get("expected_role", ""),
            "human_pace_push_rating": case.get("human_pace_push_rating", ""),
            "section_type": segment.section_type.value,
            "section_type_ai": meta(segment, "section_type_ai", meta(segment, "ai_corrected_section_type", "")),
            "ai_segment_role": meta(segment, "ai_segment_role", ""),
            "corrected_section_type": meta(segment, "corrected_section_type", segment.section_type.value),
            "energy_score": segment.energy_score,
            "pace_push_score": meta(segment, "pace_push_score", ""),
            "ai_pace_push_score": meta(segment, "ai_pace_push_score", ""),
            "ai_flow_momentum_score": meta(segment, "ai_flow_momentum_score", ""),
            "ai_static_low_end_penalty": meta(segment, "ai_static_low_end_penalty", ""),
            "beat_salience_score": meta(segment, "beat_salience_score", ""),
            "rhythmic_activity_score": meta(segment, "rhythmic_activity_score", ""),
            "bass_drive_score": meta(segment, "bass_drive_score", ""),
            "static_low_end_penalty": meta(segment, "static_low_end_penalty", ""),
            "drop_likelihood_score": meta(segment, "drop_likelihood_score", ""),
            "pace_role_hint": meta(segment, "pace_role_hint", ""),
            "pass_fail": status if not failures else f"FAIL: {', '.join(failures)}",
            "notes": case.get("notes", ""),
        }
        rows.append(row)
    return rows, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Pace-Assist analysis features against human labels.")
    parser.add_argument("--segments-dir", default="outputs")
    parser.add_argument("--ground-truth", default="config/pace_assist_ground_truth.json")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    ground_truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    cases = ground_truth.get("cases", [])
    segments = load_segments(args.segments_dir)
    _repo = InMemorySegmentRepository(segments)
    segment_by_id = {segment.segment_id: segment for segment in segments}

    rankings = {intention: rank_segments(segments, intention) for intention in INTENTION_CONTEXTS}
    ranks = rank_lookup(rankings)

    summary_rows, failed = build_summary_rows(cases, segment_by_id, ranks)
    global_failures = evaluate_global_regressions(rankings)
    failed = failed or bool(global_failures)

    print("\nPace-Assist Ground Truth Evaluation")
    print_table(summary_rows, SUMMARY_FIELDS)
    if global_failures:
        print("\nGlobal regressions")
        for failure in global_failures:
            print(f"FAIL: {failure}")
    else:
        print("\nGlobal regressions\nPASS")

    for intention, ranked in rankings.items():
        print(f"\nTop {args.top_k} candidates for {intention}")
        rows = [
            pace_assist_candidate_payload(segment, breakdown, rank)
            for rank, (segment, breakdown) in enumerate(ranked[: args.top_k], start=1)
        ]
        print_table(rows, DEBUG_FIELDS)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
