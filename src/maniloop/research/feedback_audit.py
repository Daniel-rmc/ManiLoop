"""Audit saved action/feedback evidence without model calls or simulation.

Outputs contain independent evaluation and are for human analysis only. They
must never be supplied as policy observations. Original run files are read-only.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from maniloop.core.observations import PAIR_SENSOR_FIELDS, guard_sensor_tree
from maniloop.recording.video import verify_episode


TOLERANCE = 1e-8


def _read(path):
    if path.is_symlink():
        raise ValueError(f"Symlink input is not supported: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def _vector(value):
    if (not isinstance(value, list) or len(value) != 3
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        return None
    return value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _norm(value):
    return math.sqrt(sum(x * x for x in value))


def _subtract(a, b):
    return [x - y for x, y in zip(a, b)]


def _residuals(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "position_error_m" and _number(item):
                yield item
            else:
                yield from _residuals(item)
    elif isinstance(value, list):
        for item in value:
            yield from _residuals(item)


def _index_at(observation, frames, dt):
    time = observation.get("simulation_time")
    pos = _vector(observation.get("tcp_position"))
    if not _number(time) or pos is None:
        return None
    index = round(time / dt)
    if (not 0 <= index < len(frames)
            or not math.isclose(time, index * dt, abs_tol=TOLERANCE)):
        return None
    native_pos = _vector(frames[index].get("sensors", {}).get("tcp_position"))
    if native_pos is None or _norm(_subtract(pos, native_pos)) > TOLERANCE:
        return None
    for key in ("joint_positions", "joint_velocities", "tcp_rotation_matrix",
                "tcp_quaternion_xyzw", "gripper_opening"):
        if key in observation and observation[key] != frames[index].get("sensors", {}).get(key):
            return None
    return index


def audit_run(run):
    """Return a human-only ledger for one recorded tcp_target_servo_v2 run.

    Scalar residual reconstruction uses command minus reported displacement,
    not an assumption that request and feedback images share execution times.
    Native endpoint reconstruction is restricted to controlled, aligned runs.
    Missing evidence is flagged rather than silently counted as a passed check.
    """
    run = Path(run)
    if run.is_symlink():
        raise ValueError("Symlink run directories are not supported")
    manifest, result = _read(run / "manifest.json"), _read(run / "result.json")
    policy = manifest.get("policy", {})
    interface = policy.get("action_interface", manifest.get("llm_control"))
    if interface != "tcp_target_servo_v2":
        raise ValueError("This audit requires tcp_target_servo_v2 recordings")
    event_path = run / "events.jsonl"
    if event_path.is_symlink() or (run / "recording").is_symlink():
        raise ValueError("Symlink evidence is not supported")
    if any((run / "recording" / name).is_symlink() for name in ("episode.json", "frames.jsonl")):
        raise ValueError("Symlink recording indexes are not supported")
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(event, dict) for event in events):
        raise ValueError("Expected JSON event objects")
    metadata, frames = verify_episode(run / "recording")
    dt = metadata["control_timestep"]
    controlled = policy.get("timing", manifest.get("experiment", {}).get("timing")) == "controlled"
    count = sum(e.get("type") == "request" for e in events)
    grouped = {}
    unindexed = []
    for line, event in enumerate(events, 1):
        index = event.get("request_index")
        if type(index) is int:
            if not 1 <= index <= count:
                raise ValueError("Event request_index outside recorded requests")
            grouped.setdefault(index, []).append(event)
        elif event.get("type") in {"rejected", "decision", "execution", "transition", "accepted"}:
            unindexed.append({"line": line, "type": event["type"]})
    source_paths = [run / name for name in ("manifest.json", "result.json", "events.jsonl",
                                           "recording/episode.json", "recording/frames.jsonl")]
    rows = []
    for index in range(1, count + 1):
        group = grouped.get(index, [])
        by_type = {}
        for event in group:
            kind = event.get("type")
            if kind in by_type and kind in {"decision", "accepted", "execution", "transition"}:
                raise ValueError(f"Ambiguous duplicate {kind} for request {index}")
            by_type[kind] = event
        decision = by_type.get("decision", {})
        action = decision.get("action", {})
        transition = by_type.get("transition", {}).get("transition", {})
        feedback = transition.get("feedback") or by_type.get("execution", {}).get("feedback") or {}
        feedback_source = "transition" if transition.get("feedback") else "execution" if feedback else "none"
        row = {"request_index": index, "kind": action.get("kind"),
               "accepted": "accepted" in by_type, "decision_present": bool(decision),
               "feedback_source": feedback_source, "feedback_status": feedback.get("status"),
               "requested_translation_m": None, "actual_translation_m": None,
               "residual_recomputed_m": None, "residual_reported_m": None,
               "residual_difference_m": None, "endpoint_source": "none",
               "native_start_step": None, "native_end_step": None,
               "feedback_occurrences": 0, "latest_residual_occurrences": 0,
               "flags": []}
        flags = row["flags"]
        observation, context = {}, {}
        for suffix in ("observation", "context"):
            path = run / f"{index:03d}-{suffix}.json"
            if not path.is_file():
                flags.append(f"missing_{suffix}")
                continue
            source_paths.append(path)
            value = _read(path)
            try:
                guard_sensor_tree(value)
            except ValueError:
                flags.append(f"forbidden_or_unsupported_{suffix}_fields")
            if suffix == "observation":
                observation = value
            else:
                context = value
        occurrences = list(_residuals(observation)) + list(_residuals(context))
        row["feedback_occurrences"] = len(occurrences)
        latest = observation.get("last_feedback", {}).get("position_error_m")
        if _number(latest):
            row["latest_residual_occurrences"] = sum(v == latest for v in occurrences)
        row["history_actions"] = sum("action" in item for item in context.get("history", []))
        row["history_transitions"] = sum("transition" in item for item in context.get("history", []))
        for item in context.get("history", []):
            if "transition" in item:
                prior = item["transition"]
                prior_index = prior.get("request_index")
                matches = [e.get("transition") for e in grouped.get(prior_index, []) if e.get("type") == "transition"]
                if type(prior_index) is not int or not 1 <= prior_index < index or prior not in matches:
                    flags.append("context_transition_mismatch")
            elif "action" in item:
                matches = []
                for prior_index, prior_events in grouped.items():
                    if prior_index >= index:
                        continue
                    if any(e.get("action") == item["action"] for e in prior_events if e.get("type") == "decision"):
                        matches.extend(e["feedback"] for e in prior_events if "feedback" in e)
                        matches.extend(e["transition"].get("feedback") for e in prior_events if "transition" in e)
                if item.get("feedback") not in matches:
                    flags.append("context_action_feedback_mismatch")
        if decision and action.get("observation_id") != observation.get("observation_id"):
            flags.append("action_observation_mismatch")
        if transition:
            if transition.get("request_index") != index or transition.get("action") != action:
                flags.append("transition_action_mismatch")
            if transition.get("before", {}).get("observation_id") != observation.get("observation_id"):
                flags.append("transition_observation_mismatch")
            expected_before = {key: value for key, value in observation.items() if key in PAIR_SENSOR_FIELDS}
            if transition.get("before") != expected_before:
                flags.append("transition_before_sensor_mismatch")
            if (by_type.get("execution", {}).get("feedback") is not None
                    and by_type["execution"]["feedback"] != feedback):
                flags.append("execution_transition_feedback_mismatch")
        if row["accepted"] and transition and "execution" not in by_type:
            flags.append("missing_execution_event")
        if row["accepted"] and "execution" in by_type and not transition:
            flags.append("missing_transition_event")
        if "rejected" in by_type:
            row["outcome"] = "rejected"
        elif action.get("kind") == "done":
            row["outcome"] = "model_done"
        elif row["accepted"]:
            row["outcome"] = "accepted"
        else:
            row["outcome"] = "no_execution_evidence"
        start = _index_at(observation, frames, dt)
        row["native_start_step"] = start
        if start is None:
            flags.append("request_native_alignment_unverified")
        delta = [0.0, 0.0, 0.0] if action.get("kind") == "gripper" else _vector(action.get("delta_position"))
        if delta is not None:
            row["requested_translation_m"] = _norm(delta)
        actual = _vector(feedback.get("actual_delta_position"))
        reported = feedback.get("position_error_m")
        if _number(reported):
            row["residual_reported_m"] = reported
        for field in ("rotation_error_rad", "linear_speed_m_s", "angular_speed_rad_s", "gripper_speed_s"):
            if _number(feedback.get(field)):
                row[field] = feedback[field]
        limits = observation.get("action_limits", {}).get("target_tracking", {})
        position_limit = limits.get("position_tolerance_m")
        rotation_limit = limits.get("rotation_tolerance_rad")
        if (row["accepted"] and action.get("kind") == "move" and feedback.get("status") == "timed_out"
                and all(_number(v) for v in (reported, feedback.get("rotation_error_rad"), position_limit, rotation_limit))):
            row["timed_out_pose_within_tolerances"] = (reported <= position_limit
                and feedback["rotation_error_rad"] <= rotation_limit)
        if row["accepted"] and delta is not None and actual is not None:
            row["endpoint_source"] = "recorded_feedback"
            row["actual_translation_m"] = _norm(actual)
            row["residual_vector_m"] = _subtract(delta, actual)
            row["residual_recomputed_m"] = _norm(row["residual_vector_m"])
            if _number(reported):
                difference = abs(row["residual_recomputed_m"] - reported)
                row["residual_difference_m"] = difference
                if difference > TOLERANCE:
                    flags.append("residual_mismatch")
            else:
                flags.append("missing_reported_residual")
            steps = feedback.get("control_steps")
            row["feedback_control_steps"] = steps
            if controlled and start is not None and type(steps) is int and steps > 0 and start + steps < len(frames):
                end = start + steps
                end_pos = _vector(frames[end]["sensors"].get("tcp_position"))
                native_actual = _subtract(end_pos, observation["tcp_position"]) if end_pos else None
                if native_actual is not None and _norm(_subtract(actual, native_actual)) <= TOLERANCE:
                    row["native_end_step"] = end
                else:
                    flags.append("feedback_native_alignment_mismatch")
            else:
                flags.append("feedback_native_alignment_unverified")
        elif row["accepted"]:
            flags.append("missing_execution_feedback")
            # This is an offline reconstruction, never a retroactively recorded
            # model observation. Independent terminal status is kept at run level.
            if (controlled and index == count and start is not None and start < len(frames) - 1
                    and delta is not None and action.get("kind") in {"move", "gripper"}
                    and result.get("termination_reason") == "environment_terminated"
                    and metadata.get("evaluation", {}).get("terminated") is True):
                actual = _subtract(frames[-1]["sensors"]["tcp_position"], observation["tcp_position"])
                row.update(endpoint_source="terminal_native_frame", native_end_step=len(frames) - 1,
                           actual_translation_m=_norm(actual), residual_vector_m=_subtract(delta, actual),
                           residual_recomputed_m=_norm(_subtract(delta, actual)))
                flags.append("terminal_endpoint_reconstructed_not_observed_feedback")
        after = transition.get("after", {})
        if after:
            after_step = _index_at(after, frames, dt)
            row["transition_after_step"] = after_step
            if after_step is None:
                flags.append("transition_after_alignment_unverified")
            if row["native_end_step"] is not None and after_step is not None:
                row["after_feedback_gap_steps"] = after_step - row["native_end_step"]
                pos_at_end = frames[row["native_end_step"]]["sensors"]["tcp_position"]
                row["after_feedback_drift_m"] = _norm(_subtract(after["tcp_position"], pos_at_end))
                if after_step != row["native_end_step"]:
                    flags.append("transition_after_differs_from_feedback_time")
        if row["native_end_step"] is not None and start is not None:
            row["native_executed_steps"] = row["native_end_step"] - start
        rows.append(row)
    counts = Counter(e.get("type") for e in events)
    residuals = [r["residual_recomputed_m"] for r in rows if r["endpoint_source"] == "recorded_feedback"]
    differences = [r["residual_difference_m"] for r in rows if r["residual_difference_m"] is not None]
    statuses = Counter(r["feedback_status"] for r in rows if r["accepted"] and r["feedback_status"])
    summary = {"requests": count, "decisions": counts["decision"],
               "accepted_actions": counts["accepted"], "rejections": counts["rejected"],
               "execution_events": counts["execution"], "transition_events": counts["transition"],
               "unindexed_rejections": sum(e["type"] == "rejected" for e in unindexed),
               "native_aligned_actions": sum(r["native_end_step"] is not None for r in rows),
               "native_aligned_action_steps": sum(r.get("native_executed_steps", 0) for r in rows),
               "terminal_reconstructions": sum(r["endpoint_source"] == "terminal_native_frame" for r in rows),
               "timed_out_moves_with_pose_in_tolerance": sum(r.get("timed_out_pose_within_tolerances", False) for r in rows),
               "recorded_feedback_statuses": dict(statuses),
               "recorded_residual_count": len(residuals),
               "recorded_residual_median_m": statistics.median(residuals) if residuals else None,
               "recorded_residual_max_m": max(residuals, default=None),
               "max_residual_reconstruction_difference_m": max(differences, default=None),
               "control_steps": len(frames) - 1,
               "flags": dict(Counter(flag for r in rows for flag in r["flags"]))}
    evaluation = {key: result.get("evaluation", {}).get(key) for key in
                  ("success", "current_success", "terminated", "evaluator", "control_steps")}
    if any(evaluation[k] != metadata.get("evaluation", {}).get(k) for k in evaluation):
        raise ValueError("Result evaluation differs from recording metadata")
    return {"format": "maniloop_feedback_audit_v1", "policy_input": False,
            "run_id": run.name, "scope": "Offline descriptive audit, not a learning or success-rate estimate",
            "provenance": {"model": policy.get("model"), "timing": policy.get("timing"),
                           "action_interface": interface, "source_sha256": manifest.get("source_sha256"),
                           "comparison_group": manifest.get("comparison_group"),
                           "task": manifest.get("instruction"), "images_verified": True,
                           "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            "source_files_sha256": {str(p.relative_to(run)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in source_paths},
            "summary": summary, "rows": rows, "unindexed_events": unindexed,
            "termination_reason": result.get("termination_reason"), "evaluation": evaluation}


def write_audit(runs, output):
    """Write a new audit directory; refuse to overwrite any existing artifact."""
    runs, output = [Path(p) for p in runs], Path(output)
    if not runs:
        raise ValueError("Provide at least one recorded run")
    if output.exists():
        raise FileExistsError("Audit output already exists")
    if any(output.resolve().is_relative_to(run.resolve()) for run in runs):
        raise ValueError("Audit output must be outside original run directories")
    audits = [audit_run(run) for run in runs]
    report = {"format": "maniloop_feedback_collection_v1", "policy_input": False,
              "scope": "Selected existing episodes; not an independent benchmark sample",
              "runs": audits}
    output.mkdir(parents=True, exist_ok=False)
    (output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    flat = [{"run_id": audit["run_id"], **row} for audit in audits for row in audit["rows"]]
    fields = list(dict.fromkeys(key for row in flat for key in row)) or ["run_id", "request_index"]
    with (output / "requests.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in flat:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="Explicit recorded run directories")
    parser.add_argument("--output", required=True, type=Path, help="New human-analysis directory")
    args = parser.parse_args()
    try:
        report = write_audit(args.runs, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Audit failed: {error}\n")
    print(json.dumps({"output": str(args.output), "runs": len(report["runs"]),
                      "requests": sum(a["summary"]["requests"] for a in report["runs"]),
                      "policy_input": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
