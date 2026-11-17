# INTERVIEWIQ

INTERVIEWIQ is a local Streamlit app for AI-assisted interview practice. It uses a single Groq chat model with prompt templates, saves sessions in SQLite, validates model evaluations and reports, and generates downloadable PDF reports.

## Requirements

- Python 3.11 or newer
- A Groq API key for live question generation, answer evaluations, and personalized reports
- Without a key, the app offers explicitly labeled Demo Mode practice

## Install and run (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your Groq key to `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
INTERVIEWIQ_DATABASE_PATH=data/interviewiq.sqlite3
GROQ_REQUEST_TIMEOUT=45
GROQ_MAX_RETRIES=2
```

Keep `.env` private; it is ignored by Git. Then start the app:

```powershell
streamlit run app.py
```

## Use the app

1. Create a profile and choose one of the supported roles.
2. Set experience level, difficulty, question count, interview type, and optional company focus.
3. Record your self-reported confidence before practice.
4. Answer or skip questions; live sessions receive validated, answer-specific feedback.
5. After a completed session, record self-reported confidence again and complete the usability questionnaire.
6. Open the saved report for charts, feedback, a personalized learning plan, and a PDF download.
7. Use **History** to revisit or delete sessions, and **Settings & export** to download anonymous research CSVs.

Demo Mode uses labeled sample questions and never creates LLM evaluations or contributes to real performance metrics. Demo sessions are marked in history and excluded from research exports.

## Data and research exports

SQLite data is stored locally at `data/interviewiq.sqlite3` by default. Override the location with `INTERVIEWIQ_DATABASE_PATH`. Session deletion also removes dependent answers, evaluations, reports, and survey responses.

The confidence and SUS CSVs contain random participant/session identifiers shared between the two downloads in the current Streamlit session. They omit profile names and database IDs, and include completed real sessions only. The identifiers may be regenerated in a later app session.

The usability questionnaire uses paraphrased item wording with the standard SUS scoring formula and 68 reference benchmark. For validated research comparisons, use the authorized original instrument wording; paraphrased items may affect comparability.

## Tests

Run the automated suite from the project directory:

```powershell
python -m pytest -q
```
