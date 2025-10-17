# Multi-Syllable Rhyme & Pattern Search Plan

## Goals

* Enable searching for pronunciations that match a sequence of `N` syllables, optionally spanning multiple words.
* Allow per-syllable constraints on:
  * Initial consonant cluster (onset).
  * Vowel / vowel cluster (nucleus) including stress marking.
  * Terminal consonant cluster (coda).
  * Stressed vs. unstressed syllables.
* Support wildcards so that any of the above constraints can be ignored ("don't care") or partially constrained.
* Keep the existing rhyme and phoneme search features working unchanged.
* Provide a guide and reference material for end users documenting the new feature and the phoneme inventory.

## Guiding Constraints & Questions

* **How do we represent syllables?** We currently store pronunciations as ARPABET phoneme sequences. We need a layer that segments a pronunciation into syllables with onset / nucleus / coda components and stress metadata.
* **Where does syllable segmentation come from?** CMUdict includes stress digits on vowels but not explicit syllable boundaries. We'll need to infer boundaries algorithmically. We should confirm whether the database already stores syllable counts per pronunciation and whether any syllabified representation exists.
* **How expressive should the pattern syntax be?** The DSL must let users describe combinations like `* AH1 T` meaning "any onset, vowel AH with primary stress, coda T", or `BR-OW0-*` for onset `BR`, vowel `OW` (unstressed), any coda. We should settle on something that is readable, composable, and relatively straightforward to parse.
* **How to integrate with the existing search pipeline?** Search currently iterates pronunciations row-by-row and optionally matches patterns using wildcard matching on strings. We'll likely extend this with an additional `pattern_type` (e.g., `"syllable"` or `"syllable_sequence"`) and new helper functions to parse patterns and test matches at the syllable level.
* **Performance considerations.** Adding syllable segmentation and pattern matching should avoid recomputing heavy work repeatedly. Potential caching strategies include storing syllable breakdowns alongside each pronunciation or memoizing segmentation results within the search process.
* **Scope boundaries.** We'll focus on offline segmentation of individual pronunciations in Python. Multi-word support can be accomplished by concatenating word pronunciations and then segmenting into syllables.

## Data & Representation Design

### Syllable Model

Represent each syllable as a small dataclass or tuple with:

* `onset`: tuple of consonant phonemes preceding the vowel.
* `nucleus`: vowel phoneme including stress digit (e.g., `"AE1"`). The base vowel (without stress) can be derived as needed.
* `coda`: tuple of consonant phonemes following the vowel up to the next syllable boundary.
* `stress`: derived from the nucleus (0/1/2).

Segmenting a pronunciation of tokens `[phoneme1, phoneme2, ...]` proceeds by scanning for vowels (per `phonetics.is_vowel`). For each vowel, gather preceding consonants since the last vowel as `onset`, assign the vowel to `nucleus`, and gather following consonants until the next vowel or end of pronunciation as `coda`, with the proviso that certain consonant clusters belong to the next syllable onset. We'll need heuristics to split coda vs. onset in clusters.

### Onset/Coda Heuristics

We can implement a simplified syllabification algorithm:

1. Identify indices of vowel phonemes.
2. For each vowel except the first, there may be consonant(s) between the previous vowel and the current vowel. Use a consonant cluster splitting rule, e.g., **Maximal Onset Principle** guided by a list of permissible onset clusters.
3. Maintain canonical lists of allowable onsets (single consonants and clusters). The remainder of the cluster attaches to the previous syllable's coda.
4. The final syllable's trailing consonants become the coda.

We should create reference data sets for allowed onsets and codas based on English phonotactics, perhaps approximated by the set of onsets observed in the CMU dictionary. For planning we can note that we'll generate these lists programmatically during ingestion or by scanning the dataset.

### Multi-Word Handling

When searching across multiple words, we can chain their pronunciations to form a single phoneme sequence, then syllabify that combined sequence. The query pattern of `N` syllables would then be matched against sliding windows within this combined syllable list.

We'll consider two usage modes:

* **Single word search**: default; the database iterates pronunciations for individual words.
* **Multi-word search**: we join pronunciations from consecutive words (perhaps limited to dictionary entries for phrases) or allow user-provided sequences to be checked for matches. For database-backed search, we can keep iterating word pronunciations but allow pattern lengths greater than the word's syllable count—if the pattern is longer, the word is skipped.

### Pattern DSL Concepts

We propose a per-syllable pattern grammar, e.g. `ONSET-VOWEL[STRESS][/CODA]`:

```
SyllablePattern := [Onset] '-' Vowel [StressSpec] ['/' Coda]
```

