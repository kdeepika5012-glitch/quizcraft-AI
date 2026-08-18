import os
import json
import re

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore

from google import genai


# -----------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------
load_dotenv()

app = Flask(__name__)


# -----------------------------------
# GEMINI API
# -----------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


# -----------------------------------
# FIREBASE CONNECTION
# -----------------------------------

# Render Secret File path
RENDER_FIREBASE_PATH = "/etc/secrets/firebase-key.json"

# Local computer path
LOCAL_FIREBASE_PATH = "firebase-key.json"

if os.path.exists(RENDER_FIREBASE_PATH):
    firebase_path = RENDER_FIREBASE_PATH
elif os.path.exists(LOCAL_FIREBASE_PATH):
    firebase_path = LOCAL_FIREBASE_PATH
else:
    firebase_path = None


db = None

try:
    if firebase_path:
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_path)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("Firebase connected successfully")

    else:
        print("WARNING: firebase-key.json not found")

except Exception as e:
    print("Firebase connection error:", e)


# -----------------------------------
# CODING KEYWORDS
# -----------------------------------

CODING_KEYWORDS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "c",
    "c++",
    "cpp",
    "c#",
    "csharp",
    "php",
    "ruby",
    "go",
    "golang",
    "rust",
    "kotlin",
    "swift",

    "html",
    "css",
    "react",
    "reactjs",
    "node",
    "nodejs",
    "express",
    "angular",
    "vue",
    "nextjs",
    "next.js",

    "flask",
    "django",
    "spring",
    "spring boot",

    "sql",
    "mysql",
    "postgresql",
    "postgres",
    "mongodb",
    "database",
    "dbms",

    "dsa",
    "data structures",
    "data structure",
    "algorithms",
    "algorithm",

    "oops",
    "oop",
    "object oriented programming",

    "operating system",
    "operating systems",
    "os",

    "computer networks",
    "networking",

    "api",
    "rest api",
    "rest",

    "git",
    "github",
    "docker",
    "cloud",
    "aws",
    "azure",

    "machine learning",
    "artificial intelligence",
    "ai",

    "cyber security",
    "cybersecurity",

    "linux",

    "computer science",
    "programming",
    "coding"
]


# -----------------------------------
# CHECK CODING TOPIC
# -----------------------------------

def is_coding_topic(text):
    text = text.lower()

    for keyword in CODING_KEYWORDS:
        if keyword in text:
            return True

    return False


# -----------------------------------
# QUESTION COUNT
# -----------------------------------

def get_question_count(text):

    numbers = re.findall(r"\d+", text)

    if numbers:
        count = int(numbers[0])

        if count < 1:
            return 5

        if count > 100:
            return 100

        return count

    return 5


# -----------------------------------
# DIFFICULTY
# -----------------------------------

def get_difficulty(text):

    text = text.lower()

    if any(word in text for word in [
        "hard",
        "complex",
        "difficult",
        "advanced"
    ]):
        return "Hard"

    if "easy" in text:
        return "Easy"

    if "medium" in text:
        return "Medium"

    return "Mixed"


# -----------------------------------
# GENERATE AI QUIZ
# -----------------------------------

def generate_ai_quiz(user_request, count, difficulty):

    if not client:
        return None

    prompt = f"""
You are an AI quiz generator.

User request:
{user_request}

Difficulty:
{difficulty}

Number of questions:
{count}

IMPORTANT RULES:

1. ONLY generate quizzes about:
   - Programming
   - Coding
   - Software Development
   - Computer Science
   - Databases
   - Web Development
   - Technical subjects

2. Generate EXACTLY {count} questions.

3. Every question must be directly related
   to the requested coding/technical topic.

4. Include a mixture of:
   - Conceptual questions
   - Practical questions
   - Debugging questions
   - Code-output questions
   - Problem-solving questions

5. If difficulty is Hard, questions must genuinely
   be challenging.

6. Every question must have EXACTLY 4 options.

7. There must be EXACTLY ONE correct answer.

8. Randomize the position of the correct answer.
   Do NOT always put the correct answer first.

9. Do NOT repeat questions.

10. Questions must be technically accurate.

11. Return ONLY valid JSON.

Use exactly this format:

{{
    "questions": [
        {{
            "question": "Question text",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "answer": "Correct option"
        }}
    ]
}}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # Remove markdown JSON fences if Gemini adds them
        text = re.sub(r"```json", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        data = json.loads(text)

        questions = data.get("questions", [])

        valid_questions = []

        for q in questions:

            if not isinstance(q, dict):
                continue

            question = q.get("question")
            options = q.get("options")
            answer = q.get("answer")

            if not question:
                continue

            if not isinstance(options, list):
                continue

            if len(options) != 4:
                continue

            if not answer:
                continue

            if answer not in options:
                continue

            valid_questions.append({
                "question": question,
                "options": options,
                "answer": answer
            })

        return valid_questions

    except Exception as e:

        print("Gemini error:", e)

        return None


# -----------------------------------
# HOME PAGE
# -----------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------------
# GENERATE QUIZ API
# -----------------------------------

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "No data received"
            }), 400

        subject = data.get("subject", "").strip()

        if not subject:
            return jsonify({
                "error": "Please enter a coding topic."
            }), 400

        # Only coding topics allowed
        if not is_coding_topic(subject):

            return jsonify({
                "error": "I don't know. Please ask about programming or other coding-related topics."
            }), 400

        count = get_question_count(subject)

        difficulty = get_difficulty(subject)

        questions = generate_ai_quiz(
            subject,
            count,
            difficulty
        )

        if not questions:

            return jsonify({
                "error": "Quiz generation failed. Please try again."
            }), 500


        # -----------------------------------
        # SAVE QUIZ TO FIREBASE
        # -----------------------------------

        if db:

            try:

                db.collection("quizzes").add({
                    "subject": subject,
                    "difficulty": difficulty,
                    "question_count": len(questions),
                    "questions": questions
                })

                print("Quiz saved to Firebase")

            except Exception as firebase_error:

                print(
                    "Firebase save error:",
                    firebase_error
                )


        return jsonify({
            "questions": questions,
            "count": len(questions),
            "difficulty": difficulty
        })


    except Exception as e:

        print("Server error:", e)

        return jsonify({
            "error": "Something went wrong."
        }), 500


# -----------------------------------
# RUN APP
# -----------------------------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )