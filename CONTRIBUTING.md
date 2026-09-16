# Contributing

Follow [README.md](README.md) to create a Python environment, then install test
dependencies and run the offline suite:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m maniloop smoke
```

The first check does not need graphics or an API key. The second renders cameras
and needs a working OpenGL backend. Neither makes a paid model request.

Keep model observations limited to the public sensor contract. Do not send hidden
object positions or independent evaluation results to the policy. Do not replace
contact physics with object attachments or hidden scripted grasp behavior.

For behavior changes, include a focused regression test and distinguish simulated
controller validation from live model performance. Report the OS, Python and
package versions when describing a rendering or installation issue.

Do not include keys, auth.json, private config files, raw provider error bodies,
or personal run logs in issues or pull requests. Retain asset provenance and
upstream license notices when modifying or adding robot assets.

Optional LIBERO contributions must preserve the pinned upstream task/controller
contract and pass the opt-in checks documented in [LIBERO.md](docs/LIBERO.md).

## Git workflow

The canonical repository is https://github.com/Daniel-rmc/ManiLoop and the default
branch is `main`. Create a short-lived branch for each feature or fix, make focused
commits, and open a pull request with the problem, changed behavior and validation.
Check GitHub Actions before merging.

For a new checkout:

```sh
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
git switch -c feature/your-change
```

Before committing, inspect `git status` and `git diff --staged` to confirm only the
intended source, tests and documentation are included. Keep downloaded models,
virtual environments, benchmark installations and generated runs out of Git.
