# ManiLoop contributor instructions

- Read `docs/worknotes/README.md` and the current status in `docs/worknotes/worknote.md` before substantial changes.
- Update the worknote when a meaningful milestone is completed or an important blocker/decision is discovered. Include actual validation evidence, lessons, and remaining work.
- Keep user-facing installation instructions in README and backend-specific documentation; use the worknote for engineering history.
- Preserve the sensor-only policy boundary: simulator truth, object state and evaluator outputs must never become policy inputs.
- Keep optional benchmark dependencies isolated. Do not silently change upstream task success rules, robot controllers, action scaling, or initialization distributions.
- Never commit credentials, runtime environments, downloaded benchmark assets or generated experiment outputs.
- Prefer small composable objects and explicit interfaces. Preserve existing task behavior with relevant regression checks.
