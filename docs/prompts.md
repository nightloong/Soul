# Prompts

Versioned prompts live under `prompts/`. Extraction (`extraction/v1.md`) asks the provider for structured evidence, claims, and memories; runtime (`runtime/v1.md`) generates a simulated reply using retrieved context. Imported conversation text is data, never an instruction source. Extraction references must resolve to stored events, the mapped person, and a matching excerpt before they become evidence.

The merge policy in `merge/v1.md` describes deterministic claim normalization, confidence adjustment, counterevidence, and supersession. Distillation stores prompt and input hashes so repeated runs with the same material can be reused. The runtime trace records the selected evidence and generated turn for later explanation.
