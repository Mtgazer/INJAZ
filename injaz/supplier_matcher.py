"""
Conservative Supplier Matching and Grouping for Injaz (إنجاز).
Identifies similar supplier names, font-spacing artifacts, and whitespace variations
to facilitate bulk human review and correction while preserving financial audit integrity.
"""
import re
import unicodedata
import difflib
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple, Set

from injaz.models import TransactionRecord
from injaz.normalizer import validate_supplier_field


@dataclass
class SupplierVariant:
    """Represents a specific string variation of a supplier name within a group."""
    raw_name: str
    record_count: int
    has_spacing_issue: bool
    is_valid: bool
    record_indices: List[int] = field(default_factory=list)


@dataclass
class SupplierGroupSuggestion:
    """A suggested cluster of similar supplier records for bulk human review."""
    group_id: str
    suggested_label: str
    canonical_candidate: str
    variants: List[SupplierVariant]
    total_records: int
    reason_code: str
    reason_ar: str
    record_indices: List[int]
    records: List[TransactionRecord] = field(default_factory=list)


def normalize_for_comparison(text: Optional[str]) -> str:
    """
    Normalizes Arabic text conservatively for comparison purposes only.
    Normalizes NFKC, removes tatweel, unifies common Alef variants,
    unifies word-final Taa Marbuta / Haa, Ya / Alef Maksura,
    removes punctuation, and collapses multiple spaces.
    Does NOT mutate the original text.
    """
    if not text:
        return ""
    norm = unicodedata.normalize('NFKC', text)
    norm = norm.replace('\ue900', '')
    norm = re.sub(r'[\u0640]', '', norm)  # Arabic tatweel
    norm = re.sub(r'[إأآٱ]', 'ا', norm)   # Common Alef variants
    norm = re.sub(r'[ةه]\b', 'ه', norm)    # Word-final Taa Marbuta / Haa
    norm = re.sub(r'[يى]\b', 'ي', norm)    # Word-final Ya / Alef Maksura
    norm = re.sub(r'[()\[\]{}.,:;!?\'"/\\_\-]', ' ', norm)  # Punctuation
    norm = re.sub(r'\s+', ' ', norm).strip()
    return norm


def spaceless_key(norm_text: str) -> str:
    """Removes all whitespace from normalized text to match strings across spacing boundaries."""
    return re.sub(r'\s+', '', norm_text)


def has_font_spacing_artifacts(text: Optional[str]) -> bool:
    """
    Detects whether an Arabic name has font-spacing artifacts (e.g. split isolated letters
    or multiple single-letter tokens caused by PDF font extraction).
    """
    if not text:
        return False
    # Check for isolated single Arabic letters
    norm = normalize_for_comparison(text)
    single_letters = re.findall(r'\b[أ-ي]\b', norm)
    # Check for adjacent single-letter tokens: e.g. 'ا ل ت غ ي ي ر'
    if re.search(r'\b[أ-ي]\s+[أ-ي]\b', norm):
        return True
    return len(single_letters) >= 1


