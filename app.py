import os
import re
import csv
from datetime import datetime

from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader
from groq import Groq
from dotenv import load_dotenv

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

if not os.path.exists("history.csv"):
    with open("history.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Resume Name", "Match Score", "Date Time"])

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

latest_report_path = None


@app.route("/", methods=["GET", "POST"])
def home():

    global latest_report_path

    if request.method == "POST":

        resume = request.files["resume"]
        job_description = request.form["job_description"]
        if resume.filename == "":
            return "Please select a resume."
        if not resume.filename.lower().endswith(".pdf"):
            return "Only PDF files are allowed."

        pdf_path = os.path.join(
            UPLOAD_FOLDER,
            resume.filename
        )

        resume.save(pdf_path)

        reader = PdfReader(pdf_path)

        resume_text = ""

        for page in reader.pages:
            text = page.extract_text()

            if text:
                resume_text += text

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": f"""
You are an ATS Resume Screening System.

Analyze the resume against the job description.

Resume:
{resume_text}

Job Description:
{job_description}

Return EXACTLY:

MATCH SCORE:
<number>%

MISSING SKILLS:
- skill

IMPROVEMENT SUGGESTIONS:
- suggestion

INTERVIEW QUESTIONS:
1. question
2. question
3. question
4. question
5. question
"""
                }
            ]
        )

        ai_result = response.choices[0].message.content

        score_match = re.search(r'(\d+)%', ai_result)

        score = 0
        if score >= 90:
            grade = "A+"
        elif score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "B+"
        elif score >= 60:
            grade = "B"
        elif score >= 50:
            grade = "C"
        else:
            grade = "Needs Improvement"
        if score >= 75:
                ats_status = "Highly Recommended"
        elif score >= 50:
            ats_status = "Recommended"
        else:
            ats_status = "Not Recommended For Current Role"

        if score_match:
            score = int(score_match.group(1))

        with open(
            "history.csv",
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                resume.filename,
                score,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])

        cleaned_result = re.sub(
            r'MATCH SCORE:\s*\d+%\s*',
            '',
            ai_result,
            flags=re.IGNORECASE
        )

        latest_report_path = os.path.join(
            REPORT_FOLDER,
            "resume_analysis_report.pdf"
        )

        doc = SimpleDocTemplate(latest_report_path)

        styles = getSampleStyleSheet()

        content = [
            Paragraph(
                "AI Resume Analysis Report",
                styles['Title']
            ),
            Spacer(1, 12),
            Paragraph(
                cleaned_result.replace("\n", "<br/>"),
                styles['BodyText']
            )
        ]

        doc.build(content)

        return render_template(
            "result.html",
            result=cleaned_result,
            score=score,
            ats_status=ats_status,
            grade=grade
        )

    return render_template("index.html")


@app.route("/history")
def history():

    records = []

    total_analyses = 0
    highest_score = 0
    average_score = 0
    latest_resume = "N/A"

    scores = []

    with open(
        "history.csv",
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.reader(file)

        next(reader)

        for row in reader:

            records.append(row)

            total_analyses += 1

            try:

                score = int(row[1])

                scores.append(score)

                if score > highest_score:
                    highest_score = score

            except:
                pass

        if records:
            latest_resume = records[-1][0]

        if scores:
            average_score = round(
                sum(scores) / len(scores)
            )

    return render_template(
        "history.html",
        records=records,
        total_analyses=total_analyses,
        highest_score=highest_score,
        average_score=average_score,
        latest_resume=latest_resume
    )


@app.route("/download-report")
def download_report():

    global latest_report_path

    if latest_report_path and os.path.exists(
        latest_report_path
    ):

        return send_file(
            latest_report_path,
            as_attachment=True
        )

    return "No report available."

@app.route("/download-history")
def download_history():

    return send_file(
        "history.csv",
        as_attachment=True
    )
if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )