# Methods references pass (L-03, 2026-09-28)

- Landscape section 6 holds the method cites. Crossref `api.crossref.org/works/<doi>` is the
  fastest metadata check (no mailto: do not send Henry's email to third parties).
- Crossref/OpenAlex give no page range for Eilers & Marx 1996 (Stat Sci 11(2)); 89-121 left [U].
- Green et al. EPM 72(3) is dated 2011 online, 2012 in print: "Green et al. 2012" is fine.
- Woods 2017 full text is readable at pmc.ncbi.nlm.nih.gov/articles/PMC5693749/ with a browser
  UA (Europe PMC fullTextXML returns nothing for it). The app matches its parameters.
- CJ trap: the old "12 comparisons -> .70, 17 -> .80" line had no source. Kinnear 2025:
  N_CR (comparisons involving an item) >= 20, SSR >= .8. Verhavert 2019: 10-14 for .70,
  26-37 for .90. N_CR = 2 * judgements / items; CPR = judgements / items. Watch which one a
  paper means.
- Code docstrings with missing cites (told lead, not edited): eval/dimensionality.py cites
  nothing for phase randomization (Theiler 1992) or the Whittaker smoother (Eilers 2003).
