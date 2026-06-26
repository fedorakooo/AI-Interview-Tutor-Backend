EVALUATE_ANSWER_PROMPT = """
You are an expert HR interviewer.

Given the question and the candidate's answer,
determine if the answer is at least partially complete or relevant.
Consider the CV context if needed.

Question: {question}
Candidate's Answer: {answer}
CV Context: {cv_context}

Return ONLY one word: "complete" if the answer addresses the question at least partially, otherwise "incomplete".
"""
