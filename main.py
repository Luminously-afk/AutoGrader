"""
GWA & Academic Honors Evaluation — FastAPI Backend
===================================================
Endpoints:
  POST /api/upload-com      → OCR a COM image via Groq Vision LLM
  POST /api/calculate-static → Run the GWA engine on user-edited JSON
"""

import base64
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------
app = FastAPI(title="AutoGrader — GWA & Honors Evaluator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SubjectEntry(BaseModel):
    subject_code: str
    subject_title: str
    units: float | str
    grade: str


class CalculateRequest(BaseModel):
    subjects: list[SubjectEntry]


# ---------------------------------------------------------------------------
# GWA calculation engine (shared)
# ---------------------------------------------------------------------------


def _parse_grade(grade_raw: str | None) -> float | None:
    """Try to parse a numeric grade. Returns None for INC / blank."""
    if grade_raw is None:
        return None
    g = str(grade_raw).strip()
    if g == "" or g.upper() == "INC":
        return None
    try:
        return float(g)
    except ValueError:
        return None


def calculate_gwa(subjects: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Core GWA & honors engine.

    Returns
    -------
    dict with keys: gwa, total_units, academic_standing,
                    requires_manual_input, subjects (annotated)
    """
    requires_manual_input = False
    annotated: list[dict[str, Any]] = []

    included_weighted_sum = 0.0
    included_units_sum = 0.0
    total_units = 0.0
    included_grades: list[float] = []

    for s in subjects:
        code = str(s.get("subject_code", "")).strip()
        title = str(s.get("subject_title", "")).strip()
        units_raw = s.get("units", 0)
        grade_raw = s.get("grade", "")

        # Parse units
        try:
            units = float(units_raw)
        except (ValueError, TypeError):
            units = 0.0

        grade_val = _parse_grade(grade_raw)

        entry: dict[str, Any] = {
            "subject_code": code,
            "subject_title": title,
            "units": units,
            "grade": str(grade_raw).strip() if grade_raw else "",
        }

        total_units += units
        if grade_val is None:
            requires_manual_input = True
            entry["flagged"] = True
        else:
            included_weighted_sum += grade_val * units
            included_units_sum += units
            included_grades.append(grade_val)
            entry["flagged"] = False

        annotated.append(entry)

    # If manual input required, return early
    if requires_manual_input:
        return {
            "gwa": None,
            "total_units": total_units,
            "academic_standing": "Incomplete — manual input required",
            "requires_manual_input": True,
            "subjects": annotated,
        }

    # Compute GWA
    if included_units_sum == 0:
        return {
            "gwa": None,
            "total_units": 0,
            "academic_standing": "No gradable subjects found",
            "requires_manual_input": False,
            "subjects": annotated,
        }

    gwa = round(included_weighted_sum / included_units_sum, 4)
    max_grade = max(included_grades) if included_grades else 0.0

    # Determine academic standing
    if 1.00 <= gwa <= 1.25:
        if max_grade < 1.75:
            standing = "President's Lister"
        elif max_grade == 1.75:
            standing = "Dean's Lister (Demoted from PL due to a 1.75 grade)"
        else:
            # max_grade > 1.75 — disqualified from PL
            if max_grade < 2.00:
                standing = "Dean's Lister (Demoted from PL due to a 1.75 grade)"
            else:
                standing = "No Honors"
    elif 1.26 <= gwa <= 1.50:
        if max_grade < 2.00:
            standing = "Dean's Lister"
        else:
            standing = "No Honors"
    else:
        standing = "No Honors"

    return {
        "gwa": gwa,
        "total_units": total_units,
        "academic_standing": standing,
        "requires_manual_input": False,
        "subjects": annotated,
    }


# ---------------------------------------------------------------------------
# Groq Vision helper
# ---------------------------------------------------------------------------

GROQ_SYSTEM_PROMPT = """You are an expert OCR document parser and structured data extraction AI. Your single task is to analyze photographs or scans of university grade slips (Certificate of Matriculation / COM) and extract the academic course table into a clean, valid JSON object.

INSTRUCTIONS:
1. Scan the image strictly for the table containing the student's enrolled courses and final grades.
2. For every valid subject row found, extract the following 4 fields:
   - "subject_code": The official course identifier (e.g., "IT222").
   - "subject_title": The full descriptive title of the course.
   - "units": The numerical credit units as a float (e.g., 3.0). 
   - "grade": The recorded grade as a STRING. 
     * If a numerical grade is present, output it (e.g., "1.25", "2.00").
     * If the grade is written as "INC", "INCOMPLETE", or the grade cell is physically blank, output the exact string: "INC".
     * If the grade is written as "DRP", "DROPPED", "W", or "WITHDRAWN", output the exact string: "DRP".
3. EXCLUSIONS (Do NOT extract):
   - Ignore all institutional headers, university logos, and registrar boilerplate.
   - Ignore all personal student metadata (Student Name, Student ID, Course/Year, home address).
   - Ignore bottom tally rows (e.g., "TOTAL UNITS: 21", "GPA: 1.25"). Only capture individual subject rows.

OUTPUT SPECIFICATION:
Return ONLY a valid JSON object matching the exact schema below. Do not wrap the JSON in markdown formatting (no ```json tags), do not include introductory commentary, and do not add conversational text.

{
  "subjects": [
    {
      "subject_code": "string",
      "subject_title": "string",
      "units": 0.0,
      "grade": "string"
    }
  ]
}"""


async def extract_subjects_from_image(image_bytes: bytes, content_type: str) -> list[dict]:
    """Call Groq Vision LLM to extract subjects from a COM image."""
    api_key = os.getenv("GROQ_API_KEY")
    print(api_key)

    from groq import Groq

    client = Groq(api_key=api_key)

    # Determine media type
    media_map = {
        "image/png": "image/png",
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/webp": "image/webp",
    }
    media_type = media_map.get(content_type, "image/jpeg")
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": "",
                        },
                    ],
                    
                },
            ],
            temperature=0,
            max_completion_tokens=1024,
            top_p=0.1,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(e)}")

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Groq returned invalid JSON.")

    subjects = data.get("subjects", [])
    # Sanitise each entry
    cleaned = []
    for s in subjects:
        cleaned.append({
            "subject_code": str(s.get("subject_code", "UNKNOWN")),
            "subject_title": str(s.get("subject_title", "UNKNOWN")),
            "units": float(s.get("units", 0)),
            "grade": str(s.get("grade", "INC")),
        })
    return cleaned


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload-com")
async def upload_com(file: UploadFile = File(...)):
    """Upload a COM image → OCR via Groq → return parsed subjects + GWA."""
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, and WebP images are accepted.")

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:  # 20 MB cap
        raise HTTPException(status_code=400, detail="Image too large (max 20 MB).")

    subjects = await extract_subjects_from_image(image_bytes, file.content_type)
    result = calculate_gwa([s for s in subjects])
    return result


@app.post("/api/calculate-static")
async def calculate_static(req: CalculateRequest):
    """Run the GWA engine on user-edited subjects (no Groq call)."""
    subjects_dicts = [s.model_dump() for s in req.subjects]
    result = calculate_gwa(subjects_dicts)
    return result


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# Mount static assets (CSS, JS, images if any)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
