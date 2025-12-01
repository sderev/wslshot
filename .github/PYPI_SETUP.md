# PyPI Publishing Setup

Two options for authenticating GitHub Actions to publish to PyPI.

## Option 1: Manual API Token (Traditional)

1. Generate token at https://pypi.org/manage/account/token/
   - Scope: "Entire account" or specific to `wslshot` project
   - Copy the token (starts with `pypi-`)

2. Add to GitHub Secrets:
   - Go to: `Settings > Secrets and variables > Actions`
   - Click `New repository secret`
   - Name: `PYPI_API_TOKEN`
   - Value: paste your token
   - Click `Add secret`

3. Workflow will use: `pypa/gh-action-pypi-publish@release/v1`
   - Automatically uses `PYPI_API_TOKEN` from secrets

## Option 2: Trusted Publishers / OIDC (Modern, More Secure)

No tokens needed - GitHub authenticates directly with PyPI.

1. Configure on PyPI:
   - Go to: https://pypi.org/manage/project/wslshot/settings/publishing/
   - Add a new publisher:
     - Repository owner: `sderev`
     - Repository name: `wslshot`
     - Workflow name: `release.yml`
     - Environment name: `release`

2. Update workflow (if needed):
   ```yaml
   permissions:
     id-token: write  # Required for trusted publishing
     contents: write
   ```

3. Remove `PYPI_API_TOKEN` secret from GitHub (no longer needed)

4. Workflow will use OIDC authentication automatically

## Verification

After setup, test by creating a GitHub release. Check Actions tab for workflow run.
