"""Bounded deterministic orchestration from publication configuration to artifacts."""

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.exceptions import DuplicatePublicationPuzzleError
from sudoku_gen.fingerprint import FingerprintMode
from sudoku_gen.generator import (
    DifficultyGenerationStrategy,
    PuzzleBatch,
    generate_puzzle_batch,
)
from sudoku_gen.pattern import Symmetry
from sudoku_gen.publication.cover import (
    CoverContent,
    CoverPlan,
    CoverReport,
    plan_paperback_cover,
    render_cover_pdf,
    validate_cover_pdf,
)
from sudoku_gen.publication.interior import (
    FrontMatterConfig,
    InteriorPlan,
    PublicationMetadata,
    plan_interior,
)
from sudoku_gen.publication.interior_pdf import (
    render_interior_drawings,
    render_interior_pdf,
)
from sudoku_gen.publication.locale import ES_ES, BookLocale
from sudoku_gen.publication.models import BookPlan, BookSectionInput, build_book_plan
from sudoku_gen.publication.pages import PageLayoutProfile, PagePlan, plan_book_pages
from sudoku_gen.publication.preflight import (
    PreflightReport,
    PrintProfile,
    preflight_pdf,
)
from sudoku_gen.quality import (
    BatchAuditReport,
    BatchQualityReport,
    analyze_batch,
    audit_batch,
)


@dataclass(frozen=True, slots=True)
class PublicationSectionSpec:
    title: str
    difficulty: Difficulty
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("section title must be a nonempty string.")
        if (
            not isinstance(self.difficulty, Difficulty)
            or self.difficulty is Difficulty.UNRATED
        ):
            raise ValueError("section difficulty must be publishable.")
        if type(self.count) is not int or self.count < 1:
            raise ValueError("section count must be a positive built-in integer.")


@dataclass(frozen=True, slots=True)
class PublicationJob:
    metadata: PublicationMetadata
    sections: tuple[PublicationSectionSpec, ...]
    seed: int
    front_matter: FrontMatterConfig = FrontMatterConfig()
    target_clues: int = 30
    symmetry: Symmetry = Symmetry.ROTATIONAL_180
    deduplication_mode: FingerprintMode = FingerprintMode.DIGIT_NORMALIZED
    max_attempts: int = 500
    max_section_regenerations: int = 3
    strategy: DifficultyGenerationStrategy = DifficultyGenerationStrategy.RANDOM_RETRY
    page_layout: PageLayoutProfile = PageLayoutProfile()
    print_profile: PrintProfile = PrintProfile()
    cover_content: CoverContent = CoverContent()
    locale: BookLocale = ES_ES

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, PublicationMetadata) or not self.sections:
            raise ValueError("metadata and at least one section are required.")
        if not all(
            isinstance(section, PublicationSectionSpec) for section in self.sections
        ):
            raise TypeError("sections must contain PublicationSectionSpec instances.")
        if type(self.seed) is not int:
            raise TypeError("seed must be a built-in integer.")
        if not isinstance(self.locale, BookLocale):
            raise TypeError("locale must be a BookLocale.")
        if type(self.max_section_regenerations) is not int:
            raise TypeError("max_section_regenerations must be a built-in integer.")
        if self.max_section_regenerations < 0:
            raise ValueError("max_section_regenerations must not be negative.")


@dataclass(frozen=True, slots=True)
class PublicationResult:
    job: PublicationJob
    batches: tuple[PuzzleBatch, ...]
    section_seeds: tuple[int, ...]
    section_regenerations: tuple[int, ...]
    quality_reports: tuple[BatchQualityReport, ...]
    audit_reports: tuple[BatchAuditReport, ...]
    book_plan: BookPlan
    page_plan: PagePlan
    interior_plan: InteriorPlan
    interior_pdf: bytes
    cover_plan: CoverPlan
    cover_pdf: bytes
    interior_preflight: PreflightReport
    cover_validation: CoverReport


def section_seed(seed: int, section_index: int, retry_index: int = 0) -> int:
    """Derive a stable local-generator seed without Python hash randomization."""
    if (
        type(seed) is not int
        or type(section_index) is not int
        or type(retry_index) is not int
    ):
        raise TypeError(
            "seed, section_index, and retry_index must be built-in integers."
        )
    return int.from_bytes(
        sha256(f"{seed}:{section_index}:{retry_index}".encode()).digest()[:16], "big"
    )