* `Onset`, `Vowel`, `Coda` each accept wildcard characters `*` (any) and `?` (single phoneme) using shell-style semantics.
* `Onset` and `Coda` components list consonant phonemes separated by spaces (e.g., `K R`), optionally compressed using `.` or `+` to indicate grouping if desirable. We may allow parentheses or just rely on spaces.
* `Vowel` must contain one vowel phoneme, with stress handled by an optional trailing block such as `[1]`, `[0|2]`, or `{P}` so vowel tokens remain stress-agnostic.
* `StressSpec` accepts values like `"*"` (don't care), `"S"` (primary stress), `"s"` (secondary), `"U"` (unstressed), or simply digits `0/1/2`.

A multi-syllable pattern is a whitespace-separated list of syllable patterns. Example: `*-AH[1]/T *-IY[0]` meaning: first syllable any onset, vowel `AH`, primary stress, coda `T`; second syllable any onset, vowel `IY`, unstressed, no coda constraint.

We'll need to define how to express "no onset" or "no coda". Proposed tokens:

* `Ø` or `.` to represent an empty onset/coda explicitly.
* Alternatively, treat empty string as valid (two dashes in a row). Example: `-AE[1]/T` to say no onset.

For planning we can adopt the latter: `-` followed immediately by the vowel pattern indicates empty onset; `*/-` etc. We'll detail this in documentation.

### Internal Representation of Patterns

We'll parse the user-provided pattern string into a sequence of `SyllablePattern` dataclasses with fields:

* `onset_pattern: WildcardPattern`
* `vowel_pattern: WildcardPattern`
* `coda_pattern: WildcardPattern`
* `stress_constraint: Optional[Set[str]]`

`WildcardPattern` wraps a normalized string pattern plus helper methods for matching tuples of phonemes. We'll treat phoneme clusters as space-joined strings before matching with `fnmatch`. Alternatively, we can compile them into regex objects for flexibility.

Parsing steps:

1. Tokenize by whitespace to get syllable specs.
2. For each token, parse subdivisions by `-` and `/` plus an optional trailing stress block (`[...]` or `{...}`).
3. Validate that vowels are present and that wildcard digits/stress align with known phoneme sets.
4. Provide helpful errors for invalid tokens.

### Matching Algorithm

Given a list of syllables for a pronunciation and a pattern sequence:

1. Slide a window of length `len(pattern)` across the syllable list. For each window:
   * Compare each syllable's onset, vowel, coda, and stress with the corresponding pattern using wildcard matching.
   * If all syllables in the window match, record the match (the entire word or the matched syllable span).
2. If multiple windows match within a word, we can either accept the first or return duplicates. We'll likely capture the full word once with metadata about the matching syllable range.

For words with fewer syllables than the pattern length, skip them.

### Database / Storage Considerations

The existing database stores columns `rhyme_key_n`, `terminal_vowels`, `terminal_consonants`, etc. To support the new feature efficiently we might:

* Add a table or JSON blob storing per-pronunciation syllable breakdowns (onset/nucleus/coda/stress). This could be computed during ingestion and cached, avoiding repeated syllabification at query time.
* Alternatively, perform syllabification on the fly. Initially, to minimize schema changes, we can compute segmentation in Python with memoization per pronunciation string.

For this iteration, we can implement in-memory memoization (e.g., `functools.lru_cache`) on a function that converts a pronunciation string into syllables. If we later need persistence, we can extend the ingest process.

### API & CLI Changes

We'll extend `SearchOptions` with new fields:

* `syllable_pattern: Optional[str]` or reuse `pattern` with `pattern_type="syllable"`.
* `syllable_mode: Literal["exact", "contains"]` to control sliding-window vs. full-match semantics.
* Option to ignore stress globally (toggle).

CLI updates should introduce commands/subcommands to specify the new pattern type, possibly using flags like `--syllable-pattern` or `--pattern-type syllable`.

### Testing Strategy

* Unit tests for syllabification: confirm onset/nucleus/coda extraction on sample words (e.g., `"CAT"`, `"STRING"`, `"PHOTOGRAPH"`). Compare against expected stress patterns.
* Pattern parser tests: ensure valid tokens parse correctly and invalid ones raise descriptive errors.
* Matching tests: given a known pronunciation, check whether specific patterns match or fail as expected.
* Integration tests: run search queries over a small fixture database to confirm results include words that match the pattern.

### Documentation Outputs

* **Usage Guide (`docs/syllable_pattern_guide.md`)**: instructions, CLI examples, explanation of pattern syntax and wildcard usage.
* **Phoneme Reference (`docs/phoneme_reference.txt`)**: list vowels and consonants with their ASCII ARPABET codes, grouped by type, and notes about stress digits.

### Open Questions / TBD

* Should we support optional syllables (e.g., pattern that allows either 2 or 3 syllables)? Initially, no—users supply explicit sequences. We can later add quantifiers.
* How to expose multi-word results? Perhaps show the word along with syllable indices that matched. We'll need to determine output format.
* Are we enabling near matches (edit distance) at the syllable level? For now, we keep near-matching semantics on the underlying phoneme text but focus on exact/wildcard matches in the syllable DSL.

### Implementation Phases

1. **Prototype syllable segmentation** function returning structured syllables, with caching.
2. **Pattern parser** converting user strings into `SyllablePattern` objects.
3. **Matcher** that tests segmentation windows against the parsed pattern.
4. **Search integration** via new `pattern_type` branch using the matcher.
5. **CLI extension** to let users specify the new mode.
6. **Documentation** as described above.
7. **Testing** across all new components.

