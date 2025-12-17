from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_summary_pdf(failures):
    filename = "Provar_XML_Failure_Summary.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Provar AI - XML Failure Summary Report")
    y -= 40

    for f in failures:
        if y < 200:
            c.showPage()
            y = height - 50

        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"Testcase: {f['testcase']}")
        y -= 20

        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Class: {f['classname']}")
        y -= 15
        c.drawString(40, y, f"Execution Time: {f['time']} sec")
        y -= 25

        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Error Message:")
        y -= 15
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"{f['message']}")
        y -= 25

        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Details:")
        y -= 15

        c.setFont("Helvetica", 10)
        for line in f["details"].split("\n"):
            c.drawString(40, y, line.strip())
            y -= 12

        y -= 30

    c.save()
    return filename
