# GitHub Release Checklist

Use this checklist for every GitHub release. Items under “Repository baseline” describe the prepared `0.1.0a1` source; rerun them after any source change. Items under “GitHub and publication” require the future repository owner or release operator.

## Repository baseline

- [x] Public capability claims map to implemented modules and behavior tests.
- [x] `SKILL.md` has valid frontmatter, a discriminating description, reference routing, and an explicit human-approval boundary.
- [x] Package, Skill, changelog, and intended tag use `ipd-agent-workflow-skill` / `0.1.0a1` consistently.
- [x] State and policy schemas reject unknown fields and document semantic checks performed by `ipdctl`.
- [x] Final TR/DCP approval requires an authorized human record and rejects a conflicting authorized-human rejection.
- [x] README, architecture, deployment, contribution, security, changelog, and full license files are present.
- [x] CI installs the package and runs behavior, CLI, and release-hygiene checks on the minimum and latest supported Python lines.
- [x] From the final source, run `python -B -m unittest discover -s tests -v` (14 tests passed).
- [x] From the final source, run the Skill validator and `python -B -m ipdctl --help`.
- [x] Build a wheel into a temporary directory and smoke-test the installed `ipdctl` outside the checkout.
- [x] Run `python -B scripts/release_check.py .`; no cache, temporary files, build output, generated state output, credentials, personal paths, or high-confidence secret patterns were found.
- [x] Run `git diff --check` and inspect `git status --short`; all listed files are intended source. Repeat after the first `git add`, because the initial repository currently contains only untracked files.
- [x] Review the complete Git history for secrets before the first push. This newly initialized repository has no commits or prior history; repeat after creating the release commit.

## Version and release content

- [ ] Freeze the release commit and confirm `pyproject.toml`, `ipdctl.__version__`, changelog, tag, and GitHub Release title all use `0.1.0a1` / `v0.1.0a1`.
- [ ] Write release notes that call out alpha compatibility, human approval requirements, supported Python versions, and known limitations.
- [ ] Create the annotated tag from the reviewed clean commit; never reuse or silently move a published tag.
- [ ] Attach only intentional release artifacts and checksums. Do not commit wheel, sdist, coverage, or generated IPD output to the source branch.
- [ ] Test a fresh source archive and, if published, the wheel in clean temporary locations.

## GitHub and publication

- [x] Use `zju-CS-yzy/ipd-agent-workflow-skill` as the canonical GitHub repository and include its URLs in project metadata and documentation.
- [ ] Create the remote repository and push the reviewed default branch and tag.
- [ ] Require CI and review on the default branch; restrict force pushes and tag mutation.
- [ ] Enable private vulnerability reporting and set a real private maintainer contact or security advisory process.
- [ ] Set repository description, topics, license display, Actions permissions, and release visibility.
- [ ] Confirm GitHub Actions passes for the pushed commit and that the README, Skill files, license, and source archive render correctly.
- [ ] After publication, install from the public source/wheel and run `ipdctl --help` plus a temporary-project init/validate smoke test.
