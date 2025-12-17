def compare_reports(new, baseline):
    new_fails = []
    known_fails = []
    fixed_fails = []

    baseline_sigs = set(baseline.keys())
    new_sigs = set()

    for f in new:
        sig = f["testcase"] + "|" + f["error"]
        new_sigs.add(sig)

        if sig in baseline_sigs:
            known_fails.append(f)
        else:
            new_fails.append(f)

    fixed = baseline_sigs - new_sigs

    return {
        "new": new_fails,
        "known": known_fails,
        "fixed": list(fixed)
    }
