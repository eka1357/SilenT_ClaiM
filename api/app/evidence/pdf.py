"""ReportLab Evidence Pack PDF generator (docs/PRODUCT.md US4 & docs/SECURITY.md)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
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


def _format_rs_verdict(amount_paise: int) -> str:
    return f"Rs. {round(amount_paise / 100.0):,}"


def _format_day_human(day_iso: str) -> str:
    try:
        d = date.fromisoformat(day_iso)
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        return day_iso


def _format_short_day(day_iso: str) -> str:
    try:
        d = date.fromisoformat(day_iso)
        return f"{d.day} {d.strftime('%b')}"
    except ValueError:
        return day_iso[-5:]


def _format_merchant_title(owner: str, shop_name: str) -> str:
    clean_owner = owner.strip()
    clean_shop = shop_name.strip()
    if not clean_owner or clean_owner.lower() in clean_shop.lower():
        return clean_shop
    lowered_shop = clean_shop[:1].lower() + clean_shop[1:] if clean_shop else "shop"
    return f"{clean_owner}'s {lowered_shop}"


def _strip_mode_tags(text: str) -> str:
    """Remove any '(Live)' or '(Replay)' mode tags from AI summary text."""
    cleaned = re.sub(
        r"\s*\((?:Live|Replay(?:\s+fallback)?)\)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r"\s+\.", ".", cleaned)


def _build_7day_bar_chart(
    recent_days: tuple[tuple[str, int, int], ...],
    event_day_iso: str,
) -> Drawing:
    """Build a 7-day daily totals bar chart (ink bars, event day highlighted in marigold #F0A23B)."""
    width = 172 * mm
    height = 46 * mm
    drawing = Drawing(width, height)

    ink_color = colors.HexColor("#141311")
    marigold_color = colors.HexColor("#F0A23B")
    axis_color = colors.HexColor("#CFC8BC")
    muted_color = colors.HexColor("#5C574F")

    days = recent_days[-7:]
    n_bars = len(days)
    if n_bars == 0:
        return drawing

    base_y = 11 * mm
    max_bar_h = 26 * mm
    drawing.add(Line(0, base_y, width, base_y, strokeColor=axis_color, strokeWidth=0.6))

    max_amt = max((amt for _, _, amt in days), default=0)
    scale_max = max(max_amt, 100)

    slot_w = width / n_bars
    bar_w = min(15 * mm, slot_w * 0.58)

    for idx, (day_s, _n_pay, amt_p) in enumerate(days):
        is_event = day_s == event_day_iso
        bar_color = marigold_color if is_event else ink_color
        x_center = (idx + 0.5) * slot_w
        bar_x = x_center - (bar_w / 2.0)

        raw_h = (amt_p / scale_max) * max_bar_h if amt_p > 0 else 0.0
        # Keep a visible 3 pt marigold/ink bar on zero-income days so the event day stands out.
        bar_h = max(raw_h, 3.0 if is_event else 1.5)

        drawing.add(
            Rect(
                bar_x,
                base_y,
                bar_w,
                bar_h,
                fillColor=bar_color,
                strokeColor=bar_color,
                strokeWidth=0.5,
            )
        )
        drawing.add(
            String(
                x_center,
                base_y + bar_h + 3,
                _format_rs_verdict(amt_p),
                fontName="Helvetica-Bold" if is_event else "Helvetica",
                fontSize=7.5,
                fillColor=ink_color,
                textAnchor="middle",
            )
        )
        drawing.add(
            String(
                x_center,
                base_y - 8,
                _format_short_day(day_s),
                fontName="Helvetica-Bold" if is_event else "Helvetica",
                fontSize=7.5,
                fillColor=ink_color if is_event else muted_color,
                textAnchor="middle",
            )
        )

    return drawing


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
    verdict_style = ParagraphStyle(
        "EvidenceVerdict",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#141311"),
        spaceAfter=6,
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
    verdict_line = (
        f"{_format_merchant_title(data.owner, data.shop_name)} took "
        f"{_format_rs_verdict(data.day_income_paise)} on "
        f"{_format_day_human(data.day_iso)} against a usual "
        f"{_format_rs_verdict(data.baseline_paise)}: "
        f"{data.quorum_dropped} of {data.quorum_total} shops on the street shut, "
        f"{data.rain_mm:.1f} mm of rain."
    )
    provenance_note = f"Synthetic data for demonstration | Rules version: {data.rules_version}" + (
        f" | {data.simulated_label}" if data.simulated_label else ""
    )

    story: list[object] = [
        Paragraph("SILENT CLAIM - EVIDENCE PACK", title_style),
        Paragraph(verdict_line, verdict_style),
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
        clean_summary = _strip_mode_tags(data.summary_text)
        if clean_summary:
            story.append(
                Paragraph(
                    "3. Summary (written by AI from the numbers above; it sets no amount)",
                    section_style,
                )
            )
            story.append(Paragraph(clean_summary, body_style))

    if data.recent_days:
        sec_num = 4 if data.summary_text else 3
        story.append(Paragraph(f"{sec_num}. Recent Daily Payment History (IST)", section_style))
        story.append(_build_7day_bar_chart(data.recent_days, data.day_iso))

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
