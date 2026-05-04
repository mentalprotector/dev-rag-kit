# GitHub Publishing Checklist

## 1. Repository

Recommended repository name:

```text
dev-rag-kit
```

If the repository already exists under an old name, rename it in GitHub and update the local remote:

```bash
git remote set-url origin https://github.com/YOUR_USER/dev-rag-kit.git
```

## 2. Initial publish

```bash
git init
git add .
git status
git commit -m "Initial reusable RAG toolkit"
git branch -M main
git remote add origin https://github.com/YOUR_USER/dev-rag-kit.git
git push -u origin main
```

## 3. Release checklist

- Keep `.env`, local Qdrant data, evaluation reports, and `.repo-check/` out of git.
- Verify `pyproject.toml` URLs point to the real repository.
- Run `python -m pytest -q` before pushing.
- Build the package with `python -m build` when preparing a release artifact.
