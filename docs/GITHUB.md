# GitHub Publishing Checklist

## 1. Create a repository

Create an empty GitHub repository, for example:

```text
second-brain-for-devs
```

Do not add a README, license, or `.gitignore` in GitHub if they already exist locally.

## 2. Initialize local git

```bash
git init
git add .
git status
git commit -m "Initial reusable RAG toolkit"
```

## 3. Connect remote and push

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USER/second-brain-for-devs.git
git push -u origin main
```

## 4. After push

Update `pyproject.toml` URLs from:

```text
https://github.com/mentalprotector/second-brain-for-devs
```

to the real repository URL.
