# Branch Protection Rules

Recommended GitHub branch protection settings for the `claude-watch` repository.

## Main Branch Protection

Apply these settings to the `main` branch via **Settings > Branches > Add branch protection rule**.

### Required Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Branch name pattern** | `main` | Protect the default branch |
| **Require a pull request before merging** | Enabled | All changes go through PRs |
| **Require approvals** | 1 (or more for teams) | Code review requirement |
| **Dismiss stale pull request approvals** | Enabled | Re-review after new commits |
| **Require status checks to pass before merging** | Enabled | CI must pass |
| **Require branches to be up to date before merging** | Enabled | Prevent merge conflicts |

### Required Status Checks

Select these checks from the CI workflow:

- `test (ubuntu-latest, 3.8)`
- `test (ubuntu-latest, 3.10)`
- `test (ubuntu-latest, 3.12)`
- `test (macos-latest, 3.12)`
- `test (windows-latest, 3.12)`
- `lint`
- `type-check`

**Minimum recommended**: At least `test (ubuntu-latest, 3.12)`, `lint`, and `type-check`.

### Additional Protections

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Require conversation resolution** | Enabled | Address all review comments |
| **Require signed commits** | Optional | For high-security environments |
| **Include administrators** | Recommended | Same rules for everyone |
| **Restrict who can push** | Optional | For larger teams |
| **Allow force pushes** | Disabled | Preserve history |
| **Allow deletions** | Disabled | Prevent accidental deletion |

## Setup Instructions

### Via GitHub Web UI

1. Go to **Settings** > **Branches**
2. Click **Add branch protection rule**
3. Enter `main` as the branch name pattern
4. Enable the settings listed above
5. Click **Create** or **Save changes**

### Via GitHub CLI

```bash
# Install GitHub CLI if needed
# https://cli.github.com/

# Set branch protection (basic)
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test (ubuntu-latest, 3.12)","lint","type-check"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

### Via Terraform (Infrastructure as Code)

```hcl
resource "github_branch_protection" "main" {
  repository_id = github_repository.claude_watch.node_id
  pattern       = "main"

  required_status_checks {
    strict   = true
    contexts = [
      "test (ubuntu-latest, 3.12)",
      "lint",
      "type-check"
    ]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews           = true
  }

  enforce_admins = true

  allows_deletions    = false
  allows_force_pushes = false
}
```

## Pre-merge Checklist

Before a PR can be merged, ensure:

- [ ] All CI checks pass (tests, lint, type-check)
- [ ] At least one approval from a reviewer
- [ ] Branch is up to date with `main`
- [ ] All review comments addressed
- [ ] PR description explains the changes

## Bypassing Protection (Emergency Only)

In rare emergency situations (e.g., critical security fix), administrators can:

1. Temporarily disable "Include administrators"
2. Push the fix directly
3. Re-enable the protection immediately
4. Create a follow-up PR documenting the emergency change

**This should be documented and reviewed post-incident.**

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) - How to contribute
- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
