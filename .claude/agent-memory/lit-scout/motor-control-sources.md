# Motor-control sources (L-04, 2026-09-27); written up in landscape section 1.5

- Open full texts via Europe PMC:
  - URL: `ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML`, then strip the tags.
  - Available: van Vugt 2012 PMC3499913; van Vugt 2013 PMC3604639; chronotype PMC3705811;
    Cheng 2013 PMC3865372; Tominaga 2016 PMC4990412; Kim 2021 PMC8133499; Dalla Bella 2011
    PMC3121738; Bernays 2014 PMC3941302.
  - Find a PMCID with `europepmc .../search?query=DOI:<doi>&format=json`.
- Paywalled, values unseen:
  - Jabusch 2004 Mov Disord; Repp 1996 Psych Music; Repp 1997 Psych Res (abstract elided
    everywhere; only the Semantic Scholar TLDR); Liang JAES 2018 full text.
  - The QMUL PDF host (eecs.qmul.ac.uk) hangs or has a bad cert: curl timed out, WebFetch hit a
    cert error.
- The JKU "Investigations_of_Between-Hand_Synchronization" PDF is really the SMC 2009 paper, not
  the CMJ 2010 one. Numbers: n = 163,208, mean 4.4 ms, mode 13 ms (lower minus upper staff).
- The "13 pianists, 8.1/8.9 ms" Jabusch 2004 claim comes only from a drummers paper
  (PMC7693443). It conflicts with the abstract's n = 8 healthy pianists. Unresolved.
- Kim 2021 group means for rIOI SD and velocity SD are only in figures. Its data are
  IRB-restricted.
- SKY-Piano (ISMIR 2026) has a Disklavier slow C-major scale played by 7 pros and 12 amateurs.
  It is the best open candidate for an expert vs amateur `even_*` check. Its dataset licence was
  not checked.
- No pedal-timing norms and no Alberti-evenness values exist in anything I could open.
