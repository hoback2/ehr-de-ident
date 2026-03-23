# Publish workspace to a private GitHub repo

## Goal
Create the private GitHub repository `midinas/public-ehr-deid-asset-prep`, commit the full workspace, and store large binary assets with Git LFS from the start.

## Before you publish
1. Confirm the repository should remain **private**.
2. Review the workspace for anything that should **not** leave the machine, even in a private repo:
   - PHI-containing source documents
   - secrets, tokens, SSH material, local config overrides
   - downloaded third-party model weights that should be re-fetched instead of versioned
3. Decide whether `samples/raw`, `samples/processed`, `model_assets`, and `results` should be fully versioned or only partially versioned.

If the goal is to publish the project structure and code but not local runtime artifacts, keep those large/generated directories out of the initial commit. If the goal is to mirror the entire current workspace, track the large binary content with Git LFS before the first commit.

## Recommended local prerequisites
- `git`
- `git-lfs`
- GitHub access to the `midinas` account or organization
- optional: GitHub CLI `gh`

On macOS:

```bash
brew install git-lfs gh
git lfs install
```

## Step 1: initialize the local repository
From the workspace root:

```bash
git init
git branch -M main
git lfs install
```

## Step 2: add a minimal `.gitignore`
This keeps machine-local environments and caches out of version control while still allowing the project files themselves to be committed.

Suggested `.gitignore`:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/

.venvs/
.python-version

.idea/
.vscode/
```

If you want to keep VS Code workspace settings, remove `.vscode/` from the ignore list.

## Step 3: create `.gitattributes` for Git LFS
Track large binary assets before the first commit.

Suggested starting `.gitattributes`:

```gitattributes
# Documents and images
*.pdf filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.tif filter=lfs diff=lfs merge=lfs -text
*.tiff filter=lfs diff=lfs merge=lfs -text
*.bmp filter=lfs diff=lfs merge=lfs -text

# Archives and packaged assets
*.zip filter=lfs diff=lfs merge=lfs -text
*.tar filter=lfs diff=lfs merge=lfs -text
*.gz filter=lfs diff=lfs merge=lfs -text
*.bz2 filter=lfs diff=lfs merge=lfs -text
*.xz filter=lfs diff=lfs merge=lfs -text
*.7z filter=lfs diff=lfs merge=lfs -text

# Model and tensor formats
*.bin filter=lfs diff=lfs merge=lfs -text
*.ckpt filter=lfs diff=lfs merge=lfs -text
*.gguf filter=lfs diff=lfs merge=lfs -text
*.h5 filter=lfs diff=lfs merge=lfs -text
*.onnx filter=lfs diff=lfs merge=lfs -text
*.pb filter=lfs diff=lfs merge=lfs -text
*.pt filter=lfs diff=lfs merge=lfs -text
*.pth filter=lfs diff=lfs merge=lfs -text
*.safetensors filter=lfs diff=lfs merge=lfs -text

# Workspace asset directories that are likely to contain large binaries
model_assets/** filter=lfs diff=lfs merge=lfs -text
```

Notes:
- The extension-based rules cover common sample documents and model files.
- The `model_assets/**` rule is intentionally broad because that directory is expected to contain large binaries.
- Avoid putting normal source files such as `.py`, `.md`, `.json`, or `.yaml` into LFS.

## Step 4: identify any additional large files
Before the first commit, scan for files larger than 10 MB and decide whether they should be in Git LFS.

```bash
find . -type f -size +10M \
  ! -path './.git/*' \
  ! -path './.venvs/*' \
  -print | sort
```

For any additional binary file types that appear, add matching rules to `.gitattributes` before staging.

## Step 5: create the private GitHub repo
### Option A: GitHub web UI
1. Go to GitHub and create a new repository named `public-ehr-deid-asset-prep` under `midinas`.
2. Set visibility to **Private**.
3. Do **not** initialize it with a README, `.gitignore`, or license if the local workspace will be pushed as-is.
4. Copy the repository URL.

### Option B: GitHub CLI

```bash
gh auth login
gh repo create midinas/public-ehr-deid-asset-prep --private --disable-issues --disable-wiki
```

If you want issues or wiki enabled, omit those flags.

## Step 6: stage and verify the first commit
From the workspace root:

```bash
git add .gitignore .gitattributes .
git status
git lfs ls-files
```

Verify that:
- normal source files are staged normally
- large binary files appear in `git lfs ls-files`
- nothing sensitive or accidental is staged

Then commit:

```bash
git commit -m "Initial import"
```

## Step 7: connect `origin` and push
If you created the repo in the GitHub UI:

```bash
git remote add origin git@github.com:midinas/public-ehr-deid-asset-prep.git
git push -u origin main
```

If you prefer HTTPS:

```bash
git remote add origin https://github.com/midinas/public-ehr-deid-asset-prep.git
git push -u origin main
```

## Step 8: verify on GitHub
After the push:
1. Confirm the repo is private.
2. Open a few large tracked files and confirm they were uploaded through Git LFS.
3. Check that source files render normally on GitHub.
4. Confirm no PHI-containing raw data or secrets were pushed unintentionally.

## If a large file was committed before LFS was configured
If you accidentally committed a large binary file before adding LFS rules, rewrite the local history before the first shared push:

```bash
git lfs migrate import --include="*.pdf,*.png,*.jpg,*.jpeg,*.pt,*.pth,*.onnx,*.bin,*.safetensors"
```

Then re-check:

```bash
git status
git lfs ls-files
```

If you already pushed the non-LFS history, coordinate before force-pushing rewritten history.

## Recommended first-push checklist for this workspace
- Commit project docs, scripts, parser wrappers, Docker assets, manifests, and evaluation templates.
- Do not commit `.venvs`, Python caches, or editor junk.
- Put model weights and oversized binary artifacts into Git LFS.
- Review `samples/raw` carefully before publishing because it may contain PHI.
- Review `results` carefully before publishing because outputs may preserve source content.

## Short command sequence
If the workspace is ready and already reviewed, this is the shortest safe sequence:

```bash
git init
git branch -M main
git lfs install

# create .gitignore and .gitattributes first

git add .
git status
git lfs ls-files
git commit -m "Initial import"
gh repo create midinas/public-ehr-deid-asset-prep --private --source=. --remote=origin --push
```

That command sequence works best when the GitHub CLI is already authenticated and the LFS rules were added before `git add .`.