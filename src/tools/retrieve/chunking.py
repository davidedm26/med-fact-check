from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import nltk

@dataclass
class SourceMetadata:
    id: str = ""
    title: str = ""
    type: str = "Scientific Literature"
    date: str = "N/A"
    url: str = ""
    extra_info: Dict[str, Any] = field(default_factory=dict)

    @property
    def target_source(self) -> str:
        return {
            "Scientific Literature": "literature",
            "Clinical Trial": "clinical_trials",
            "Systematic Review": "systematic_reviews",
            "Protein Knowledge": "knowledge_base",
        }.get(self.type, "literature")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "date": self.date,
            "url": self.url,
            "extra_info": self.extra_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceMetadata":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            type=data.get("type", "Scientific Literature"),
            date=data.get("date", "N/A"),
            url=data.get("url", ""),
            extra_info=data.get("extra_info") or {},
        )


@dataclass
class IndexedChunk:
    chunk_id: str
    text: str
    chunk_index: int
    section: str
    source: SourceMetadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "section": self.section,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndexedChunk":
        return cls(
            chunk_id=data["chunk_id"],
            text=data["text"],
            chunk_index=data["chunk_index"],
            section=data["section"],
            source=SourceMetadata.from_dict(data["source"]),
        )


@dataclass
class RetrievedText:
    text_content: str
    source_metadata: SourceMetadata
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_content": self.text_content,
            "source_metadata": self.source_metadata.to_dict(),
            "score": self.score,
        }


@dataclass
class BiomedicalChunker:
    chunk_size: int = 300
    overlap: int = 50

    _SECTION_RE_PARTS = (
        r"Abstract", r"Introduction", r"Background",
        r"Methods?", r"Materials?\s+and\s+Methods?",
        r"Results?", r"Discussion", r"Conclusions?",
        r"References?", r"Eligibility", r"Summary",
        r"Outcomes?", r"Interventions?",
    )

    def __post_init__(self) -> None:
        self._section_pat = re.compile(
            r"^(?:" + "|".join(self._SECTION_RE_PARTS) + r")[\s:]*$",
            re.IGNORECASE | re.MULTILINE,
        )
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)

    def chunk(self, text: str, source: SourceMetadata) -> List[IndexedChunk]:
        chunks: List[IndexedChunk] = []
        idx = 0

        for section_label, section_text in self._split_sections(text):
            if section_label == "References":
                continue

            sentences = nltk.tokenize.sent_tokenize(section_text)
            if not sentences:
                continue

            current_chunk_sentences = []
            current_chunk_word_count = 0
            new_sentences_added = 0

            for sentence in sentences:
                sentence_words = sentence.split()
                sentence_word_count = len(sentence_words)

                if current_chunk_word_count + sentence_word_count > self.chunk_size and current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences).strip()
                    chunks.append(
                        IndexedChunk(
                            chunk_id=self._make_id(source.id, idx),
                            text=chunk_text,
                            chunk_index=idx,
                            section=section_label,
                            source=source,
                        )
                    )
                    idx += 1

                    overlap_sentences = []
                    overlap_word_count = 0
                    for s in reversed(current_chunk_sentences):
                        overlap_sentences.insert(0, s)
                        overlap_word_count += len(s.split())
                        if overlap_word_count >= self.overlap:
                            break
                    
                    if len(overlap_sentences) == len(current_chunk_sentences):
                        overlap_sentences = overlap_sentences[1:]
                        overlap_word_count = sum(len(s.split()) for s in overlap_sentences)

                    current_chunk_sentences = overlap_sentences
                    current_chunk_word_count = overlap_word_count
                    new_sentences_added = 0

                current_chunk_sentences.append(sentence)
                current_chunk_word_count += sentence_word_count
                new_sentences_added += 1

            if current_chunk_sentences:
                new_words_count = sum(len(s.split()) for s in current_chunk_sentences[-new_sentences_added:]) if new_sentences_added > 0 else 0
                if new_words_count < 50 and chunks and chunks[-1].section == section_label:
                    if new_sentences_added > 0:
                        new_text = " ".join(current_chunk_sentences[-new_sentences_added:])
                        chunks[-1].text += " " + new_text
                else:
                    chunk_text = " ".join(current_chunk_sentences).strip()
                    if len(chunk_text) >= 40:
                        chunks.append(
                            IndexedChunk(
                                chunk_id=self._make_id(source.id, idx),
                                text=chunk_text,
                                chunk_index=idx,
                                section=section_label,
                                source=source,
                            )
                        )
                        idx += 1

        return chunks

    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        sections: List[Tuple[str, str]] = []
        current_label = "Body"
        current_lines: List[str] = []

        for line in text.split("\n"):
            if self._section_pat.match(line.strip()):
                if current_lines:
                    sections.append((current_label, "\n".join(current_lines)))
                current_label = self._normalise_section(line.strip())
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_label, "\n".join(current_lines)))

        return sections or [("Body", text)]

    @staticmethod
    def _normalise_section(raw: str) -> str:
        mapping = {
            "abstract": "Abstract",
            "introduction": "Introduction",
            "background": "Background",
            "results": "Results",
            "discussion": "Discussion",
            "references": "References",
            "conclusion": "Conclusion",
            "conclusions": "Conclusion",
            "eligibility": "Eligibility",
            "summary": "Summary",
        }
        for key, label in mapping.items():
            if key in raw.lower():
                return label
        if "method" in raw.lower():
            return "Methods"
        return "Body"

    @staticmethod
    def _make_id(doc_id: str, idx: int) -> str:
        return hashlib.md5(f"{doc_id}__{idx}".encode()).hexdigest()[:14]


