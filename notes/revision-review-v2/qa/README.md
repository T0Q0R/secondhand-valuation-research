# Scope of revision QA

All 30 pages were inspected in contact sheets, with full-page checks of pages 1, 11, 12, 14–22, 29 and 30 (14 pages). This is layout review, not independent human scientific peer review.

Raw geometry reports preserve XeTeX grouped-trace extraction false positives; the line/glyph extraction adapter passed using unchanged thresholds and rejected injected real collisions. Do not report an unadapted checker PASS.

The initial verbatim-check report contains a parser false positive: its generic optional-bracket regex treats the half-open mathematical interval after \\in as an optional command argument and consumes text up to a later closing bracket. Five explicitly selected exact excerpts are checked in the final empty-findings report; source/PDF anchors are separately validated. No mathematical text was changed to appease the checker.

The correspondence checker establishes those quoted excerpts and anchors only. A–I scientific limitations and unresolved C/public-release/author/external-training items remain in REVIEW_RESPONSE.zh.md.
