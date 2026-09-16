# Offline execution-feedback audit

This tool checks existing LIBERO `tcp_target_servo_v2` recordings. It does not call a model, start a simulator, alter recordings, or change policy inputs.

```bash
python -m maniloop.research.feedback_audit \
  runs/your-recorded-episode \
  --output artifacts/research/feedback-audit-01
```

Pass several episode directories to analyze them together. The output directory must be new and outside the original episode directories. The command refuses to overwrite existing output.

Each episode must contain `manifest.json`, `result.json`, `events.jsonl`, numbered observation/context JSON files, and a complete `recording/` directory. Native frame indexes and both camera image hashes are checked with the existing recording verifier. This tool currently supports the target-servo interface, not VLA action chunks or other control protocols.

Outputs:

- `audit.json`: per-request evidence, run-level summaries, input hashes and separate independent evaluation.
- `requests.csv`: per-request numerical diagnostics. Units are indicated by column names; absent values mean unavailable, not zero.

**Human analysis only.** The JSON contains independent evaluation and is marked `policy_input: false`. Do not send either output to a robot policy as observation or context. These artifacts are generated under the ignored `artifacts/` directory by the example command.

## What is checked

For a move with requested translation `u` and reported actual translation `d`, the tool reconstructs the TCP residual vector as `u - d` and its Euclidean norm as the scalar TCP error. For a gripper command that holds the arm pose, `u = 0`. This calculation uses the execution feedback's displacement; it does not assume that the request snapshot and later image correspond exactly to the execution endpoints.

For controlled runs, recorded request and transition states are matched to native frames. The reported feedback duration identifies a candidate feedback endpoint, which is checked against the actual displacement. A later transition frame is kept separate, including any time gap and drift. Realtime execution does not receive the same endpoint-alignment assumption.

The audit distinguishes:

- requests, returned decisions, accepted actions, rejections, execution events and transitions;
- logged feedback versus a terminal endpoint reconstructed from native recording frames;
- a model's `done` declaration versus independent task evaluation;
- `reached`, `completed`, `timed_out` and interrupted execution;
- feedback appearing in the current observation and in historical context.

If an accepted final action is interrupted by a recorded environment termination, a missing feedback endpoint may be reconstructed from the last native frame in a controlled run. Its `endpoint_source` is `terminal_native_frame`; no feedback status is invented, and the reconstruction is not treated as information received by the model. This applies to recorded environment termination, not only successful episodes.

`feedback_occurrences` counts numeric `position_error_m` fields in that request's saved observation and context. `latest_residual_occurrences` counts values equal to the latest observation residual. Coincidentally equal numbers can contribute to this count; it is a representation diagnostic, not a count of independent experiences.

## Reading warnings and boundaries

Missing snapshots, forbidden structured fields, mismatched action/state/history copies and uncertain alignments produce row-level `flags`. These rows remain visible for diagnosis; their presence in the report does not mean the evidence passed validation. Corrupted native recording hashes or inconsistent final evaluation stop the audit. Events without explicit request IDs remain listed as unindexed; the tool does not silently assign them to the nearest request.

The sensor check covers saved structured observation/context fields using the existing policy guard. It does not inspect image semantics, prove absence of prompt-based hints, or capture the exact remote provider transport. The audit hashes native camera files but does not assert that every image actually sent to the model is byte-identical to those files.

TCP residual is command-tracking error, not object localization error, grasp success or task progress. `timed_out` may reflect velocity, orientation, gripper or stability criteria as well as position. Recorded examples are descriptive evidence, not a benchmark sample, causal feedback ablation or demonstration of learning.

The per-run source digest and comparison group are retained. A combined report does not make different source versions or control settings directly comparable. It deliberately does not compute a pooled task success rate.
