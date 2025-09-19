# Poetry Assistant

A command line assistant for lyricists, poets, and rappers. The application builds a local SQLite database of words enriched with pronunciations, syllable stresses, parts of speech, definitions, and synonyms. Users can search the lexicon using phonetic patterns, stressed syllable masks, lexical filters, and similarity scores, and can request rhyme suggestions for arbitrary lines.

## Features

* **Comprehensive phonetic database** – ingest the [CMU Pronouncing Dictionary](https://github.com/cmusphinx/cmudict) for pronunciations and syllable stress patterns, and enrich entries with definitions, parts of speech, and synonym sets from [WordNet](https://wordnet.princeton.edu/).
* **Phoneme-aware search** – query by terminal vowel sounds, consonant clusters, combined rhyme keys, full pronunciations, or stress patterns using wildcard or regular-expression style syntax.
* **Near-rhyme support** – compute phoneme edit distance and similarity scores so that off-rhymes and slant rhymes are surfaced alongside perfect rhymes.
* **Lexical filters** – limit results to words with specific parts of speech, textual definitions, or synonyms.
* **Rhyming line assistant** – analyse the last syllables of an input line and propose candidate rhyme words for one to four ending syllables.
* **Extensible data model** – each word can store multiple pronunciations, definitions, and synonym lists.

## Installation

The project is packaged as a standard Python module. Install dependencies and the CLI entry point with `pip`:

```bash
pip install -e ".[cli]"
```

The optional `tabulate` dependency provides pretty tabular output; without it, search results are emitted as JSON.

## Building the database

Create or refresh the SQLite database by downloading the source corpora:

```bash
poetry-assistant ingest --database data/poetry.db
```

The CLI defaults to storing data in `poetry_assistant.db` in the current directory. If you choose a different location, such as `data/poetry.db` above, pass the same `--database` flag to subsequent commands. The ingestion command downloads the CMU Pronouncing Dictionary (~3 MB) and the WordNet lexicon (~30 MB via NLTK) and stores structured records in the requested database file. Use `--cmu` to point at a local CMU file, or `--no-wordnet` to skip definition enrichment.

## Searching the lexicon

```bash
poetry-assistant search "AE1 T" --type rhyme --syllables 1 --limit 10 --database data/poetry.db
```

Key options:

* `pattern` – phoneme pattern expressed in ARPABET. Use `*` and `?` wildcards or `--regex` for full regular expressions.
* `--type` – choose `rhyme`, `vowel`, `consonant`, `both`, or `phonemes` depending on the feature you want to match.
* `--syllables` – how many ending syllables to consider when `--type rhyme`.
* `--max-distance` / `--min-similarity` – enable near-match scoring by phoneme edit distance.
* `--stress` – wildcard mask over stress digits (e.g. `1*0` to require stressed then unstressed syllables).
* `--pos`, `--definition`, `--synonym` – filter by lexical metadata from WordNet.

Results include each word’s pronunciation, stress signature, similarity score (if applicable), and the first matching definition.

## Rhyming with entire lines

```bash
poetry-assistant rhymes-with "I wrote a clever rap" --max-syllables 3 --database data/poetry.db
```

The assistant tokenises the final words of the line, retrieves pronunciations, and returns rhyme suggestions for the last one through N syllables. Near-rhyme parameters (`--max-distance`, `--min-similarity`, `--pos`) mirror the search command.

## Inspecting individual entries

```bash
poetry-assistant word serendipity --database data/poetry.db
```

Displays all pronunciations along with syllable counts, stress patterns, and the associated definitions and synonyms.

## Frequently asked questions

**Does a database already exist for pronunciations and stresses?**  
Yes. The CMU Pronouncing Dictionary is an openly licensed corpus that enumerates pronunciations, ARPABET phonemes, and stress digits for more than 134,000 entries. WordNet supplies parts of speech, definitions, and synonym sets. The ingestion command stitches these corpora into a single SQLite database tailored for phonetic exploration.

## Development

Run the automated tests with `pytest`:

```bash
pytest
```

The repository includes fixtures that exercise rhyme searching, similarity scoring, and the line-based rhyme assistant without requiring external downloads.
