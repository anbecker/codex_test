"""Syllable segmentation and pattern matching utilities."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from .phonetics import is_vowel, strip_stress, tokens

# ---------------------------------------------------------------------------
# Syllable representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Syllable:
    """Structured view of a syllable within a pronunciation."""

    onset: Tuple[str, ...]
    nucleus: str
    coda: Tuple[str, ...]
    stress: str

    @property
    def onset_text(self) -> str:
        return " ".join(self.onset)

    @property
    def coda_text(self) -> str:
        return " ".join(self.coda)

    @property
    def vowel(self) -> str:
        return self.nucleus

    @property
    def vowel_base(self) -> str:
        return strip_stress(self.nucleus)


# ---------------------------------------------------------------------------
# Syllable segmentation
# ---------------------------------------------------------------------------

_SINGLE_ONSETS = {
    "B",
    "CH",
    "D",
    "DH",
    "F",
    "G",
    "HH",
    "JH",
    "K",
    "L",
    "M",
    "N",
    "P",
    "R",
    "S",
    "SH",
    "T",
    "TH",
    "V",
    "W",
    "Y",
    "Z",
    "ZH",
    "NG",
}

_CLUSTER_ONSETS = {
    ("B", "L"),
    ("B", "R"),
    ("B", "W"),
    ("CH", "R"),
    ("D", "R"),
    ("D", "W"),
    ("F", "L"),
    ("F", "R"),
    ("G", "L"),
    ("G", "R"),
    ("G", "W"),
    ("HH", "Y"),
    ("K", "L"),
    ("K", "R"),
    ("K", "W"),
    ("P", "L"),
    ("P", "R"),
    ("P", "W"),
    ("S", "K"),
    ("S", "L"),
    ("S", "M"),
    ("S", "N"),
    ("S", "P"),
    ("S", "T"),
    ("S", "W"),
    ("SH", "R"),
    ("T", "R"),
    ("T", "W"),
    ("TH", "R"),
    ("TH", "W"),
    ("V", "L"),
    ("V", "R"),
    ("Z", "L"),
    ("Z", "R"),
    ("ZH", "R"),
    ("S", "P", "L"),
    ("S", "P", "R"),
    ("S", "T", "L"),
    ("S", "T", "R"),
    ("S", "K", "L"),
    ("S", "K", "R"),
    ("S", "K", "W"),
}

_ALLOWED_ONSETS: set[Tuple[str, ...]] = {(c,) for c in _SINGLE_ONSETS}
_ALLOWED_ONSETS.update(_CLUSTER_ONSETS)


def syllabify(pronunciation: Sequence[str] | str) -> List[Syllable]:
    """Split a pronunciation into syllables."""

    if isinstance(pronunciation, str):
        phonemes = tuple(tokens(pronunciation))
    else:
        phonemes = tuple(pronunciation)
    return list(_syllabify_cached(phonemes))


@lru_cache(maxsize=8192)
def _syllabify_cached(phonemes: Tuple[str, ...]) -> Tuple[Syllable, ...]:
    syllables: List[Syllable] = []
    current_onset: List[str] = []
    i = 0
    length = len(phonemes)
    while i < length:
        phoneme = phonemes[i]
        if is_vowel(phoneme):
            nucleus = phoneme
            stress = phoneme[-1] if phoneme[-1].isdigit() else "0"
            # gather consonants until next vowel
            j = i + 1
            buffer: List[str] = []
            while j < length and not is_vowel(phonemes[j]):
                buffer.append(phonemes[j])
                j += 1
            next_vowel_exists = j < length
            coda, next_onset = _split_cluster(buffer, next_vowel_exists)
            syllables.append(
                Syllable(onset=tuple(current_onset), nucleus=nucleus, coda=tuple(coda), stress=stress)
            )
            current_onset = next_onset
            i = j
        else:
            current_onset.append(phoneme)
            i += 1
    # Any trailing onset consonants become part of the last coda
    if current_onset and syllables:
        last = syllables[-1]
        merged_coda = last.coda + tuple(current_onset)
        syllables[-1] = Syllable(onset=last.onset, nucleus=last.nucleus, coda=merged_coda, stress=last.stress)
    return tuple(syllables)


def _split_cluster(cluster: List[str], allow_onset: bool) -> Tuple[List[str], List[str]]:
    if not cluster:
        return [], []
    if not allow_onset:
        return list(cluster), []
    for index in range(len(cluster)):
        suffix = tuple(cluster[index:])
        if suffix in _ALLOWED_ONSETS:
            return cluster[:index], list(suffix)
    # default: keep final consonant as onset of next syllable
    return cluster[:-1], [cluster[-1]]


# ---------------------------------------------------------------------------
# Pattern parsing and matching
# ---------------------------------------------------------------------------

_EMPTY_MARKERS = {"", "Ø", "ø", "0", "NONE", "none", "NULL", "null"}


@dataclass(frozen=True)
class _TokenPattern:
    kind: str
    values: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentPattern:
    tokens: Optional[Tuple[_TokenPattern, ...]] = None
    require_empty: bool = False

    def matches(self, cluster: Sequence[str]) -> bool:
        if self.require_empty:
            return len(cluster) == 0
        if self.tokens is None:
            return True
        return _match_token_pattern(self.tokens, tuple(cluster))


@dataclass(frozen=True)
class VowelPattern:
    options: Tuple[str, ...]

    def matches(self, vowel: str) -> bool:
        return any(fnmatch.fnmatchcase(vowel, option) for option in self.options)


@dataclass(frozen=True)
class SyllablePattern:
    onset: ComponentPattern
    vowel: VowelPattern
    coda: ComponentPattern
    stress: Optional[set[str]] = None

    def matches(self, syllable: Syllable, *, ignore_stress: bool = False) -> bool:
        if not self.onset.matches(syllable.onset):
            return False
        if not self.vowel.matches(syllable.vowel):
            return False
        if not self.coda.matches(syllable.coda):
            return False
        if ignore_stress or self.stress is None:
            return True
        return syllable.stress in self.stress


@dataclass(frozen=True)
class WildcardSyllable:
    """Wildcard that matches any single syllable."""


@dataclass(frozen=True)
class WildcardSequence:
    """Wildcard that matches zero or more syllables."""


PatternElement = Union[SyllablePattern, WildcardSyllable, WildcardSequence]


def parse_syllable_pattern(pattern: str) -> List[PatternElement]:
    """Parse a multi-syllable pattern string."""

    tokens = _tokenize(pattern)
    syllables: List[PatternElement] = []
    for token in tokens:
        stress_values: Optional[set[str]] = None
        core = token.strip()
        if not core:
            raise ValueError("Empty syllable pattern segment")
        if core == "*":
            syllables.append(WildcardSyllable())
            continue
        if core == "**":
            syllables.append(WildcardSequence())
            continue
        if "-" not in core:
            raise ValueError(f"Invalid syllable pattern '{token}': missing '-' separator")
        onset_text, remainder = core.split("-", 1)
        onset = _parse_component(onset_text, allow_wildcard=True)
        coda = ComponentPattern(tokens=None, require_empty=False)
        vowel_text = remainder
        if "/" in remainder:
            vowel_text, coda_text = remainder.split("/", 1)
            coda = _parse_component(coda_text, allow_wildcard=True)
        vowel_text = vowel_text.strip()
        if not vowel_text:
            raise ValueError(f"Invalid syllable pattern '{token}': missing vowel specification")
        vowel_text, stress_values = _separate_stress_block(vowel_text)
        syllables.append(
            SyllablePattern(
                onset=onset,
                vowel=_parse_vowel_pattern(vowel_text),
                coda=coda,
                stress=stress_values,
            )
        )
    return syllables


def find_syllable_matches(
    syllables: Sequence[Syllable],
    pattern: Sequence[PatternElement],
    *,
    contains: bool = False,
    ignore_stress: bool = False,
) -> List[Tuple[int, int]]:
    """Return the start/end indices of matches for ``pattern`` within ``syllables``."""

    if not pattern:
        return [(0, 0)] if not syllables else [(0, len(syllables))]
    matches: List[Tuple[int, int]] = []

    @lru_cache(maxsize=None)
    def _match(start: int, index: int) -> Tuple[int, ...]:
        if index == len(pattern):
            return (start,)
        token = pattern[index]
        results: List[int] = []
        if isinstance(token, WildcardSequence):
            # Allow the wildcard sequence to consume zero syllables before
            # exploring longer spans. This preserves the intended "zero or
            # more" semantics without requiring callers to add an explicit
            # single-syllable wildcard to cover the empty case.
            results.extend(_match(start, index + 1))
            for next_start in range(start + 1, len(syllables) + 1):
                results.extend(_match(next_start, index + 1))
            return tuple(dict.fromkeys(results))
        if start >= len(syllables):
            return tuple()
        if isinstance(token, WildcardSyllable):
            return _match(start + 1, index + 1)
        if token.matches(syllables[start], ignore_stress=ignore_stress):
            return _match(start + 1, index + 1)
        return tuple()

    candidate_starts: Iterator[int]
    if contains:
        candidate_starts = iter(range(0, len(syllables) + 1))
    else:
        candidate_starts = iter((0,))
    for start in candidate_starts:
        for end in _match(start, 0):
            if not contains and start != 0:
                continue
            if not contains and end != len(syllables):
                continue
            if end < start:
                continue
            if end > len(syllables):
                continue
            matches.append((start, end))
    # Remove duplicates while preserving order
    unique: List[Tuple[int, int]] = []
    seen = set()
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)
    return unique


def matches_syllable_pattern(
    syllables: Sequence[Syllable],
    pattern: Sequence[PatternElement],
    *,
    contains: bool = False,
    ignore_stress: bool = False,
) -> bool:
    """Return ``True`` if ``pattern`` matches ``syllables``."""

    return bool(find_syllable_matches(syllables, pattern, contains=contains, ignore_stress=ignore_stress))


def _tokenize(pattern: str) -> List[str]:
    tokens: List[str] = []
    current: List[str] = []
    depth = 0
    for char in pattern.strip():
        if char in "([":
            depth += 1
        elif char in ")]":
            if depth == 0:
                raise ValueError(f"Unmatched closing bracket in pattern '{pattern}'")
            depth -= 1
        if char.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    if depth != 0:
        raise ValueError(f"Unmatched opening bracket in pattern '{pattern}'")
    return tokens


def _separate_stress_block(text: str) -> Tuple[str, Optional[set[str]]]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Vowel component cannot be empty")

    for closing, opening in (("]", "["), ("}", "{")):
        if stripped.endswith(closing):
            start = _find_matching_open(stripped, opening, closing)
            if start is None:
                raise ValueError(f"Unmatched '{closing}' in vowel component '{text}'")
            inner = stripped[start + 1 : -1].strip()
            prefix = stripped[:start].strip()
            if not prefix:
                # the bracket pair belongs to the vowel options themselves
                continue
            if not inner or inner == "*":
                return prefix, None
            if _looks_like_stress(inner):
                return prefix, _parse_stress_spec(inner)
    return stripped, None


def _find_matching_open(text: str, opening: str, closing: str) -> Optional[int]:
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char == closing:
            depth += 1
        elif char == opening:
            depth -= 1
            if depth == 0:
                return index
    return None


def _looks_like_stress(value: str) -> bool:
    allowed = set("012PpSsUu|, ")
    return all(char in allowed for char in value)


def _parse_stress_spec(spec: str) -> Optional[set[str]]:
    allowed: set[str] = set()
    for symbol in spec.replace(",", "").replace("|", ""):
        if symbol in "012":
            allowed.add(symbol)
        elif symbol in "Pp":
            allowed.add("1")
        elif symbol in "Ss":
            allowed.add("2")
        elif symbol in "Uu":
            allowed.add("0")
        elif symbol.isspace():
            continue
        else:
            raise ValueError(f"Unknown stress marker '{symbol}' in stress specification '{spec}'")
    if not allowed:
        return None
    return allowed


def _parse_component(text: str, allow_wildcard: bool) -> ComponentPattern:
    raw = text.strip()
    if not raw:
        return ComponentPattern(tokens=None, require_empty=True)
    cleaned = _strip_brackets(raw)
    normalized = _normalize_component_text(cleaned)
    if normalized.upper() in _EMPTY_MARKERS:
        return ComponentPattern(tokens=None, require_empty=True)
    if not allow_wildcard and normalized == "*":
        raise ValueError("'*' is not allowed for onset components; use explicit phonemes or omit the onset")
    token_pattern = _compile_component_pattern(normalized)
    return ComponentPattern(tokens=token_pattern)


def _parse_vowel_pattern(text: str) -> VowelPattern:
    raw = text.strip()
    if not raw:
        raise ValueError("Vowel component cannot be empty")
    cleaned = _strip_brackets(raw)
    pieces = _split_vowel_options(cleaned)
    options: List[str] = []
    for piece in pieces:
        normalized = _normalize_vowel_option(piece)
        if normalized not in options:
            options.append(normalized)
    if not options:
        raise ValueError(f"Invalid vowel specification '{text}'")
    return VowelPattern(tuple(options))


def _split_vowel_options(text: str) -> List[str]:
    normalized = (
        text.replace("|", " ")
        .replace(",", " ")
        .replace("_", " ")
        .replace(".", " ")
        .replace("+", " ")
    )
    return [piece for piece in normalized.split() if piece]


def _normalize_vowel_option(option: str) -> str:
    cleaned = option.strip()
    if not cleaned:
        raise ValueError("Empty vowel option is not allowed")
    normalized = cleaned.upper()
    if normalized == "*":
        return normalized
    has_digit = any(char.isdigit() for char in normalized)
    has_wildcard = any(char in {"*", "?"} for char in normalized)
    if not has_digit and not has_wildcard:
        return f"{normalized}?"
    return normalized


def _strip_brackets(text: str) -> str:
    stripped = text.strip()
    if (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("(") and stripped.endswith(")")
    ):
        return stripped[1:-1].strip()
    return stripped


def _normalize_component_text(text: str) -> str:
    cleaned = text.replace("_", " ").replace(".", " ").replace("+", " ")
    parts = cleaned.strip().split()
    return " ".join(parts)


def _compile_component_pattern(text: str) -> Tuple[_TokenPattern, ...]:
    tokens = _split_component_tokens(text)
    if not tokens:
        return tuple()
    compiled: List[_TokenPattern] = []
    for token in tokens:
        if token == "*":
            compiled.append(_TokenPattern("star"))
        elif token == "?":
            compiled.append(_TokenPattern("any"))
        elif token.startswith("[") and token.endswith("]"):
            choices = _parse_choice_block(token)
            compiled.append(_TokenPattern("set", choices))
        else:
            compiled.append(_TokenPattern("literal", (token,)))
    return tuple(compiled)


def _split_component_tokens(text: str) -> List[str]:
    tokens: List[str] = []
    current: List[str] = []
    depth = 0
    for char in text:
        if char == "[":
            depth += 1
            current.append(char)
        elif char == "]":
            if depth == 0:
                raise ValueError(f"Unmatched closing bracket in component '{text}'")
            depth -= 1
            current.append(char)
        elif char.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if depth != 0:
        raise ValueError(f"Unmatched opening bracket in component '{text}'")
    if current:
        tokens.append("".join(current))
    return [token for token in (token.strip() for token in tokens) if token]


def _parse_choice_block(token: str) -> Tuple[str, ...]:
    inner = token[1:-1].strip()
    if not inner:
        raise ValueError("Empty choice block '[]' is not allowed in onset or coda patterns")
    pieces: List[str] = []
    current: List[str] = []
    for char in inner:
        if char in {" ", "\t", "\n", "\r", ",", "|"}:
            if current:
                pieces.append("".join(current))
                current = []
        elif char in {"_", ".", "+"}:
            if current:
                pieces.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        pieces.append("".join(current))
    pieces = [piece for piece in (piece.strip() for piece in pieces) if piece]
    if pieces:
        if len(pieces) == 1 and pieces[0] == inner:
            # no explicit separators; treat contiguous uppercase symbols as individual consonants when possible
            if inner.isalpha() and inner.isupper():
                letters: List[str] = []
                for char in inner:
                    symbol = char
                    if symbol in _SINGLE_ONSETS:
                        letters.append(symbol)
                    else:
                        return (inner,)
                if letters:
                    return tuple(letters)
        return tuple(pieces)
    # default fallback: treat each uppercase consonant individually when possible
    if inner.isalpha() and inner.isupper():
        letters = [char for char in inner if char in _SINGLE_ONSETS]
        if letters and len(letters) == len(inner):
            return tuple(letters)
    return (inner,)


def _match_token_pattern(pattern: Sequence[_TokenPattern], cluster: Sequence[str]) -> bool:
    def _match(pi: int, ci: int) -> bool:
        while pi < len(pattern):
            part = pattern[pi]
            if part.kind == "star":
                # Collapse consecutive stars for efficiency
                while pi + 1 < len(pattern) and pattern[pi + 1].kind == "star":
                    pi += 1
                next_index = pi + 1
                if next_index == len(pattern):
                    return True
                for skip in range(ci, len(cluster) + 1):
                    if _match(next_index, skip):
                        return True
                return False
            if ci >= len(cluster):
                return False
            token = cluster[ci]
            if part.kind == "literal":
                if token != part.values[0]:
                    return False
            elif part.kind == "any":
                pass
            elif part.kind == "set":
                if token not in part.values:
                    return False
            else:
                raise ValueError(f"Unknown token pattern kind '{part.kind}'")
            pi += 1
            ci += 1
        return ci == len(cluster)

    return _match(0, 0)

