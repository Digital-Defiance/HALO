# Construction references

Checked 2026-10-27. Local PDFs are ignored by Git; the source links below are
the reproducible references.

## Mann 2004 — obtained

Casey Mann, "Heesch's Tiling Problem", *American Mathematical Monthly* 111(6),
509–517 (2004).

- Author-hosted PDF: <https://faculty.washington.edu/cemann/Heesch.pdf>
- DOI: <https://doi.org/10.1080/00029890.2004.11920105>
- Local copy: `mann_2004_heesch.pdf`, 9 pages, verified PDF and visually inspected
  page 4 (printed page 512), Figures 5–6.
- SHA-256: `8ab554449e5c6cb5b6c17e3f77335a0a8b1fd23ceaa9af1644f03ea658b46740`

Theorem 1 gives H=4 for the 2- and 3-hexapillars, and H=5 for n-hexapillars
with n>=4. These are hexagon chains with geometric edge markings. This supplies
a construction to reproduce, not an already certified unmarked O/H/I tile
within HALO's size and coordinate-span limits.

## Bašić 2021 — full text and figure accessible

Bojan Bašić, "A Figure with Heesch Number 6: Pushing a Two-Decade-Old Boundary",
*The Mathematical Intelligencer* 43, 50–53 (2021).

- Full text and figures: <https://pmc.ncbi.nlm.nih.gov/articles/PMC7812982/>
- DOI: <https://doi.org/10.1007/s00283-020-10034-w>
- The full text describes six hexagons, eleven equilateral triangles and half
  an equilateral triangle; Figure 1 was inspected.
- Both attempted PDF endpoints returned HTML. No invalid `.pdf` is retained.
  The accessible full text is sufficient to start geometric feasibility work.

The half-triangle matters: a direct conversion into equilateral-triangle cells
cannot simply be assumed. Check supported grids, intended placements and exact
cell/span costs before promising a realization. Enlarging a drawing does not
automatically preserve its Heesch number.

## Additional sources

- Mann and Thomas, "Heesch Numbers of Edge-Marked Polyforms", *Experimental
  Mathematics* 25(3), 281–294 (2016):
  <https://doi.org/10.1080/10586458.2015.1096867>. This is the published paper
  following the 2006 abstract in the original plan.
- Kaplan, *Heesch Numbers of Unmarked Polyforms*:
  <https://cs.uwaterloo.ca/~csk/heesch/unmarked.pdf>.
- Current target and verifier limits:
  <https://epoch.ai/frontiermath/open-problems/heesch-number>.

See `RESEARCH_PLAN.md` for the experiment order and its acceptance gates.
