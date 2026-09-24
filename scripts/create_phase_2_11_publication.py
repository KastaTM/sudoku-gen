"""Generate the bounded 36-puzzle Phase 2.11 development publication."""

from pathlib import Path

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.fingerprint import FingerprintMode
from sudoku_gen.generator import DifficultyGenerationStrategy
from sudoku_gen.pattern import Symmetry
from sudoku_gen.publication import (
    CoverContent,
    FrontMatterConfig,
    PageLayoutProfile,
    PublicationJob,
    PublicationMetadata,
    PublicationSectionSpec,
    export_publication,
    run_publication,
)

if __name__ == "__main__":
    job = PublicationJob(
        metadata=PublicationMetadata(
            "Sudokus de ejemplo",
            subtitle="Edición de práctica",
            author="Sudoku Gen",
            copyright_notice="© 2026 Sudoku Gen",
            instructions="Completa cada cuadrícula sin repetir dígitos.",
        ),
        sections=(PublicationSectionSpec("Fácil", Difficulty.EASY, 36),),
        seed=202611,
        front_matter=FrontMatterConfig(True, True, True, True),
        target_clues=30,
        symmetry=Symmetry.ROTATIONAL_180,
        deduplication_mode=FingerprintMode.DIGIT_NORMALIZED,
        max_attempts=500,
        strategy=DifficultyGenerationStrategy.RANDOM_RETRY,
        page_layout=PageLayoutProfile(2, 6, 1),
        cover_content=CoverContent(back_cover_copy="Una colección de sudokus."),
    )
    result = run_publication(job)
    export_publication(result, Path("dev-output/phase-2.11-publication"))
