# AutoGrader: GWA & Academic Honors Evaluator

AutoGrader is a fast, web-based tool designed to automate the extraction, calculation, and evaluation of student grades, General Weighted Average (GWA), and academic honors eligibility (President's Lister / Dean's Lister).

---

## 💡 The Motivation

This project was born out of a real struggle faced by students in our school. **We do not have a student portal** to view, track, or automatically calculate our grades. 

In the past, students had to manually calculate their GWA or create a brand-new Google Sheet every single semester. Because the curriculum, subjects, and unit distributions change continuously, managing these sheets was tedious, error-prone, and frustrating. 

**AutoGrader** solves this by letting students simply snap a photo or upload a screenshot of their **Certificate of Matriculation (COM)** or grade slip. The system automatically reads the course details, computes the GWA, and checks honors eligibility in seconds.

---

## ✨ Features

- **AI-Powered COM Parsing (OCR):** Upload a photo, scan, or screenshot of your Certificate of Matriculation (COM). The backend utilizes **Groq Vision LLM** to perform structured OCR and extract subject codes, titles, units, and grades automatically.
- **Dynamic GWA Engine:** Computes the exact General Weighted Average (GWA) based on course units and grades.
- **Honors Eligibility Predictor:** Automatically determines if you qualify for academic honors:
  - **President's Lister (PL):** GWA of `1.00` to `1.25`, with no grade of `1.75` or higher.
  - **Dean's Lister (DL):** GWA of `1.26` to `1.50`, with no grade of `2.00` or higher (or demoted from PL due to a `1.75` grade).
- **Interactive Editing & Correction:** OCR isn't always perfect, or you might want to simulate future grades. AutoGrader features an interactive grid allowing you to add, edit, or delete subjects, units, and grades, then recalculate instantly.
- **Modern UI/UX:** Responsive, single-page application built with clean, modern components.

---

## 🛠️ Technology Stack

- **Backend:** FastAPI (Python), Uvicorn, Pydantic, Groq Python SDK, Python-Dotenv
- **Frontend:** Vanilla HTML, CSS, JavaScript (served directly by the FastAPI backend)
- **AI/OCR Model:** `meta-llama/llama-4-scout-17b-16e-instruct` via Groq API

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- A Groq API Key (get one from [Groq Console](https://console.groq.com/))

### Installation

1. **Clone or download** this repository.
2. Navigate to the project root directory:
   ```bash
   cd AutoGrader
   ```
3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Environment Variables:**
   Create a `.env` file in the root directory (you can copy [.env.example](file:///.env.example)):
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

### Running the Application

1. **Start the FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```
2. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:8000`.

---

## 📜 Honors Policy Logic

AutoGrader evaluates student status based on the following academic guidelines:

| GWA Range | Grade Restriction | Standing / Award |
|---|---|---|
| **1.00 - 1.25** | No grade $\ge 1.75$ | **President's Lister** |
| **1.00 - 1.25** | Max grade $= 1.75$ | **Dean's Lister** (Demoted from PL) |
| **1.26 - 1.50** | No grade $\ge 2.00$ | **Dean's Lister** |
| Any other GWA | Grade $\ge 2.00$ or GWA $> 1.50$ | **No Honors** |

*Note: Incomplete ("INC") grades will flag the subject and prompt you for manual input before final GWA & Honors calculations can be completed.*
