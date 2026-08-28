# Apply-Buddy

A local job-application assistant that scrapes LinkedIn job postings, scores their fit against your CV using an LLM, tailors your LaTeX CV per role, generates cover letters, and tracks application status.

## Setup

### Prerequisites

- **Python 3.10+**
- **Google Chrome** (for the scraper)
- **LaTeX distribution** (MiKTeX or TeX Live) — optional, for auto-compiling tailored CVs
- **Pandoc** — optional, for converting cover letters to .docx/.pdf
- **wkhtmltopdf** (or a LaTeX engine) — optional, Pandoc needs one of these to produce cover-letter PDFs

### Install

```bash
pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env` and set your LLM config:
   ```
   LLM_PROVIDER=openai
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_API_KEY=sk-dummy
   LLM_MODEL=llama3.2
   ```
   - For **OpenAI**: `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://api.openai.com/v1`
   - For **Databricks**: `LLM_PROVIDER=databricks`, `LLM_BASE_URL=<your-serving-endpoint>` (e.g. `https://adb-<workspace-id>.18.azuredatabricks.net/serving-endpoints`), `LLM_MODEL=<deployed-endpoint-name>`

2. (Optional) Copy `config.example.yaml` to `config.yaml` and customize paths, thresholds, and the list of available LLM models.

3. Place your master CV `.tex` file at `data/cv/cv.tex` (or configure the path in Settings).

### LinkedIn Login (First Time)

```bash
python -m linkedin_jobs_scraper login --chrome-user-data-dir ./chrome-profile
```

Log in with your LinkedIn credentials and **tick "Keep me logged in"**. After that, the scraper reuses this profile.

### Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 in your browser.

## Usage

1. **Settings** → Add search queries (keywords, locations, filters).
2. **Jobs** → Click **Fetch Jobs** to scrape LinkedIn. Jobs whose title doesn't match any query's significant keywords are automatically filtered out.
3. **Score Fit** → Batch-score all new jobs against your CV, or score individual jobs from the job detail page.
4. Per job: **Tailor CV**, **Write Cover Letter**, mark as **Applied**.
5. **Applied** board → Track status (interview, offer, rejected, etc.).

### Customizing Prompts & Models

In **Settings → Prompts & Models**, you can:

- **Edit prompts** — Customize the LLM instructions for Score Fit, CV Tailor, and Cover Letter generation. Each prompt uses template variables like `{job_title}`, `{company}`, `{description}`, `{cv_plain}`, etc.
- **Select a model per action** — Override the default LLM model for each prompt type independently. The available models list is configured in `config.yaml` via `llm_available_models`.
- **Reset to default** — Restore any prompt to its original template with one click.

## Notes

- LinkedIn scraping is best-effort and against LinkedIn ToS. Use at low volume for personal use.
- CV tailoring and cover letters require an LLM endpoint (OpenAI, Ollama, LM Studio, etc.).
- LaTeX and Pandoc are optional; the app saves raw `.tex` and `.md` files even if compilation is unavailable.