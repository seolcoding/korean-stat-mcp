# KOSIS Reports

This directory keeps historical report source data and summary notes used while
developing the report-generation examples.

Generated HTML reports under `kosis-reports/html/` are intentionally not tracked.
Regenerate them locally when visual inspection is needed, then leave the output
ignored by Git.

Release packaging also excludes this directory from source distributions and
Docker build context. If a report sample is needed in package documentation,
copy the minimal excerpt into `docs/` instead of adding generated HTML or bulk
data files here.
