"""Create the Phase 2.10 cover from the finalized Phase 2.9 interior PDF."""

from pathlib import Path

from sudoku_gen.publication import (
    CoverContent,
    Line,
    Point,
    PublicationMetadata,
    VectorDrawing,
    plan_paperback_cover,
    render_cover_drawing,
    render_cover_pdf,
    render_svg,
    validate_cover_pdf,
)

if __name__ == "__main__":
    output = Path("dev-output")
    interior = output / "phase-2.9-editorial-preview.pdf"
    if not interior.exists():
        raise RuntimeError("Generate the Phase 2.9 editorial preview first.")
    metadata = PublicationMetadata(
        "Sudokus de ejemplo", subtitle="Edición de práctica", author="Sudoku Gen"
    )
    plan = plan_paperback_cover(
        interior.read_bytes(),
        metadata,
        content=CoverContent(
            back_cover_copy="Una colección de sudokus para practicar."
        ),
    )
    pdf = render_cover_pdf(plan)
    report = validate_cover_pdf(pdf, plan)
    if report.has_blocking_issues:
        raise RuntimeError(", ".join(issue.code for issue in report.issues))
    (output / "phase-2.10-cover-preview.pdf").write_bytes(pdf)
    final_drawing = render_cover_drawing(plan)
    (output / "phase-2.10-cover-preview.svg").write_text(
        render_svg(final_drawing), encoding="utf-8"
    )
    g = plan.geometry
    guides = tuple(
        Line(Point(rect.left, rect.top), Point(rect.right, rect.top), 0.75, False)
        for rect in (g.back_trim, g.spine, g.front_trim, g.barcode_exclusion)
    )
    (output / "phase-2.10-cover-diagnostic.svg").write_text(
        render_svg(VectorDrawing(g.canvas, guides)), encoding="utf-8"
    )
    dimensions = f"{g.canvas.width / 72:.6f} × {g.canvas.height / 72:.2f}"
    print(f"Wrote cover preview ({dimensions} inches).")
