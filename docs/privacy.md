# Privacy

PersonaForge stores the SQLite database and imported material locally. Put private files in `data/private/`; this directory, `.env`, and database files are Git ignored. The repository examples contain fictional conversations only.

Import preview reads a selected file and reports a hash and mapping issues. Applying an import requires that exact hash, so a changed source cannot be silently applied. Raw speaker names and source locators remain available for review.

Distillation and simulation send selected source excerpts, context, and relevant claims to the configured OpenAI-compatible model endpoint. A local endpoint keeps those requests on the device; a remote endpoint processes them under that provider's terms. Model credentials come from environment variables and are not saved in the database. Imported text is untrusted input: the extraction layer validates its event IDs, speaker IDs, and quoted spans before storing evidence. Simulation output is always labelled as generated.
