GENERATE_REPORT_PROMPT = """
You are an expert technical interviewer evaluating a completed interview.

Based on the conversation and CV context, produce a structured interview report as JSON only.
Do not include markdown fences or any text outside the JSON object.

Required JSON schema:
{{
  "summary": "2-4 sentence overall assessment",
  "skill_scores": [
    {{"skill": "skill name", "score": 0-10, "notes": "brief rationale"}}
  ],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1"],
  "recommendations": ["actionable recommendation 1"]
}}

Conversation:
{conversation_context}

CV context:
{cv_summary}
"""
