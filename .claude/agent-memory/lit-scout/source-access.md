# How to reach primary sources (2026-09-27)

- MDPI returns 403 to WebFetch and to curl, even with a browser UA. Use OpenAlex instead:
  `api.openalex.org/works/doi:<doi>`. Rebuild the abstract from `abstract_inverted_index`.
  OpenAlex also works for JASA and Psychology of Music abstracts.
- arXiv PDFs: `curl -sL arxiv.org/pdf/<id>` then `pdftotext` (in /opt/homebrew/bin). This is more
  reliable than WebFetch summaries, which drop numbers and tables.
- Parameter counts and licences: `huggingface.co/api/models/<id>?blobs=true` gives
  `safetensors.total` and `cardData.license`.
  Repo licences: `api.github.com/repos/<o>/<r>`, then open the LICENSE file (the API says
  NOASSERTION for CC licences).
- WebFetch summaries of papers can be wrong on details. Always grep the PDF text for the number.
