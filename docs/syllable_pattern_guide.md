# Syllable Pattern Search Guide

This guide explains how to describe multi-syllable rhyme patterns and search for
matching pronunciations using the poetry assistant tools. The new syllable DSL
lets you specify onsets, vowels, codas, and stress for each syllable, with
optional wildcards whenever you do not care about a component.

## Overview

* **Onset** – optional consonant or consonant cluster before the vowel.
* **Vowel** – one vowel phoneme (ARPABET) including an optional stress digit.
* **Coda** – optional consonant or consonant cluster after the vowel.
* **Stress** – optional constraint on the stress of the vowel (primary, secondary,
  unstressed).

A syllable pattern is written as:

```
Onset - Vowel[Stress] [/ Coda]
```

Whitespace separates syllables in the full pattern. Use parentheses or square
brackets when an onset or coda contains spaces (multi-phoneme clusters).

Examples:

* `*-AE[1]/T` – any onset, vowel `AE`, primary stress, and a `T` coda.
* `-IY[0]` – no onset, vowel `IY`, unstressed, empty coda (slash omitted).
* `[S P]-AY[1]` – onset `S P`, vowel `AY`, primary stress, empty coda.

Combine syllables by placing them next to each other:

```
[S P]-AY[1] D-ER[0]
```

This pattern matches the pronunciation of “spider”.

## Wildcards & Empty Components

* `*` and `?` follow shell-style wildcard semantics inside onset, vowel, or coda
  components. For example, `*-OW[12]?/T` matches any onset, any vowel beginning
  with `OW` and ending in stress `1` or `2`, and a `T` coda.
* Leave the onset or coda blank to require it to be empty: `-AE[1]` or
  `*-IY[0]/` (the slash is optional when you do not care about the coda).
* You can still spell out explicit empty markers (`Ø`, `NONE`, `0`) if you
  prefer, but they are no longer required.
* Separate multiple phonemes inside onsets or codas with spaces by wrapping the
  sequence in `[]` or `()`, or use `_`, `.` or `+` as separators. For example,
  `[K R]-OW[1]` and `K_R-OW[1]` both specify an onset of `K R`.

### Vowel alternatives

* Provide multiple vowel options by separating them with `|`, commas, or
  whitespace inside brackets/parentheses. Each option may include wildcards.
* When you omit a stress digit (e.g., `ER` instead of `ER0`), the pattern will
  match any vowel sharing that base phoneme. Combine with stress braces to limit
  the allowed stress levels.

Examples:

* `*-[ER|AH][0]/*` – matches an unstressed syllable with vowel `ER` or `AH`.
* `*-EH[1]/* *-[AH|ER][0]/* *-AE[1]/P` – matches three-syllable phrases such as
  **clever rap** (`K_L-EH[1]/V R-ER[0]/Ø R-AE[1]/P`) and **mend the gap**
  (`M-EH[1]/ND DH-AH[0]/Ø G-AE[1]/P`).
* `([B|K] R)-[AA|AE][0|1]/[P|T]` – accepts clusters like **brat**, **crap**,
  **crop**, or the surname **Kratt** by allowing either `B R` or `K R` onsets,
  vowels `AA` or `AE`, stress `0` or `1`, and codas `P` or `T`.

## Token-aware onset and coda constraints

Onset and coda patterns operate on whole phoneme tokens, so wildcards respect
multi-letter symbols such as `TH`, `CH`, and `SH`.

* `([BD] R)-AW[1]/N` – matches **brown** and **drown** (onsets `B R` / `D R`) but
  not **gown** (onset `G`).
* `*-AW[1]/N` – the onset wildcard accepts **brown**, **drown**, and **gown** so
  long as the vowel and coda match.
* `?-AW[1]/N` – requires exactly one onset phoneme, matching **gown** while
  excluding **brown** and **drown** with their two-phoneme clusters.
* `(* R)-OW[1]/N` – demands that the final onset consonant be `R`, matching
  **thrown** (onset `TH R`) while ignoring how many consonants precede it.
* `?-AA[1]/(R M)` – accepts any single phoneme onset before the vowel `AA`, so
  **charm** (onset `CH`) and **farm** (onset `F`) both qualify.

## Stress Constraints

Stress digits follow CMU dictionary conventions:

* `1` – primary stress.
* `2` – secondary stress.
* `0` – unstressed.

Add a trailing stress block with brackets (e.g., `[1]`, `[0|2]`) or braces if
you prefer (`{1}`, `{0|2}`). The block accepts digits directly as well as the
shorthand `P` (primary), `S` (secondary), and `U` (unstressed). If you do not
care about stress, omit the block entirely or pass `--ignore-syllable-stress`
when searching.

## CLI Usage

Run the search command with `--type syllable` to activate syllable matching. The
`--contains` flag allows the pattern to match any consecutive syllables within a
pronunciation. Combine with `--ignore-syllable-stress` to ignore stress markers.

```bash
poetry-assistant search "[S P]-AY[1] D-ER[0]" --type syllable
poetry-assistant search "*-AW[1]/*" --type syllable --contains
poetry-assistant search "D-ER*[1]" --type syllable --contains --ignore-syllable-stress
poetry-assistant search "*-EH[12]/* *-(AH|ER)[0]/* *-IY[012]/*" --type syllable
```

The tabulated output shows the syllable range that satisfied the pattern in the
`Match` column. Ranges are 1-indexed and inclusive on the right. For example,
`1-2` means the first two syllables matched.

The final example demonstrates three syllables with wildcard onsets, vowel
choices, and explicit stress blocks. It matches words such as "heavenly" (`HH
EH1 V AH0 N L IY0`), "memory" (`M EH1 M ER0 IY0`), and "seventeen" (`S EH1 V
AH0 N T IY1 N`).

## Programmatic Usage

Use the helper utilities directly from Python:

```python
from poetry_assistant import parse_syllable_pattern, SearchEngine, SearchOptions

pattern = parse_syllable_pattern("[S P]-AY[1] D-ER[0]")
options = SearchOptions(pattern_type="syllable", pattern="[S P]-AY[1] D-ER[0]")
engine = SearchEngine(database)
results = engine.search(options)
for match in results:
    print(match.word, match.matched_syllables)
```

`parse_syllable_pattern` returns structured pattern objects and `syllabify`
converts pronunciations into syllables:

```python
from poetry_assistant import syllabify
from poetry_assistant.phonetics import strip_stress

syllables = syllabify("S P AY1 D ER0")
for syllable in syllables:
    onset = syllable.onset_text or "-"
    coda = syllable.coda_text
    print(f"{onset}-{strip_stress(syllable.vowel)}[{syllable.stress}]/{coda}")
```

## Tips

* Patterns can span any number of syllables. Combine with `--contains` to search
  for sub-phrases anywhere in a word or multi-word entry.
* Leave the pattern empty (omit the argument) to list pronunciations while still
  benefiting from the `Match` column for reference.
* When a pattern feels overly restrictive, replace components with `*` to widen
  the search incrementally.
* The syllable segmentation uses a maximal onset heuristic guided by common
  English consonant clusters. Consult the phoneme reference for available onset
  symbols.
