from fpdf import FPDF
from datetime import datetime


class PDFReport(FPDF):
    """Custom PDF class for Med Fact Check reports."""

    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(59, 130, 246)  # Blue
        self.cell(0, 10, 'Med Fact Check - Verification Report', 0, 0, 'C')
        self.ln(5)
        self.set_draw_color(59, 130, 246)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()} | Med Fact Check Report', 0, 0, 'C')


def safe_text(text):
    """Sanitize text for PDF output, handling Unicode gracefully."""
    if not isinstance(text, str):
        text = str(text)
    # Remove null bytes and control characters that can corrupt PDFs
    text = text.replace('\x00', '')
    # Replace common Unicode characters with Latin-1 equivalents
    replacements = {
        '\u2018': "'", '\u2019': "'",   # Smart quotes
        '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--',  # Em/en dash
        '\u2026': '...',                # Ellipsis
        '\u00a0': ' ',                  # Non-breaking space
        '\u2022': '-',                  # Bullet
        '\u2192': '->',                # Arrow
        '\u2264': '<=', '\u2265': '>=', # Math symbols
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode to latin-1 with 'replace' for any remaining unsupported chars
    return text.encode('latin-1', 'replace').decode('latin-1')


def generate_fact_check_pdf(claim, final_verdict, subclaims):
    """
    Generates a PDF report for a fact check.
    Returns the PDF as a bytes object ready for st.download_button.
    """
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Date
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(128, 128, 128)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.cell(0, 10, f'Generated on: {date_str}', 0, 1, 'R')
    pdf.ln(5)

    # === Original Claim ===
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, 'Original Claim', 0, 1, 'L')

    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 7, safe_text(claim))
    pdf.ln(8)

    # === Final Verdict ===
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, 'Final Verdict', 0, 1, 'L')

    label = final_verdict.get('label', 'UNKNOWN').upper()
    conf = final_verdict.get('confidence', 0.0)
    if isinstance(conf, str):
        try:
            conf = float(conf)
        except ValueError:
            conf = 0.0

    # Color code verdict
    if label == "SUPPORTED":
        pdf.set_text_color(16, 185, 129)
    elif label == "REFUTED":
        pdf.set_text_color(239, 68, 68)
    else:
        pdf.set_text_color(245, 158, 11)

    pdf.set_font('Helvetica', 'B', 16)
    if conf <= 1.0:
        conf_display = f'{int(conf * 100)}%'
    else:
        conf_display = f'{int(conf)}%'
    pdf.cell(0, 12, safe_text(f'{label}  ({conf_display} confidence)'), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)

    # Justification
    justification = final_verdict.get('justification', '')
    if justification:
        pdf.ln(3)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, 'Justification:', 0, 1, 'L')
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(0, 6, safe_text(justification))

    pdf.ln(10)

    # === Subclaim Analysis ===
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, 'Subclaim Analysis', 0, 1, 'L')
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    for i, sc in enumerate(subclaims, 1):
        sc_text = sc.get('subclaim', 'Unknown Subclaim')
        sc_label = sc.get('label', 'UNKNOWN').upper()
        sc_conf = sc.get('confidence', 0.0)
        if isinstance(sc_conf, str):
            try:
                sc_conf = float(sc_conf)
            except ValueError:
                sc_conf = 0.0
        sc_justification = sc.get('justification', sc.get('selection_reasoning', 'No justification provided.'))

        # Subclaim header
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 7, safe_text(f'Subclaim {i}: {sc_text}'))

        # Verdict badge
        pdf.set_x(10)
        if sc_label == "SUPPORTED":
            pdf.set_text_color(16, 185, 129)
        elif sc_label == "REFUTED":
            pdf.set_text_color(239, 68, 68)
        else:
            pdf.set_text_color(245, 158, 11)

        pdf.set_font('Helvetica', 'B', 10)
        if sc_conf <= 1.0:
            sc_conf_display = f'{int(sc_conf * 100)}%'
        else:
            sc_conf_display = f'{int(sc_conf)}%'
        pdf.cell(0, 7, safe_text(f'Verdict: {sc_label} ({sc_conf_display} confidence)'), 0, 1, 'L')

        # Justification
        pdf.set_x(10)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(0, 6, safe_text(f'Justification: {sc_justification}'))
        pdf.ln(3)

        # Evidence Documents (plain text only, no write_html)
        evidence = sc.get("retrieved_chunks", [])
        if evidence:
            pdf.set_x(10)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(59, 130, 246)
            pdf.cell(0, 6, 'Evidence Sources:', 0, 1, 'L')

            for chunk in evidence[:5]:
                if isinstance(chunk, dict):
                    text = chunk.get("text", "")
                    meta = chunk.get("metadata", {})
                    source_title = (meta.get("title") or meta.get("id") or
                                    chunk.get("source") or "Document")
                else:
                    text = str(chunk)
                    source_title = "Document"

                pdf.set_x(15)
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(30, 41, 59)
                pdf.cell(0, 5, safe_text(source_title), 0, 1, 'L')

                pdf.set_x(15)
                pdf.set_font('Helvetica', 'I', 9)
                pdf.set_text_color(100, 116, 139)
                # Truncate very long evidence texts to prevent page overflow
                display_text = text[:500] + ('...' if len(text) > 500 else '')
                pdf.multi_cell(0, 5, safe_text(display_text))
                pdf.ln(2)

        # Separator between subclaims
        pdf.set_draw_color(226, 232, 240)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(5)

    # Return as bytes - pdf.output() in fpdf2 returns bytearray
    return bytes(pdf.output())
