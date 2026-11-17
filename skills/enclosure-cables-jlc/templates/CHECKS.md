# <device name>: checks

Written by `scripts/check_all.py` into `out/CHECKS.md` from `out/checks/*.json`. Do not edit by hand: change the source, run the build, run `check_all.py` again.

Headline: passed <N>, failed <N>, could not run <N>, not applicable <N>, waived <N>. A row whose input file changed after the check is STALE and counts as failed. A check that could not run is not a pass. A failed or could-not-run row accepted in `waivers.toml` is printed WAIVED with its reason, who and date and counted apart; it never hides a STALE row.

| ID | Section | Check | Value | Rule | Verdict |
|---|---|---|---|---|---|
