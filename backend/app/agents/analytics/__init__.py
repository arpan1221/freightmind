# Analytics agent — module isolation contract
# ────────────────────────────────────────────
# This package (app.agents.analytics) and its route (app.api.routes.analytics)
# must NEVER import from:
#   - app.agents.extraction
#   - app.models.extracted_document
#   - app.models.extracted_line_item
#
# This isolation enables standalone invocability (FR41) and is verified by
# tests/test_story_2_7.py. Violating this contract will break the standalone test.
