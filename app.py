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

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

app = Flask(__name__)

latest_report_path = None


def detect_category(resume_text):

    text = resume_text.lower()

    if any(word in text for word in [
        "python",
        "java",
        "developer",
        "software",
        "programming"
    ]):
        return "Software Developer"

    elif any(word in text for word in [
        "human resource",
        "recruitment",
        "hr",
        "employee"
    ]):
        return "Human Resource"

    elif any(word in text for word in [
        "marketing",
        "sales",
        "digital marketing"
    ]):
        return "Marketing"

    elif any(word in text for word in [
        "data analyst",
        "analytics",
        "sql",
        "power bi"
    ]):
        return "Data Analyst"

    else:
        return "Career Transition Candidate"


@app.route('/', methods=['GET', 'POST'])
def home():

    global latest_report_path

    if request.method == 'POST':

        resume = request.files['resume']
        job_description = request.form['job_description']

        pdf_path = os.path.join(
            'uploads',
            resume.filename
        )

        resume.save(pdf_path)

        reader = PdfReader(pdf_path)

        resume_text = ""

        for page in reader.pages:

            text = page.extract_text()

            if text:
                resume_text += text

        category = detect_category(resume_text)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": f"""
You are a professional ATS Resume Analyzer.

Compare the resume with the job description.

Resume:
{resume_text}

Job Description:
{job_description}

Rules:

1. Give realistic ATS Match Score.
2. Detect missing skills.
3. Give improvement suggestions.
4. Give 5 interview questions.
5. Score should be between 0 and 100.

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

        if score_match:
            score = int(score_match.group(1))

        if score >= 75:
            ats_status = "Highly Recommended"
        elif score >= 50:
            ats_status = "Recommended"
        else:
            ats_status = "Not Recommended For Current Role"

        with open(
            'history.csv',
            'a',
            newline='',
            encoding='utf-8'
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                resume.filename,
                score,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            ])

        cleaned_result = re.sub(
            r'MATCH SCORE:\s*\d+%\s*',
            '',
            ai_result,
            flags=re.IGNORECASE
        )

        report_filename = "resume_analysis_report.pdf"

        latest_report_path = os.path.join(
            "reports",
            report_filename
        )

        doc = SimpleDocTemplate(
            latest_report_path
        )

        styles = getSampleStyleSheet()

        content = [
            Paragraph(
                "AI Resume Analysis Report",
                styles['Title']
            ),
            Spacer(1, 12),
            Paragraph(
                f"Resume Category: {category}",
                styles['Heading2']
            ),
            Spacer(1, 12),
            Paragraph(
                f"ATS Recommendation: {ats_status}",
                styles['Heading2']
            ),
            Spacer(1, 12),
            Paragraph(
                cleaned_result.replace(
                    "\n",
                    "<br/>"
                ),
                styles['BodyText']
            )
        ]

        doc.build(content)

        return render_template(
            'result.html',
            result=cleaned_result,
            score=score,
            category=category,
            ats_status=ats_status
        )

    return render_template('index.html')


@app.route('/history')
def history():

    records = []

    total_analyses = 0
    highest_score = 0
    average_score = 0
    latest_resume = "N/A"

    scores = []

    with open(
        'history.csv',
        'r',
        encoding='utf-8'
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
        'history.html',
        records=records,
        total_analyses=total_analyses,
        highest_score=highest_score,
        average_score=average_score,
        latest_resume=latest_resume
    )


@app.route('/download-report')
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


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)