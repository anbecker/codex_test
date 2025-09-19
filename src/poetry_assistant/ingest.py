"""Data ingestion routines for the poetry assistant."""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import nltk
from nltk.corpus import wordnet as wn
from tqdm import tqdm

from .database import PoetryDatabase

LOGGER = logging.getLogger(__name__)

CMU_URL = "https://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b"

POS_MAP = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb",
}


def ensure_nltk_data() -> None:
    """Ensure the WordNet corpus is available."""

    try:
        wn.ensure_loaded()
    except LookupError:
        LOGGER.info("Downloading WordNet corpus via NLTK…")
        nltk.download("wordnet")
        wn.ensure_loaded()


def download_cmudict(destination: Path | None = None) -> Path:
    """Download the CMU pronouncing dictionary to the destination path."""

    import urllib.request

    if destination is None:
        destination = Path(tempfile.gettempdir()) / "cmudict-0.7b"
    LOGGER.info("Downloading CMU Pronouncing Dictionary…")
    urllib.request.urlretrieve(CMU_URL, destination)
    return destination


def parse_cmudict(path: Path) -> Iterator[Tuple[str, List[str]]]:
    """Yield ``(word, phonemes)`` from a CMU dictionary file."""

    pattern = re.compile(r"^(?P<word>[A-Z'\-.]+)(?:\((?P<variant>\d+)\))?\s+(?P<phones>.+)")
    with path.open("r", encoding="utf8") as handle:
        for line in handle:
            if not line or line.startswith(";;;"):
                continue
            match = pattern.match(line.strip())
            if not match:
                continue
            word = match.group("word").lower()
            phones = match.group("phones").split()
            yield word, phones


def ingest_cmudict(db: PoetryDatabase, cmu_path: Path) -> Dict[str, int]:
    """Ingest pronunciations into the database."""

    word_ids: Dict[str, int] = {}
    for word, phones in tqdm(parse_cmudict(cmu_path), desc="CMU"):
        word_id = word_ids.get(word)
        if word_id is None:
            word_id = db.add_word(word)
            word_ids[word] = word_id
        db.add_pronunciation(word_id, phones)
    return word_ids


def ingest_wordnet(db: PoetryDatabase, word_ids: Dict[str, int]) -> None:
    """Populate definitions and synonyms using WordNet."""

    ensure_nltk_data()
    for word, word_id in tqdm(word_ids.items(), desc="WordNet"):
        synsets = wn.synsets(word)
        for synset in synsets:
            pos = POS_MAP.get(synset.pos())
            definition = synset.definition()
            examples = synset.examples()
            example = examples[0] if examples else None
            synonyms = {
                lemma.name().replace("_", " ").lower()
                for lemma in synset.lemmas()
                if lemma.name().lower() != word
            }
            db.add_definition(
                word_id,
                pos,
                definition,
                example,
                source="wordnet",
                synonyms=sorted(synonyms),
            )


def build_database(
    database_path: Path | str,
    cmu_source: Optional[Path | str] = None,
    download_if_missing: bool = True,
    include_wordnet: bool = True,
) -> Path:
    """Build or update the assistant database."""

    db_path = Path(database_path)
    db = PoetryDatabase(db_path)
    db.initialize()

    if cmu_source is None:
        if not download_if_missing:
            raise ValueError("CMU source not provided and download disabled.")
        cmu_source = download_cmudict()
    cmu_path = Path(cmu_source)
    if not cmu_path.exists():
        if download_if_missing:
            cmu_path = download_cmudict(Path(cmu_source))
        else:
            raise FileNotFoundError(cmu_source)

    LOGGER.info("Ingesting pronunciations from %s", cmu_path)
    word_ids = ingest_cmudict(db, cmu_path)
    LOGGER.info("Loaded %s unique words", len(word_ids))

    if include_wordnet:
        LOGGER.info("Enriching with WordNet definitions")
        ingest_wordnet(db, word_ids)

    db.close()
    return db_path