def clean_despaced_candidate(text: str) -> str:
    """
    Produces a clean, human-readable candidate name by collapsing spaces between
    isolated single Arabic letters while respecting clear multi-letter word tokens.
    """
    if not text:
        return ""
    s = text.strip()
    # Collapse isolated letters adjacent to words or other letters using match groups
    for _ in range(4):
        # Single letter followed by space and single letter: e.g. 'ا ل' -> 'ال'
        s = re.sub(r'\b([أ-ي])\s+([أ-ي])\b', r'\1\2', s)
        # Word of 2+ letters followed by single isolated letter: e.g. 'للمقا و' -> 'للمقاو'
        s = re.sub(r'([أ-ي]{2,})\s+([أ-ي])\b', r'\1\2', s)
        # Single isolated letter followed by word of 2+ letters: e.g. 'ا لتغيير' -> 'التغيير'
        s = re.sub(r'\b([أ-ي])\s+([أ-ي]{2,})', r'\1\2', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s



def generate_canonical_candidate(variants: List[str]) -> str:
    """
    Selects or generates the best initial canonical name candidate for user review.
    Prefers valid, clean variants over noisy ones.
    """
    if not variants:
        return ""

    # 1. Check if any variant is already fully valid with no spacing issues
    valid_variants = [
        v for v in variants
        if validate_supplier_field(v)[0] and not has_font_spacing_artifacts(v)
    ]
    if valid_variants:
        # Return the most frequent / cleanest valid variant
        return Counter(valid_variants).most_common(1)[0][0]

    # 2. Otherwise clean the most frequent variant
    most_common_raw = Counter(variants).most_common(1)[0][0]
    candidate = clean_despaced_candidate(most_common_raw)
    return candidate or most_common_raw


def detect_group_reason(variants: List[str], records: List[TransactionRecord]) -> Tuple[str, str]:
    """Determines the primary reason why these records are grouped together."""
    has_spacing_issues = any(
        not r.is_supplier_valid
        or "font-spaced" in " ".join(r.review_reasons).lower()
        or has_font_spacing_artifacts(r.supplier_name)
        for r in records
    )

    if len(variants) == 1:
        if has_spacing_issues:
            return "font_spacing", "تجزئة أحرف وتفاوت مسافات في كشف الحساب"
        return "single_group", "سجلات تابعة للمورد نفسه"

    # Multiple variants: examine differences
    norm_variants = [normalize_for_comparison(v) for v in variants]
    spaceless_keys = set(spaceless_key(nv) for nv in norm_variants)

    if len(spaceless_keys) == 1:
        if has_spacing_issues:
            return "font_spacing", "تجزئة أحرف وتفاوت مسافات الطباعة"
        # Differ only by space
        return "whitespace", "اختلاف مسافات بيضاء بين المعاملات"

    # Check for spelling variation (Alef / Taa Marbuta)
    alef_free = set(re.sub(r'[إأآا]', 'ا', nv) for nv in norm_variants)
    if len(alef_free) == 1:
        return "spelling", "فروق إملائية شائعة (همزات وألف وتاء مربوطة)"

    # Check for trailing token differences (e.g. 'بلك', 'ف')
    return "token_variation", "تشابه كبير في مسمى المورد مع لواحق متبقية"


def are_names_conservatively_similar(name1: str, name2: str) -> bool:
    """
    Evaluates whether two distinct supplier strings represent credible variants
    of the same supplier entity, adhering to strict conservative thresholds.
    Never merges completely different companies.
    """
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    if not norm1 or not norm2:
        return False

    # 1. Spaceless equality (differ only in spacing/tatweel/hamza)
    if spaceless_key(norm1) == spaceless_key(norm2):
        return True

    # 2. High ratio check using difflib
    ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()
    if ratio >= 0.90 and min(len(norm1), len(norm2)) >= 8:
        # Check token overlap
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        common = tokens1.intersection(tokens2)
        # At least one significant shared token
        if any(len(t) >= 3 for t in common):
            return True

    # 3. Token containment where remainder is a single token or noise letter (e.g. 'ف', 'بلك')
    if norm1 in norm2 or norm2 in norm1:
        longer, shorter = (norm1, norm2) if len(norm1) >= len(norm2) else (norm2, norm1)
        diff = longer.replace(shorter, '').strip()
        if len(diff) <= 4 or diff in ('ف', 'بلك', 'شركة', 'مؤسسة'):
            return True

    return False


def group_similar_suppliers(records: List[TransactionRecord]) -> List[SupplierGroupSuggestion]:
    """
    Analyzes transaction records in memory and returns a list of conservative
    supplier group suggestions.
    Prioritizes records with invalid supplier flags or spacing review reasons,
    while also discovering other credible variants.
    Single-variant groups that are already 100% valid with NO review reasons are excluded
    to keep the interface focused on actionable corrections.
    """
    # 1. Map raw supplier names to records
    raw_map: Dict[str, List[Tuple[int, TransactionRecord]]] = defaultdict(list)
    for idx, r in enumerate(records):
        if r.supplier_name and r.supplier_name.strip():
            raw_map[r.supplier_name.strip()].append((idx, r))

    if not raw_map:
        return []

    # 2. Initial clustering by spaceless key
    spaceless_clusters: Dict[str, List[str]] = defaultdict(list)
    for raw_name in raw_map.keys():
        norm = normalize_for_comparison(raw_name)
        sk = spaceless_key(norm)
        spaceless_clusters[sk].append(raw_name)

    # 3. Secondary conservative merge across similar spaceless keys
    cluster_keys = list(spaceless_clusters.keys())
    merged_clusters: List[List[str]] = []
    used_keys: Set[str] = set()

    for i, k1 in enumerate(cluster_keys):
        if k1 in used_keys:
            continue
        current_variants = list(spaceless_clusters[k1])
        used_keys.add(k1)

        rep1 = current_variants[0]
        for j in range(i + 1, len(cluster_keys)):
            k2 = cluster_keys[j]
            if k2 in used_keys:
                continue
            rep2 = spaceless_clusters[k2][0]
            if are_names_conservatively_similar(rep1, rep2):
                current_variants.extend(spaceless_clusters[k2])
                used_keys.add(k2)

        merged_clusters.append(current_variants)

    # 4. Build SupplierGroupSuggestion objects
    suggestions: List[SupplierGroupSuggestion] = []

    for group_idx, variant_names in enumerate(merged_clusters, start=1):
        group_records: List[TransactionRecord] = []
        group_indices: List[int] = []
        variant_objs: List[SupplierVariant] = []

        for v_name in variant_names:
            items = raw_map[v_name]
            v_recs = [rec for _, rec in items]
            v_indices = [idx for idx, _ in items]

            is_valid, _ = validate_supplier_field(v_name)
            has_spacing = has_font_spacing_artifacts(v_name)

            variant_objs.append(SupplierVariant(
                raw_name=v_name,
                record_count=len(v_recs),
                has_spacing_issue=has_spacing,
                is_valid=is_valid,
                record_indices=v_indices
            ))

            group_records.extend(v_recs)
            group_indices.extend(v_indices)

        # Determine whether this group needs review
        has_any_invalid = any(not v.is_valid for v in variant_objs)
        has_any_spacing = any(v.has_spacing_issue for v in variant_objs)
        has_review_reasons = any(
            any("supplier" in r_reason.lower() or "font-spaced" in r_reason.lower() for r_reason in r.review_reasons)
            for r in group_records
        )
        is_multi_variant = len(variant_names) > 1

        # Keep group only if actionable: multiple variants OR has issues/review reasons
        if not (is_multi_variant or has_any_invalid or has_any_spacing or has_review_reasons):
            continue

        reason_code, reason_ar = detect_group_reason(variant_names, group_records)
        canonical = generate_canonical_candidate(variant_names)
        label = canonical if canonical else variant_names[0]

        suggestions.append(SupplierGroupSuggestion(
            group_id=f"grp_{group_idx}_{spaceless_key(normalize_for_comparison(label))[:12]}",
            suggested_label=label,
            canonical_candidate=canonical,
            variants=sorted(variant_objs, key=lambda v: v.record_count, reverse=True),
            total_records=len(group_records),
            reason_code=reason_code,
            reason_ar=reason_ar,
            record_indices=group_indices,
            records=group_records
        ))

    # Prioritize: groups with invalid/spacing issues first, then by total records descending
    suggestions.sort(
        key=lambda g: (
            1 if any(not v.is_valid or v.has_spacing_issue for v in g.variants) else 0,
            g.total_records
        ),
        reverse=True
    )

    return suggestions
