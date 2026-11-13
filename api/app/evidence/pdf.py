"""ReportLab Evidence Pack PDF generator (docs/PRODUCT.md US4 & docs/SECURITY.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass(frozen=True, slots=True)
class EvidencePackData:
    """Verified deterministic facts included in a claim's PDF evidence pack."""

    claim_id: str
    shop_id: str
    shop_name: str
    owner: str
    category: str
    street_name: str
    day_iso: str
    baseline_paise: int
    day_income_paise: int
    quorum_dropped: int
    quorum_total: int
    quorum_share: float
    rain_mm: float
    rain_source: str
    consent_at: datetime | None
    rules_version: str
    decision_reason: str
    simulated_label: str | None = None
    cause_label: str | None = None
    summary_text: str | None = None
    recent_days: tuple[tuple[str, int, int], ...] = ()


def _format_rs(amount_paise: int) -> str:
    return f"Rs. {amount_paise / 100.0:,.2f}"


def build_evidence_pdf(data: EvidencePackData, output_path: Path) -> Path:
    """Render a deterministic, adjuster-ready PDF evidence pack to `output_path`."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Silent Claim Evidence Pack - {data.claim_id}",
        author="Silent Claim (Simulated Demo)",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EvidenceTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#141311"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "EvidenceSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#5C574F"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#141311"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "EvidenceBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1E1D1A"),
    )

    drop_pct = (
        0.0 if data.baseline_paise <= 0 else (data.day_income_paise / data.baseline_paise) * 100.0
    )
    consent_str = (
        data.consent_at.isoformat() if data.consent_at is not None else "Pending / not recorded"
    )
    provenance_note = f"Synthetic data for demonstration | Rules version: {data.rules_version}" + (
        f" | {data.simulated_label}" if data.simulated_label else ""
    )

    story: list[object] = [
        Paragraph(f"SILENT CLAIM - EVIDENCE PACK ({data.claim_id})", title_style),
        Paragraph(provenance_note, subtitle_style),
        Paragraph("1. Claim & Merchant Summary", section_style),
    ]

    summary_rows = [
        ["Claim ID", data.claim_id],
        ["Shop", f"{data.shop_name} ({data.shop_id}) - {data.category}"],
        ["Owner", data.owner],
        ["Street", data.street_name],
        ["Event Date (IST)", data.day_iso],
        ["Consent Timestamp", consent_str],
        ["Trigger Reason", data.decision_reason],
        ["Rules Version", data.rules_version],
    ]
    if data.cause_label:
        summary_rows.append(["Voice Cause Classification", data.cause_label])

    summary_table = Table(summary_rows, colWidths=[52 * mm, 120 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1E1D1A")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFC8BC")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3EFE6")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(summary_table)

    story.append(Paragraph("2. Quantitative Loss & Environmental Proof", section_style))
    proof_rows = [
        ["Metric", "Value"],
        ["Baseline (28 trading-day median)", _format_rs(data.baseline_paise)],
        ["Event-day Income", f"{_format_rs(data.day_income_paise)} ({drop_pct:.1f}% of baseline)"],
        [
            "Street Quorum",
            f"{data.quorum_dropped} / {data.quorum_total} shops dropped ({data.quorum_share * 100:.1f}%)",
        ],
        ["Rainfall Measurement", f"{data.rain_mm:.1f} mm"],
        ["Rainfall Data Source", data.rain_source],
    ]
    proof_table = Table(proof_rows, colWidths=[68 * mm, 104 * mm])
    proof_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A24")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFC8BC")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(proof_table)

    if data.summary_text:
        story.append(Paragraph("3. Cosmetic Note (Non-Binding Summary)", section_style))
        story.append(Paragraph(data.summary_text, body_style))

    if data.recent_days:
        sec_num = 4 if data.summary_text else 3
        story.append(Paragraph(f"{sec_num}. Recent Daily Payment History (IST)", section_style))
        hist_rows = [["Date", "Transactions", "Daily Total"]]
        for day_s, n_pay, amt_p in data.recent_days:
            hist_rows.append([day_s, str(n_pay), _format_rs(amt_p)])
        hist_table = Table(hist_rows, colWidths=[50 * mm, 45 * mm, 77 * mm])
        hist_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAE4D8")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFC8BC")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(hist_table)

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Disclaimer: Synthetic data for demonstration. Automated claim eligibility and quorum "
            "thresholds were evaluated solely by pure deterministic rules; no LLM set any amount.",
            subtitle_style,
        )
    )

    doc.build(story)
    return output_path
