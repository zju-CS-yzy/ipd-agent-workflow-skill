# Published dashboard exports

The canonical generated dashboard is `.ipd/dashboard/`. Copy or publish an
approved snapshot here only when the project requires it.

Use `ipdctl render-dashboard` when a current inspection view is needed during
an active iteration; it does not change project or runtime facts. Use formal
`ipdctl refresh` only at its allowed workflow boundary. The generated
`.ipd/dashboard/governance.md` file is a facts-derived registry and Gate plan,
not an editable governance source or acceptance record.
