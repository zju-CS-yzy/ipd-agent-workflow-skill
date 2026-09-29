#!/usr/bin/env sh
# SVN server-side reference template. Set IPD_PROJECT_ROOT to a maintained
# working copy before an administrator enables this hook.
set -eu

: "${IPD_PROJECT_ROOT:?IPD_PROJECT_ROOT must name the project working copy}"
cd "$IPD_PROJECT_ROOT"
exec ipdctl verify
