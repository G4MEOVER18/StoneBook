@echo off
REM Fügt alle Bilder des Objekts 043 in das DOCX-Dokument ein
set DOCX=Analyse_Objekt_043.docx
set OUT=Analyse_Objekt_043_final.docx

python - <<END
import os
from docx import Document
from docx.shared import Inches

doc = Document(os.environ['DOCX'])

doc.add_heading("Fotodokumentation", level=1)

for f in os.listdir("."):
    if f.lower().endswith((".jpg", ".jpeg", ".png")):
        try:
            doc.add_picture(f, width=Inches(3))
            doc.add_paragraph(f"Bild: {f}")
        except Exception as e:
            print("Fehler bei", f, ":", e)

doc.save(os.environ['OUT'])
print("Fertig: Bilder eingefügt in", os.environ['OUT'])
END

pause
