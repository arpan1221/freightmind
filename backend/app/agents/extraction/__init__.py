# Extraction agent — module isolation contract
# ────────────────────────────────────────────
# This package (app.agents.extraction) and its routes (app.api.routes.documents,
# app.api.routes.extraction) must NEVER import from:
#   - app.agents.analytics
#   - app.api.routes.analytics
#   - app.schemas.analytics
#
# This isolation enables standalone invocability (FR42) and is verified by
# tests/test_story_3_8.py. Violating this contract will break the standalone test.
