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

`assets/demo-data.json` and `assets/frames/` are a curated public illustration of the 2026-09-16 GPT-6 experiment, not a raw experiment export. Eight selected timeline points retain the real camera images, brief action explanations and selected execution feedback. The terminal result remains **official success = false**. Feedback is the result of the action associated with that step, not necessarily the instant shown in its before-image.

The complete local run, model request payloads, source snapshot, account usage, credentials, private configuration and weights are not part of the site. Future media should follow the same review and minimization process. See the [first-run report](https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/research/2026-09-16-gpt6-demo-first-run.md) for the scope and limitations.

ManiLoop source is MIT licensed. Simulation images depict the LIBERO / robosuite Panda scene; upstream projects and assets retain their respective licenses. See the repository's [third-party notes](https://github.com/Daniel-rmc/ManiLoop/blob/main/README.md#许可证与贡献).
