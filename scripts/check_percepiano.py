"""Load every PercePiano segment and the labels, and print counts.

Usage: uv run python scripts/check_percepiano.py
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

from pianolens.data.percepiano import (
    PercePianoStats,
    iter_percepiano,
    load_percepiano_official_means,
    load_percepiano_ratings,
    percepiano_index,
)


def main() -> None:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    idx = percepiano_index()
    stats = PercePianoStats()
    n_pedal = 0
    for ap in iter_percepiano(index=idx, stats=stats):
        n_pedal += len(ap.performance.pedal) > 0
    print(f"segment MIDI files:            {len(idx)}")
    print(f"loaded:                        {stats.loaded}, failed {len(stats.failed)}")
    for f, e in stats.failed:
        print(f"  {f}: {e[:160]}")
    print(f"segments without score xml:    {len(stats.missing_score)} {stats.missing_score[:5]}")
    print(f"segments with pedal events:    {n_pedal}")
    print(f"per work:\n{idx.groupby(['piece_id', 'work']).size().groupby('piece_id').sum()}")
    print(f"bars: {idx['bars'].value_counts().to_dict()}")
    print(f"provenance: {idx['provenance'].value_counts().to_dict()}")
    human = idx[idx["provenance"] != "synthetic"]
    print(f"performer ids: {idx['performer_id'].nunique()} "
          f"({human['performer_id'].nunique()} human)")
    print(f"segments with bar range: {idx['first_bar'].notna().sum()} "
          f"by method {idx['span_method'].value_counts().to_dict()}")

    r = load_percepiano_ratings()
    t = r.table
    rated = set(t["performance_id"])
    print(f"ratings rows (long): {len(t)}; rating submissions: {t['rating_id'].nunique()}")
    print(f"raters: {t['rater_id'].nunique()}; rated segments: {len(rated)}")
    print(f"rated segments not in MIDI index: {len(rated - set(idx['performance_id']))}")
    unrated = sorted(set(idx["performance_id"]) - rated)
    print(f"MIDI segments with no rating: {len(unrated)} {unrated[:14]}")
    per = t.groupby("performance_id")["rater_id"].nunique()
    print(f"distinct raters per segment: min {per.min()} median {per.median()} max {per.max()} "
          f"mean {per.mean():.2f}")
    multi = t.groupby(["performance_id", "rater_id", "dimension"]).size()
    print(f"(segment, rater, dim) cells with >1 rating: {(multi > 1).sum()} of {len(multi)}")
    raw = load_percepiano_ratings(drop_exact_duplicates=False)
    n_raw = raw.table.drop_duplicates(["rating_id", "rater_id", "performance_id"]).shape[0]
    print(f"distinct (rating_id, rater, segment) incl. verbatim duplicates: {n_raw}")
    off = load_percepiano_official_means()
    ours_raw = raw.mean() / 7
    common = off.index.intersection(ours_raw.index)
    print(f"official mean labels: {len(off)}; max |ours(no dedupe) - official|: "
          f"{np.abs(ours_raw.loc[common, off.columns] - off.loc[common]).max().max():.2e}")
    ours = r.mean() / 7
    common = off.index.intersection(ours.index)
    print(f"max |ours(dedupe) - official|: "
          f"{np.abs(ours.loc[common, off.columns] - off.loc[common]).max().max():.3f}")
    in_off = idx["performance_id"].isin(off.index)
    humans_rated = idx[in_off & (idx["provenance"] != "synthetic")]
    print(f"official-labelled segments by human pianists: {len(humans_rated)}, performers "
          f"{humans_rated['performer_id'].nunique()}")


if __name__ == "__main__":
    main()
