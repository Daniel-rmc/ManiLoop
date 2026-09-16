# ManiLoop project website

Static showcase at <https://daniel-rmc.github.io/ManiLoop/>. The actual simulator and model calls run locally; this site never accepts credentials or starts inference.

## Preview

From the repository root:

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:8080/>. All assets are relative, so the page also works below the `/ManiLoop/` project path. There is no package install, external font, analytics script or build step.

## Publish

Website source lives in `main:site/`. GitHub Pages serves the root of `gh-pages`; `.nojekyll` keeps it a plain static site. After reviewing and committing changes:

```bash
git push origin main
git subtree push --prefix site origin gh-pages
```

This is a normal fast-forward publication. Do not force-push if the remote diverges; inspect its changes first. Pages is configured once in repository Settings → Pages → Deploy from a branch → `gh-pages` / root. Check the Pages deployment and live site after publishing.

## Public demo media

`assets/demo-data.json` and `assets/episodes/20260916-172331-d3bc5ef2/` present one reviewed GPT-6 episode from 2026-09-16. Initial official success is false; final **LIBERO check_success is true** after 46 decisions and 706 native control steps. The MP4 contains initialization and every control step from this same attempt, including its grasp retries: 707 dual-camera frames at 20 fps, 35.35 seconds. Model waiting time is omitted while controlled simulation is frozen. It is not a concatenation of successful segments.

The official evaluator stops the episode during the final descent. The gripper is still closed; no additional release or withdrawal was executed after termination. The site displays this boundary explicitly. This one development episode cannot establish a benchmark success rate.

Eight selected timeline points provide decision context alongside the continuous video. These retain real camera images, brief action explanations and available execution feedback. Feedback belongs to the corresponding action, not necessarily the instant shown in a before-image. The final interrupted action has no fabricated completion feedback. `assets/frames/` remains as media from the earlier failed attempt; it is not the current main demonstration.

The raw local run, model request payloads, source snapshot, account usage, credentials, private configuration and weights are not part of the site. Future media should follow the same review and minimization process. See the [success report](https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/research/2026-09-16-gpt6-success-episode.md) for evidence and scope. The [first-run failure report](https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/research/2026-09-16-gpt6-demo-first-run.md) and v0.2.0 history remain available.

ManiLoop source is MIT licensed. Simulation images depict the LIBERO / robosuite Panda scene; upstream projects and assets retain their respective licenses. See the repository's [third-party notes](https://github.com/Daniel-rmc/ManiLoop/blob/main/README.md#许可证与贡献).
