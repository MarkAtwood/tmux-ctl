# Publishing tmux-ctl

## PyPI

```sh
# Build
python3 -m venv .venv-build
.venv-build/bin/pip install build twine
.venv-build/bin/python -m build

# Upload to PyPI (need account + API token)
.venv-build/bin/twine upload dist/*

# Cleanup
rm -rf .venv-build dist
```

After publishing, users can:
```sh
pip install tmux-ctl
pipx install tmux-ctl
```

## Homebrew

1. Create a tap repository: `MarkAtwood/homebrew-tap`

2. Copy `homebrew/tmux-ctl.rb` to the tap repo

3. Update the formula with real sha256 hashes:
   ```sh
   # Get hash from PyPI release
   curl -sL https://files.pythonhosted.org/packages/source/t/tmux-ctl/tmux_ctl-0.1.0.tar.gz | shasum -a 256
   ```

4. Generate dependency stanzas:
   ```sh
   pipx install homebrew-pypi-poet
   poet -r tmux-ctl
   ```

5. Users can then:
   ```sh
   brew tap MarkAtwood/tap
   brew install tmux-ctl
   ```

## Version bumps

1. Update version in `pyproject.toml`
2. Update version in `homebrew/tmux-ctl.rb`
3. Tag: `git tag v0.1.0 && git push --tags`
4. Publish to PyPI
5. Update Homebrew formula sha256
