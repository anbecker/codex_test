# Task List

This backlog captures upcoming enhancements requested for the poetry assistant. Each task should receive a design spike and implementation plan before coding begins.

## Data Enrichment

- [ ] **Attach relative word frequencies to the lexicon.** Source corpus-based frequency counts (e.g., SUBTLEX, Google N-grams) during database ingestion, normalize them, and store alongside each pronunciation to let search rank common words more highly than rare ones.
- [ ] **Record part-of-speech metadata.** Incorporate POS tags for each word/pronunciation variant so queries can filter by grammatical role. Decide how to handle words with multiple parts of speech and whether to expose priorities.
- [ ] **Build synonym families.** Integrate a thesaurus dataset to cluster words into synonym sets. Provide identifiers so the search engine can expand queries or group results by semantic family.

## Search Engine Enhancements

- [ ] **Expose part-of-speech filters in search options.** Extend the API and CLI so users can restrict results to specific POS categories, using the metadata added above.
- [ ] **Support configurable multi-word/phrase composition.** Allow patterns to match sequences that span multiple dictionary entries while giving users strict controls (e.g., maximum span length, explicit enable flags) to avoid combinatorial explosions.
- [ ] **Introduce syllable-level fuzzy matching.** Implement an edit-distance style metric that scores onset, vowel, and coda differences equally at one-third apiece. Provide thresholds or top-N selection so users can request near matches instead of exact token matches.

## Performance & Scalability

- [ ] **Optimize large-scale searches.** Profile the new syllable-matching and combination logic on the full lexicon, add indexes or caching as needed, and ensure latency remains acceptable even when many pronunciations satisfy a loose pattern.
- [ ] **Provide configuration for resource-heavy features.** Offer toggles for expensive operations (e.g., enabling fuzzy search or multi-word composition) and sensible defaults that keep the search responsive in production settings.

## Documentation & UX

- [ ] **Update guides once features land.** Expand the syllable pattern guide and CLI docs to describe frequency-aware ranking, POS filtering, synonym usage, and fuzzy match semantics with real-word examples.
- [ ] **Document data sources and refresh cadence.** Record where frequency, POS, and thesaurus data originate, plus how often they should be refreshed to keep the database current.
