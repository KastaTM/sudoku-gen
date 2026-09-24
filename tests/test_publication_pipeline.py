"""Focused deterministic configuration and regeneration-budget pipeline tests."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

import sudoku_gen.publication.pipeline as pipeline
from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.generator import PuzzleBatch, PuzzleBatchItem
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookSectionInput,
    CoverContent,
    CoverReport,
    FrontMatterConfig,
    PageLayoutProfile,
    PublicationJob,
    PublicationMetadata,
    PublicationSectionSpec,
    build_book_plan,
    export_publication,
    plan_book_pages,
    plan_interior,
    plan_paperback_cover,
    publication_manifest,
    render_cover_pdf,
    render_interior_drawings,
    render_interior_pdf,
    run_publication,
    section_seed,
)
from sudoku_gen.quality import BatchAuditReport, BatchQualityReport

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def metadata() -> PublicationMetadata:
    return PublicationMetadata("Pipeline test")


def test_section_seed_is_stable_and_distinct_by_section_and_retry() -> None:
    first = section_seed(1234, 0, 0)

    assert first == section_seed(1234, 0, 0)
    assert first != section_seed(1234, 1, 0)
    assert first != section_seed(1234, 0, 1)
    with pytest.raises(TypeError):
        section_seed(True, 0)


def test_regeneration_budget_validation_and_zero_boundary_configuration() -> None:
    section = PublicationSectionSpec("Easy", Difficulty.EASY, 1)
    job = PublicationJob(metadata(), (section,), 1, max_section_regenerations=0)

    assert job.max_section_regenerations == 0
    with pytest.raises(TypeError):
        PublicationJob(metadata(), (section,), 1, max_section_regenerations=True)
    with pytest.raises(ValueError):
        PublicationJob(metadata(), (section,), 1, max_section_regenerations=-1)


def batch(clue_index: int) -> PuzzleBatch:
    puzzle = SudokuPuzzle(
        Grid(
            tuple(
                value if index == clue_index else 0
                for index, value in enumerate(SOLUTION.cells)
            )
        ),
        SOLUTION,
    )
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    item = PuzzleBatchItem(
        puzzle, report, fingerprint_puzzle(puzzle, FingerprintMode.DIGIT_NORMALIZED)
    )
    return PuzzleBatch(
        (item,), Difficulty.EASY, FingerprintMode.DIGIT_NORMALIZED, 1, 0, 0
    )


def job(*, regenerations: int = 1) -> PublicationJob:
    return PublicationJob(
        metadata(),
        (
            PublicationSectionSpec("First", Difficulty.EASY, 1),
            PublicationSectionSpec("Second", Difficulty.EASY, 1),
        ),
        99,
        front_matter=FrontMatterConfig(False, False, False, False),
        page_layout=PageLayoutProfile(1, 1, 1),
        max_section_regenerations=regenerations,
        cover_content=CoverContent(),
    )


def patch_final_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline, "audit_batch", lambda *_args, **_kwargs: BatchAuditReport(True, 1, ())
    )
    monkeypatch.setattr(
        pipeline,
        "analyze_batch",
        lambda *_args: BatchQualityReport(
            1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, ()
        ),
    )
    monkeypatch.setattr(pipeline, "plan_book_pages", lambda book, **_kwargs: object())
    monkeypatch.setattr(
        pipeline,
        "plan_interior",
        lambda *_args, **_kwargs: type("I", (), {"physical_page_count": 24})(),
    )
    monkeypatch.setattr(
        pipeline, "render_interior_drawings", lambda *_args, **_kwargs: ()
    )
    monkeypatch.setattr(
        pipeline, "render_interior_pdf", lambda *_args, **_kwargs: b"interior"
    )
    monkeypatch.setattr(
        pipeline,
        "preflight_pdf",
        lambda *_args, **_kwargs: type(
            "P",
            (),
            {"has_blocking_issues": False, "issues": (), "actual_page_count": 24},
        )(),
    )
    monkeypatch.setattr(
        pipeline,
        "plan_paperback_cover",
        lambda *_args, **_kwargs: type(
            "C",
            (),
            {
                "geometry": type(
                    "G",
                    (),
                    {
                        "canvas": type("R", (), {"width": 1, "height": 1})(),
                        "spine": type("R", (), {"width": 1})(),
                    },
                )()
            },
        )(),
    )
    monkeypatch.setattr(
        pipeline, "render_cover_pdf", lambda *_args, **_kwargs: b"cover"
    )
    monkeypatch.setattr(pipeline, "validate_cover_pdf", lambda *_args: CoverReport(()))


def test_cross_section_collision_regenerates_only_conflicting_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_final_stages(monkeypatch)
    calls: list[int] = []
    batches = iter((batch(0), batch(0), batch(1)))
    monkeypatch.setattr(
        pipeline,
        "generate_puzzle_batch",
        lambda *args, **kwargs: calls.append(kwargs["seed"]) or next(batches),
    )

    result = run_publication(job())

    assert calls == [section_seed(99, 0), section_seed(99, 1), section_seed(99, 1, 1)]
    assert result.section_regenerations == (0, 1)
    assert result.section_seeds == (section_seed(99, 0), section_seed(99, 1, 1))


@pytest.mark.parametrize("budget, expected_calls", [(0, 2), (2, 4)])
def test_persistent_collision_exhausts_exact_regeneration_budget(
    monkeypatch: pytest.MonkeyPatch, budget: int, expected_calls: int
) -> None:
    patch_final_stages(monkeypatch)
    calls: list[int] = []
    monkeypatch.setattr(
        pipeline,
        "generate_puzzle_batch",
        lambda *args, **kwargs: calls.append(kwargs["seed"]) or batch(0),
    )

    with pytest.raises(ValueError, match="regeneration budget"):
        run_publication(job(regenerations=budget))
    assert len(calls) == expected_calls
    assert calls[0] == section_seed(99, 0)


def test_staged_export_writes_four_files_and_refuses_existing_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_final_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline, "generate_puzzle_batch", lambda *_args, **_kwargs: batch(0)
    )
    result = run_publication(
        PublicationJob(
            metadata(),
            (PublicationSectionSpec("Only", Difficulty.EASY, 1),),
            1,
            front_matter=FrontMatterConfig(False, False, False, False),
            page_layout=PageLayoutProfile(1, 1, 1),
        )
    )
    monkeypatch.setattr(pipeline, "publication_manifest", lambda _result: b"{}")
    destination = tmp_path / "book"

    export_publication(result, destination)
    assert {path.name for path in destination.iterdir()} == {
        "interior.pdf",
        "cover.pdf",
        "manifest.json",
        "quality-report.json",
    }
    with pytest.raises(FileExistsError):
        export_publication(result, destination)


def test_staged_export_cleans_up_after_intermediate_write_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_final_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline, "generate_puzzle_batch", lambda *_args, **_kwargs: batch(0)
    )
    result = run_publication(
        PublicationJob(
            metadata(),
            (PublicationSectionSpec("Only", Difficulty.EASY, 1),),
            1,
            front_matter=FrontMatterConfig(False, False, False, False),
            page_layout=PageLayoutProfile(1, 1, 1),
        )
    )
    original = Path.write_bytes
    calls = 0

    def fail_second(self: Path, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("write failure")
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", fail_second)
    destination = tmp_path / "book"
    with pytest.raises(OSError, match="write failure"):
        export_publication(result, destination)
    assert not destination.exists()
    assert not (tmp_path / "book.staging").exists()


def test_manifest_records_retry_statistics_and_exact_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_final_stages(monkeypatch)
    batches = iter((batch(0), batch(0), batch(1)))
    monkeypatch.setattr(
        pipeline, "generate_puzzle_batch", lambda *_args, **_kwargs: next(batches)
    )
    result = run_publication(job())
    manifest = json.loads(publication_manifest(result))

    assert manifest == json.loads(publication_manifest(result))
    assert manifest["sections"][1]["seed"] == section_seed(99, 1, 1)
    assert manifest["sections"][1]["regenerations"] == 1
    assert manifest["sections"][0]["attempts"] == 1
    assert manifest["interior_sha256"] == sha256(b"interior").hexdigest()
    assert manifest["cover_sha256"] == sha256(b"cover").hexdigest()
    assert manifest["interior_page_count"] == manifest["effective_page_count"] == 24


def test_preexisting_staging_directory_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_final_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline, "generate_puzzle_batch", lambda *_args, **_kwargs: batch(0)
    )
    result = run_publication(
        PublicationJob(
            metadata(),
            (PublicationSectionSpec("Only", Difficulty.EASY, 1),),
            1,
            front_matter=FrontMatterConfig(False, False, False, False),
            page_layout=PageLayoutProfile(1, 1, 1),
        )
    )
    staging = tmp_path / "book.staging"
    staging.mkdir()
    sentinel = staging / "sentinel.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError, match="staging"):
        export_publication(result, tmp_path / "book")
    assert sentinel.read_text() == "keep"
    assert not (tmp_path / "book").exists()


@pytest.mark.parametrize("stage", ["audit", "preflight", "cover"])
def test_blocking_pipeline_stages_prevent_success(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    patch_final_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline, "generate_puzzle_batch", lambda *_args, **_kwargs: batch(0)
    )
    if stage == "audit":
        monkeypatch.setattr(
            pipeline,
            "audit_batch",
            lambda *_args, **_kwargs: BatchAuditReport(False, 1, ()),
        )
    elif stage == "preflight":
        monkeypatch.setattr(
            pipeline,
            "preflight_pdf",
            lambda *_args, **_kwargs: type(
                "P", (), {"has_blocking_issues": True, "issues": ("blocked",)}
            )(),
        )
    else:
        monkeypatch.setattr(
            pipeline, "validate_cover_pdf", lambda *_args: CoverReport((object(),))
        )
    expected = "Cover" if stage == "cover" else stage
    with pytest.raises(ValueError, match=expected):
        run_publication(
            PublicationJob(
                metadata(),
                (PublicationSectionSpec("Only", Difficulty.EASY, 1),),
                1,
                front_matter=FrontMatterConfig(False, False, False, False),
                page_layout=PageLayoutProfile(1, 1, 1),
            )
        )


def test_real_editorial_rendering_and_cover_integration_from_controlled_batch() -> None:
    controlled = PuzzleBatch(
        tuple(batch(index).items[0] for index in range(4)),
        Difficulty.EASY,
        FingerprintMode.DIGIT_NORMALIZED,
        4,
        0,
        0,
    )
    book = build_book_plan((BookSectionInput("Easy", controlled),))
    pages = plan_book_pages(book, layout=PageLayoutProfile(2, 6, 7))
    interior = plan_interior(
        metadata(), pages, config=FrontMatterConfig(True, False, False, False)
    )
    drawings = render_interior_drawings(interior)
    interior_pdf = render_interior_pdf(interior)
    cover = plan_paperback_cover(interior_pdf, metadata())
    cover_pdf = render_cover_pdf(cover)

    assert tuple(item.puzzle.number for item in pages.pages[0].items) == (1, 2)
    assert interior.physical_page_count == len(drawings) == 4
    assert interior_pdf.startswith(b"%PDF") and cover_pdf.startswith(b"%PDF")
    assert cover.geometry.effective_page_count == 4
