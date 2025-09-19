"""Command line interface for the poetry assistant."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .database import PoetryDatabase
from .ingest import build_database
from .models import SearchResult
from .rhymes import RhymeAssistant
from .search import SearchEngine, SearchOptions

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - optional dependency
    tabulate = None

LOGGER = logging.getLogger("poetry_assistant")


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Phonetic rhyme assistant")
    parser.add_argument("--database", default="poetry_assistant.db", help="SQLite database path")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Download and ingest data sources")
    ingest_parser.add_argument("--cmu", help="Path to CMU pronouncing dictionary file")
    ingest_parser.add_argument("--no-wordnet", action="store_true", help="Skip WordNet enrichment")

    search_parser = subparsers.add_parser("search", help="Search for rhymes and phonetic patterns")
    search_parser.add_argument("pattern", nargs="?", help="Phoneme pattern to match")
    search_parser.add_argument("--type", choices=["rhyme", "vowel", "consonant", "both", "phonemes"], default="rhyme")
    search_parser.add_argument("--syllables", type=int, default=1, help="Number of syllables to consider for rhyme matching")
    search_parser.add_argument("--regex", action="store_true", help="Treat pattern as regular expression")
    search_parser.add_argument("--contains", action="store_true", help="Allow substring matches instead of whole string matches")
    search_parser.add_argument("--max-distance", type=int, help="Maximum edit distance for near matches")
    search_parser.add_argument("--min-similarity", type=float, help="Minimum similarity score for matches (0-1)")
    search_parser.add_argument("--stress", help="Stress pattern wildcard (use * and ?)")
    search_parser.add_argument("--pos", help="Part of speech filter (noun, verb, adjective, adverb)")
    search_parser.add_argument("--definition", help="Search for words whose definition contains this text")
    search_parser.add_argument("--synonym", help="Search using synonym text")
    search_parser.add_argument("--limit", type=int, default=25, help="Maximum number of results")

    word_parser = subparsers.add_parser("word", help="Show pronunciations and definitions for a word")
    word_parser.add_argument("word", help="Word to inspect")

    rhyme_parser = subparsers.add_parser("rhymes-with", help="Suggest words that rhyme with the end of a line")
    rhyme_parser.add_argument("line", help="Input line to analyse")
    rhyme_parser.add_argument("--max-syllables", type=int, default=3, help="Maximum syllables to match")
    rhyme_parser.add_argument("--max-distance", type=int, help="Maximum edit distance for near rhymes")
    rhyme_parser.add_argument("--min-similarity", type=float, help="Minimum similarity score for near rhymes")
    rhyme_parser.add_argument("--pos", help="Part of speech filter for rhymes")
    rhyme_parser.add_argument("--limit", type=int, default=15, help="Maximum suggestions per syllable count")

    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    db_path = Path(args.database)

    if args.command == "ingest":
        build_database(
            database_path=db_path,
            cmu_source=args.cmu,
            download_if_missing=True,
            include_wordnet=not args.no_wordnet,
        )
        LOGGER.info("Database created at %s", db_path)
        return

    if not db_path.exists():
        parser.error(f"Database {db_path} does not exist. Run 'poetry-assistant ingest' first.")

    db = PoetryDatabase(db_path)
    db.initialize()

    if args.command == "search":
        options = SearchOptions(
            pattern=args.pattern,
            pattern_type=args.type,
            syllables=args.syllables,
            regex=args.regex,
            contains=args.contains,
            max_distance=args.max_distance,
            min_similarity=args.min_similarity,
            stress_pattern=args.stress,
            part_of_speech=args.pos,
            definition_query=args.definition,
            synonym_query=args.synonym,
            limit=args.limit,
        )
        engine = SearchEngine(db)
        results = engine.search(options)
        _print_results(results)
    elif args.command == "word":
        assistant = RhymeAssistant(db)
        pronunciations = assistant.pronunciations_for_word(args.word)
        if not pronunciations:
            print(f"No pronunciations found for {args.word}")
        else:
            print(f"Pronunciations for {args.word}:")
            for pron in pronunciations:
                print(f"  - {pron.text} (syllables={pron.syllable_count}, stress={pron.stress_pattern})")
            # attach definitions
            word_rows = db.pronunciations_for_word(args.word)
            if word_rows:
                word_id = word_rows[0]["word_id"]
                definitions = db.load_definitions([word_id]).get(word_id, [])
                if definitions:
                    print("Definitions:")
                    for definition in definitions:
                        synonyms = ", ".join(definition.synonyms)
                        base = f"  - ({definition.part_of_speech}) {definition.definition}"
                        if synonyms:
                            base += f" | synonyms: {synonyms}"
                        if definition.example:
                            base += f" | example: {definition.example}"
                        print(base)
    elif args.command == "rhymes-with":
        assistant = RhymeAssistant(db)
        results = assistant.suggest_rhymes(
            line=args.line,
            max_syllables=args.max_syllables,
            max_results=args.limit,
            max_distance=args.max_distance,
            min_similarity=args.min_similarity,
            part_of_speech=args.pos,
        )
        for syllables, suggestions in results.items():
            print(f"Last {syllables} syllable(s):")
            for suggestion in suggestions:
                print(f"  {suggestion}")
            if not suggestions:
                print("  (no matches)")
    db.close()


def _print_results(results: list[SearchResult]) -> None:
    if not results:
        print("No matches found")
        return
    rows = []
    for result in results:
        definition = result.definitions[0].definition if result.definitions else ""
        rows.append(
            [
                result.word,
                result.pronunciation,
                result.stress_pattern,
                result.similarity if result.similarity is not None else "",
                definition,
            ]
        )
    headers = ["Word", "Pronunciation", "Stress", "Similarity", "Definition"]
    if tabulate:
        print(tabulate(rows, headers=headers))
    else:
        print(json.dumps(dict(headers=headers, rows=rows), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()

