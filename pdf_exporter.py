from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import datetime
import os

def export_summary_pdf(df):
    """
    Export Jira summary + failures into a professional PDF file.
    """

    # PDF output path
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"Provar_AI_Summary_{timestamp}.pdf"
    pdf_path = os.path.join(os.getcwd(), pdf_filename)

    # PDF document
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # ---------------------------
    # TITLE
    # ---------------------------
    title = "<para align='center'><b><font size=16>Provar AI Failure Summary Report</font></b></para>"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 20))

    # ---------------------------
    # METADATA
    # ---------------------------
    meta_text = f"""
    <b>Generated On:</b> {datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")}<br/>
    <b>Total Failures:</b> {len(df)}<br/>
    """
    story.append(Paragraph(meta_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # ---------------------------
    # FAILURE TABLE
    # ---------------------------
    story.append(Paragraph("<b>Failure Summary</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    table_data = [["Testcase", "Error Message"]]

    for _, row in df.iterrows():
        table_data.append([row["testcase"], row["error"]])

    table = Table(table_data, colWidths=[200, 350])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.black),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 12),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("BACKGROUND", (0,1), (-1,-1), colors.whitesmoke),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey)
    ]))

    story.append(table)
    story.append(Spacer(1, 20))

    # ---------------------------
    # AI ROOT CAUSE SECTION
    # ---------------------------
    story.append(Paragraph("<b>AI Generated Jira Analysis</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    for i, row in df.iterrows():
        text = f"""
        <b>{i+1}. Testcase:</b> {row["testcase"]}<br/>
        <b>Error:</b> {row["error"]}<br/>
        <b>AI Suggestion:</b><br/> {row["jira"]}<br/><br/>
        """
        story.append(Paragraph(text, styles["Normal"]))
        story.append(Spacer(1, 15))

    # Build PDF
    doc.build(story)

    return pdf_path
