# Dashboard qualification

The v0.5.1 gate replaces the unavailable external v1.4 reference with three
independent checks. The historical report and legacy adapter remain historical;
new results do not claim reconstruction of that missing reference.

## Self-contained regression

```sh
python -B -m unittest tests.test_dashboard_navigation -v
```

This covers all six task types in both locales, portable file bindings and
missing files, fact preservation, deterministic outputs, and a 300-node graph
with all five relation types. Large-graph assertions check XML, edge identity,
prerequisite → dependent direction and non-overlapping node boxes; they do not
claim pixel identity or eliminate every edge crossing.

## Actual-browser interaction

Install test-only dependencies in an isolated environment:

```sh
python -m pip install playwright==1.63.0
python -m playwright install --with-deps chromium
python -B scripts/verify_dashboard_browser.py --output <LOCAL_OUTPUT>
```

On Windows with Chrome and Edge installed, add `--channel chrome --channel
msedge`. The verifier checks both locales over `file:` and loopback HTTP, all
32 relationship selections, stable node coordinates, phase switching, sidebar
navigation, actual opening of a Unicode/special-character text file, copy-path
behavior, zoom, keyboard activation, unique SVG identifiers and JavaScript
errors. Desktop/mobile screenshots are written only to the external output
directory. Standalone SVG exports are static and retain their declared edges;
interactive filtering operates in `index.html`.

## Frozen local real-project Golden

The original project must be accessed only for enumeration, reads and hashes.
Freeze a consistent snapshot outside this checkout, preserving canonical IPD
files, referenced artifacts/evidence, the current Dashboard and sufficient Git
data to reproduce reconciliation. Compare source hashes before/after capture
and snapshot hashes; if capture was inconsistent, discard it. Do not use hard
links, symbolic links or directory junctions. Do not run any IPD commands in
the original project or frozen fixture. If possible, apply filesystem read-only
permissions to the frozen fixture; checks also assert its hashes stay unchanged.

Extract the published `v0.5.0-beta` Skill source to a separate local directory,
then run:

```sh
python -B scripts/verify_local_golden.py --fixture <FROZEN_PROJECT> --baseline-source <V050_SOURCE> --output <LOCAL_OUTPUT>
```

The verifier reproduces the stored v0.5.0 verification outcome in an independent
copy. Known failures remain expected failures: their paths/codes must match,
and the tool must not adopt a fresh baseline just to obtain a green report.
For an unambiguous legacy review subject it checks unauthorized recovery and
cross-subject rejection with zero writes, records simulated authorized recovery
only in the test copy, and verifies unrelated facts are unchanged. It checks
pure rendering, deterministic outputs, the 16-file/manifest-2.2 contract,
validation, review-step formal-refresh rejection, and unchanged verification
diagnostics. Both locale variants are created as further independent copies.
No simulated authorization constitutes a decision in the real project.

Use the resulting local report for additional browser cases:

```sh
python -B scripts/verify_dashboard_browser.py --output <BROWSER_OUTPUT> --channel chrome --channel msedge --external-projects <LOCAL_OUTPUT>/qualification.json
```

Check the original project hashes again after qualification. Differences must
be reported, including concurrent user/project edits; never overwrite or roll
back the original to make hashes match. Detailed command logs, file paths,
screenshots, snapshots and expected private facts remain outside Git and release
assets. CI runs self-contained fixtures only. A missing required local Golden
gate is reported as not executed, never passed by a mock or skip.
