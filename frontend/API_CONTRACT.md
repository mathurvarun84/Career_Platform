# RIP V2 — API Contract (source of truth for frontend)

## Base URL
Development: http://localhost:8000
Env var: VITE_API_URL

## Endpoints

### POST /api/analyze
Request: multipart/form-data
  - resume: File (PDF | DOCX | TXT, max 5MB)
  - jd_text: string (optional, empty string if not provided)
  - run_sim: boolean (default false)

Response 200:
  { "job_id": string }   // UUID v4

Response 422: validation error (file too large, wrong type)
Response 500: pipeline error

### GET /api/stream/{job_id}
Protocol: Server-Sent Events (text/event-stream)
Each event data field is JSON:

  // Progress events (status: "running")
  { "step": 1, "label": "Reading your resume...", "pct": 10, "status": "running" }
  { "step": 1, "label": "Resume parsed successfully", "pct": 30, "status": "running" }
  { "step": 2, "label": "Analyzing gaps against JD...", "pct": 45, "status": "running" }
  { "step": 2, "label": "Gap analysis complete", "pct": 65, "status": "running" }
  { "step": 3, "label": "Rewriting changed sections...", "pct": 75, "status": "running" }
  { "step": 3, "label": "Resume rewritten successfully", "pct": 95, "status": "running" }

  // Terminal events
  { "status": "complete", "pct": 100 }
  { "status": "error", "error": string }

### GET /api/result/{job_id}
Response 200: AnalysisResult (see Types section below)
Response 404: job not found or not complete yet

### POST /api/gap-close
Request JSON:
  {
    "job_id": string,
    "accepted_sections": { [section_name: string]: "balanced" | "aggressive" | "top_1_percent" },
    "user_id": string
  }

Response 200:
  { "docx_id": string }

### GET /api/download/{docx_id}
Response 200: application/octet-stream (binary .docx file)
Content-Disposition: attachment; filename="resume_improved.docx"

### GET /api/history
Query params: user_id (string)
Response 200:
  {
    "runs": [
      {
        "run_id": string,
        "timestamp": string (ISO 8601),
        "ats_score": number,
        "jd_match": number | null,
        "percentile": number | null
      }
    ]
  }

## TYPES section (canonical shapes from orchestrator.py return dict):

AnalysisResult = {
  job_id: string,
  ats: {
    score: number,                        // 0-100
    breakdown: {
      keyword_match: number,              // 0-25
      formatting: number,                 // 0-25
      readability: number,                // 0-25
      impact_metrics: number              // 0-25
    },
    ats_issues: string[]
  },
  resume: {
    experience_years: number,
    seniority: "junior" | "mid" | "senior" | "staff",
    tech_stack: string[],
    domains: string[],
    has_metrics: boolean,
    has_summary: boolean,
    sections_present: string[],
    resume_sections: { [section_name: string]: { full_text: string } }
  },
  gap: {
    jd_match_score_before: number | null,
    section_gaps: SectionGap[],
    missing_keywords: string[],
    priority_fixes: string[],
    changes: ActionableChange[]         // from evaluate mode
  } | null,
  rewrites: {
    [section_name: string]: {
      balanced: string,
      aggressive: string,
      top_1_percent: string
    }
  } | null,
  sim: {
    personas: PersonaVerdict[],         // always 10 items
    shortlist_rate: number,             // 0.0 to 1.0
    consensus_strengths: string[],
    consensus_weaknesses: string[],
    most_critical_fix: string
  } | null,
  percentile: number | null,
  positioning: {
    positioning_line: string,
    delta_line: string,
    cta_line: string,
    fix_items: string[]
  } | null
}

SectionGap = {
  section: string,
  needs_change: boolean,
  gap_reason: string,
  missing_keywords: string[],
  rewrite_instruction: string,
  present_in_resume: boolean,
  sub_changes: SubLocationChange[]
}

SubLocationChange = {
  sub_id: string,
  sub_label: string,
  needs_change: boolean,
  gap_reason: string,
  rewrite_instruction: string,
  missing_keywords: string[]
}

ActionableChange = {
  change_id: number,
  location: { section: string, sub_location: string },
  change_type: "rewrite_bullet" | "add_keyword" | "rewrite_section" | "add_section" | "remove_content" | "strengthen_metric",
  priority: "critical" | "high" | "medium",
  why: string,
  original_text: string,
  suggested_text: string,
  keywords_added: string[]
}

PersonaVerdict = {
  persona: string,
  first_impression: string,
  noticed: string[],
  ignored: string[],
  rejection_reason: string,
  shortlist_decision: boolean
}
