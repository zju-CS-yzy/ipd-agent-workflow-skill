# IPD workspace

`ipdctl init` owns this directory. Edit `task_profile.yaml` and the additive
`process_extensions.yaml`, then inspect `ipdctl tailor --preview --json` before
running `ipdctl tailor`. When `context --json` reports `refinement_due`, prepare
an explicit plan and inspect `ipdctl refine --plan PLAN --preview --json` before
an authorized human applies it. Run `ipdctl refresh` and `ipdctl verify` after
every governed change. Dashboard files are derived outputs.
