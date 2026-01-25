# Branching style (Git flow)

We use a lightweight **Git Flow**.

## Branches

- `main`  
  Production-ready. Always deployable.

- `develop`  
  Integration branch for ongoing work.

- `feature/<short-description>`  
  New features (branched from `develop`, merged back into `develop`).

- `release/<version>` (optional)  
  Stabilization branch when preparing a release.

- `hotfix/<short-description>`  
  Critical fixes (branched from `main`, merged back into `main` and `develop`).

## Workflow

### Feature development
1. Create branch from `develop`:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/auth-pages
   ```
2. Commit small, descriptive commits.
3. Open a Pull Request into `develop`.

### Release (optional)
1. Create `release/x.y.z` from `develop`
2. Only bugfixes + docs on release branch
3. Merge release into `main` and tag
4. Merge back into `develop`

### Hotfix
1. Create hotfix from `main`
2. Merge into `main` + tag
3. Merge into `develop`

## Commit messages

Prefer Conventional-ish style (not strict):

- `feat(auth): add register/login/logout`
- `fix(apps): correct AppConfig paths`
- `chore(docs): add setup instructions`

## Pull request rules (recommended)

- Use PRs for all changes (except trivial docs)
- PR must:
  - pass `python manage.py check`
  - include migration files when models change
  - include a short description + screenshots for UI changes
- Prefer **squash merge** for noisy commits
