# Resume Intelligence Platform V2

Resume Intelligence Platform V2 is an AI-assisted resume evaluation and rewriting tool for software engineers. It parses uploaded resumes, scores ATS readiness, compares the resume against an optional job description, identifies gaps, generates rewrite suggestions, and can export a rewritten resume document.

## What It Does

- Parses PDF, DOCX, and TXT resumes into usable text and structured sections.
- Scores resumes with a deterministic ATS engine.
- Uses multi-agent LLM analysis for resume understanding, job description intelligence, gap analysis, rewrite generation, and optional recruiter simulation.
- Benchmarks candidate positioning with local percentile and career-positioning engines.
- Provides both a Streamlit app and a React/Vite frontend backed by FastAPI.

## Project Structure

```text
.
|-- agents/          # LLM agents for resume, JD, gap, rewrite, and recruiter simulation
|-- backend/         # FastAPI API used by the React frontend
|-- engine/          # ATS scoring, percentile, career positioning, and DOCX generation
|-- frontend/        # React/Vite web UI
|-- memory/          # Local per-user session and style memory helpers
|-- schemas/         # Pydantic input/output contracts for agents
|-- app.py           # Streamlit application
|-- orchestrator.py  # Coordinates parsing, agents, scoring, rewrites, and exports
`-- parser.py        # Resume file parsing helpers
```

## Requirements

- Python 3.11 or newer
- Node.js and npm for the React frontend
- OpenAI API key
- Anthropic API key

Some PDF/OCR flows may also require local OCR tooling such as Tesseract and Poppler, depending on the input file type.

## Environment Variables

Real environment files are intentionally ignored by Git. Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Then fill in your private keys:

```env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Do not commit `.env` or any file containing real API keys.

## Python Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## Run The Streamlit App

```bash
streamlit run app.py
```

The Streamlit app includes resume evaluation, recruiter simulation, gap closing, rewrite review, and DOCX export flows.

## Run The FastAPI Backend

```bash
uvicorn backend.main:app --reload
```

The API exposes endpoints for resume analysis, progress streaming, gap closing, result polling, and DOCX download.

## Run The React Frontend

```bash
cd frontend
npm install
npm run dev
```

By default, the frontend expects the backend to be available locally and uses the Vite development server for the browser UI.

## Testing

```bash
pytest
```

The existing tests focus on agent compliance and gap-session behavior.

## Notes For Contributors

- Keep secrets in `.env` only.
- Commit `.env.example` when adding new configuration keys.
- Avoid committing generated files such as `__pycache__`, `node_modules`, temporary uploads, local exports, and build output.
- The project includes a graphify knowledge graph under `graphify-out/` for codebase navigation.
