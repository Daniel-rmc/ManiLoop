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

For substantial work, read [worknote rules](docs/worknotes/README.md) and the
[current worknote](docs/worknotes/worknote.md). Update the worknote at meaningful
milestones, including actual validation, problems, decisions and remaining work.
Optional LIBERO contributions must preserve the pinned upstream task/controller
contract and pass the opt-in checks documented in [LIBERO.md](docs/LIBERO.md).
