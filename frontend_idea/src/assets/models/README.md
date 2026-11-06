# 3D models

`lady-justice.glb` — Lady Justice, used on the left of the scene (click → the answer's scales).

* Source: `3D_Models/lady-justice/source/Lady Justice.glb` (95 MB, 4 million triangles — far too heavy for a browser).
* This copy was made with `python frontend_idea/scripts/optimize_model.py "<source>.glb" src/assets/models/lady-justice.glb --cells 220`
  → ≈ 141 000 triangles, 3.6 MB, upright, feet at y = 0, its grey cavity painting kept as vertex colours.
  More detail: `--cells 300` (heavier); lighter for phones: `--cells 160`.
* Licence: downloaded from Sketchfab by Bobur — keep the author's name and licence in `ATTRIBUTION.txt` next to this file
  (most Sketchfab downloads are CC-BY: attribution is required when the site is shown publicly).

If the file is missing, the page shows a simple gold stand-in figure instead (no error).
