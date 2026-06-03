import os
from fpdf import FPDF
from datetime import datetime

class PDFReport(FPDF):
    def header(self):
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        # Move to the right
        self.cell(80)
        # Title
        self.cell(30, 10, 'Med Fact Check - Verification Report', 0, 0, 'C')
        # Line break
        self.ln(20)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def safe_text(text):
    if not isinstance(text, str):
        text = str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_fact_check_pdf(claim, final_verdict, subclaims):
    """
    Generates a PDF report for a fact check.
    Returns the PDF as a bytes object.
    """
    pdf = PDFReport()
    pdf.add_page()
    
    # Date
    pdf.set_font('Arial', 'I', 10)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.cell(0, 10, f'Generated on: {date_str}', 0, 1, 'R')
    pdf.ln(5)

    # Original Claim
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Original Claim:', 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 8, safe_text(claim))
    pdf.ln(5)

    # Final Verdict
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Final Verdict:', 0, 1, 'L')
    label = final_verdict.get('label', 'UNKNOWN').upper()
    conf = final_verdict.get('confidence', 0.0)
    
    # Color code verdict
    if label == "SUPPORTED":
        pdf.set_text_color(0, 128, 0)
    elif label == "REFUTED":
        pdf.set_text_color(200, 0, 0)
    else:
        pdf.set_text_color(100, 100, 100)
        
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, safe_text(f'{label} (Confidence: {conf:.2f})'), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Subclaims
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Subclaim Analysis:', 0, 1, 'L')
    pdf.ln(2)

    for i, sc in enumerate(subclaims, 1):
        sc_text = sc.get('subclaim', 'Unknown Subclaim')
        sc_label = sc.get('label', 'UNKNOWN').upper()
        sc_conf = sc.get('confidence', 0.0)
        justification = sc.get('justification', 'No justification provided.')
        
        # Reset X explicitly to avoid "Not enough horizontal space" if multi_cell leaves cursor at right margin
        pdf.set_x(10)
        pdf.set_font('Arial', 'B', 11)
        pdf.multi_cell(0, 8, safe_text(f'Subclaim {i}: {sc_text}'))
        
        pdf.set_x(10)
        pdf.set_font('Arial', 'I', 10)
        pdf.multi_cell(0, 8, safe_text(f'Verdict: {sc_label} (Conf: {sc_conf:.2f})'))
        
        pdf.set_x(10)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, safe_text(f'Justification: {justification}'))
        pdf.ln(5)

    # Return as bytes
    return bytes(pdf.output())