def run_publication(job: PublicationJob) -> PublicationResult:
    """Generate, audit, plan, render, and validate one bounded publication job."""
    if not isinstance(job, PublicationJob):
        raise TypeError("job must be a PublicationJob.")
    accepted: list[PuzzleBatch] = []
    seeds: list[int] = []
    regenerations: list[int] = []
    for index, section in enumerate(job.sections):
        for retry in range(job.max_section_regenerations + 1):
            seed = section_seed(job.seed, index, retry)
            batch = generate_puzzle_batch(
                section.count,
                section.difficulty,
                seed=seed,
                target_clues=job.target_clues,
                symmetry=job.symmetry,
                deduplication_mode=job.deduplication_mode,
                max_attempts=job.max_attempts,
                strategy=job.strategy,
            )
            try:
                build_book_plan(
                    tuple(
                        BookSectionInput(spec.title, candidate)
                        for spec, candidate in zip(
                            job.sections[:index], accepted, strict=True
                        )
                    )
                    + (BookSectionInput(section.title, batch),),
                    deduplication_mode=job.deduplication_mode,
                )
            except DuplicatePublicationPuzzleError:
                if retry == job.max_section_regenerations:
                    raise ValueError(
                        "Cross-section regeneration budget exhausted."
                    ) from None
                continue
            accepted.append(batch)
            seeds.append(seed)
            regenerations.append(retry)
            break
    batches = tuple(accepted)
    audits = tuple(audit_batch(batch, symmetry=job.symmetry) for batch in batches)
    if any(not report.passed for report in audits):
        raise ValueError("Puzzle audit failed.")
    book = build_book_plan(
        tuple(
            BookSectionInput(spec.title, batch)
            for spec, batch in zip(job.sections, batches, strict=True)
        ),
        deduplication_mode=job.deduplication_mode,
    )
    pages = plan_book_pages(book, layout=job.page_layout)
    interior = plan_interior(job.metadata, pages, config=job.front_matter)
    drawings = render_interior_drawings(
        interior, print_profile=job.print_profile, locale=job.locale
    )
    interior_pdf = render_interior_pdf(
        interior, print_profile=job.print_profile, locale=job.locale
    )
    preflight = preflight_pdf(
        interior_pdf,
        drawings=drawings,
        interior_plan=interior,
        profile=job.print_profile,
    )
    if preflight.has_blocking_issues:
        raise ValueError("Interior preflight failed.")
    cover = plan_paperback_cover(
        interior_pdf,
        job.metadata,
        content=job.cover_content,
        print_profile=job.print_profile,
    )
    cover_pdf = render_cover_pdf(cover)
    cover_validation = validate_cover_pdf(cover_pdf, cover)
    if cover_validation.has_blocking_issues:
        raise ValueError("Cover validation failed.")
    return PublicationResult(
        job,
        batches,
        tuple(seeds),
        tuple(regenerations),
        tuple(analyze_batch(batch) for batch in batches),
        audits,
        book,
        pages,
        interior,
        interior_pdf,
        cover,
        cover_pdf,
        preflight,
        cover_validation,
    )


def publication_manifest(result: PublicationResult) -> bytes:
    """Return deterministic JSON describing final artifacts and reproducible inputs."""
    payload = {
        "schema_version": 1,
        "title": result.job.metadata.title,
        "author": result.job.metadata.author,
        "seed": result.job.seed,
        "sections": [
            {
                "title": spec.title,
                "difficulty": spec.difficulty.value,
                "count": spec.count,
                "seed": result.section_seeds[index],
                "regenerations": result.section_regenerations[index],
                "attempts": batch.attempts,
            }
            for index, (spec, batch) in enumerate(
                zip(result.job.sections, result.batches, strict=True)
            )
        ],
        "interior_page_count": result.interior_plan.physical_page_count,
        "effective_page_count": result.job.print_profile.effective_page_count(
            result.interior_plan.physical_page_count
        ),
        "interior_sha256": sha256(result.interior_pdf).hexdigest(),
        "cover_sha256": sha256(result.cover_pdf).hexdigest(),
        "cover_width_points": result.cover_plan.geometry.canvas.width,
        "cover_height_points": result.cover_plan.geometry.canvas.height,
        "spine_width_points": result.cover_plan.geometry.spine.width,
        "preflight_blocking": result.interior_preflight.has_blocking_issues,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def export_publication(result: PublicationResult, directory: Path) -> None:
    """Write validated artifacts once; refuse an existing destination directory."""
    if not isinstance(directory, Path):
        raise TypeError("directory must be a pathlib.Path.")
    if directory.exists():
        raise FileExistsError("Publication output directory already exists.")
    staging = directory.with_name(f"{directory.name}.staging")
    if staging.exists():
        raise FileExistsError("Publication staging directory already exists.")
    staging.mkdir(parents=True)
    try:
        (staging / "interior.pdf").write_bytes(result.interior_pdf)
        (staging / "cover.pdf").write_bytes(result.cover_pdf)
        (staging / "manifest.json").write_bytes(publication_manifest(result))
        (staging / "quality-report.json").write_bytes(
            json.dumps(
                {
                    "batches": [
                        {
                            "accepted_count": quality.accepted_count,
                            "attempts": quality.attempts,
                            "difficulty_rejections": quality.difficulty_rejections,
                            "duplicate_rejections": quality.duplicate_rejections,
                            "audit_passed": audit.passed,
                            "audit_issues": [issue.code for issue in audit.issues],
                        }
                        for quality, audit in zip(
                            result.quality_reports, result.audit_reports, strict=True
                        )
                    ],
                    "preflight_issues": [
                        issue.code for issue in result.interior_preflight.issues
                    ],
                    "cover_issues": [
                        issue.code for issue in result.cover_validation.issues
                    ],
                },
                sort_keys=True,
            ).encode()
        )
        staging.rename(directory)
    except Exception:
        if staging.exists():
            for file in staging.iterdir():
                file.unlink()
            staging.rmdir()
        raise
