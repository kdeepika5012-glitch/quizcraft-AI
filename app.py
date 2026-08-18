from flask import Flask, render_template, request, jsonify

import firebase_admin
from firebase_admin import credentials, firestore

import os
import json
import re
import random
import time

from dotenv import load_dotenv
from google import genai


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found.")


# =========================================================
# GEMINI
# =========================================================

client = None

if GEMINI_API_KEY:
    client = genai.Client(
        api_key=GEMINI_API_KEY
    )


# Use models available through Gemini API
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


# =========================================================
# FIREBASE
# =========================================================

FIREBASE_KEY_PATHS = [
    "/etc/secrets/firebase-key.json",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "firebase-key.json"
    ),
    "firebase-key.json"
]

firebase_key_path = next(
    (
        path
        for path in FIREBASE_KEY_PATHS
        if os.path.exists(path)
    ),
    None
)

db = None

try:
    firebase_admin.get_app()

except ValueError:

    if firebase_key_path:
        print(
            "Firebase key found:",
            firebase_key_path
        )

        cred = credentials.Certificate(
            firebase_key_path
        )

        firebase_admin.initialize_app(
            cred
        )

    else:
        print(
            "WARNING: firebase-key.json not found."
        )


try:
    if firebase_admin._apps:
        db = firestore.client()
        print("Firebase connected successfully.")
    else:
        db = None

except Exception as e:
    print(
        "Firebase connection error:",
        e
    )
    db = None


# =========================================================
# CODING KEYWORDS
# =========================================================

CODING_KEYWORDS = [

    # Programming languages
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
    "golang",
    "go programming",
    "rust",
    "kotlin",
    "swift",

    # Web development
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

    # Backend
    "flask",
    "django",
    "spring",
    "spring boot",
    "fastapi",

    # Database
    "sql",
    "mysql",
    "postgresql",
    "postgres",
    "mongodb",
    "database",
    "dbms",
    "firebase",
    "firestore",
    "oracle",

    # Computer science
    "dsa",
    "data structures",
    "data structure",
    "algorithms",
    "algorithm",
    "oops",
    "oop",
    "object oriented programming",

    # Technical
    "operating system",
    "operating systems",
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
    "gcp",
    "machine learning",
    "artificial intelligence",
    "cyber security",
    "cybersecurity",
    "linux",
    "computer science",
    "programming",
    "coding",

    # Software engineering
    "software engineering",
    "software development",
    "debugging",
    "debug",
    "data science",
    "deep learning",
    "neural network",
    "computer architecture",
    "compiler",
    "virtual machine",
    "jvm",
    "jre",
    "jdk",
    "microservices",
    "api development",
    "web development",
    "frontend",
    "backend",
    "full stack"
]


# =========================================================
# CHECK CODING TOPIC
# =========================================================

def is_coding_topic(text):

    text_lower = text.lower().strip()

    for keyword in CODING_KEYWORDS:

        pattern = r"\b" + re.escape(keyword) + r"\b"

        if re.search(
            pattern,
            text_lower
        ):
            return True

    return False


# =========================================================
# GET QUESTION COUNT
# =========================================================

def get_question_count(text):

    match = re.search(
        r"\b(\d+)\b",
        text
    )

    if match:

        count = int(
            match.group(1)
        )

        if count < 1:
            return 5

        # Safety limit
        if count > 100:
            return 100

        return count

    return 5


# =========================================================
# GET DIFFICULTY
# =========================================================

def get_difficulty(text):

    text_lower = text.lower()

    if (
        "hard" in text_lower
        or "complex" in text_lower
        or "difficult" in text_lower
        or "advanced" in text_lower
        or "challenging" in text_lower
    ):
        return "Hard"

    if "easy" in text_lower:
        return "Easy"

    if "medium" in text_lower:
        return "Medium"

    return "Mixed"


# =========================================================
# GET TOPIC
# =========================================================

def get_topic(text):

    text_lower = text.lower()

    topic = re.sub(
        r"\b("
        r"give|me|a|an|the|question|questions|quiz|for|about|"
        r"please|can|you|create|generate|make|"
        r"easy|medium|hard|complex|difficult|advanced|challenging"
        r")\b",
        " ",
        text_lower
    )

    topic = re.sub(
        r"\b\d+\b",
        " ",
        topic
    )

    topic = re.sub(
        r"\s+",
        " ",
        topic
    ).strip()

    if not topic:
        topic = text.strip()

    return topic


# =========================================================
# CLEAN GEMINI RESPONSE
# =========================================================

def clean_json_response(text):

    if not text:
        raise Exception(
            "Gemini returned an empty response."
        )

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.replace(
        "```",
        ""
    )

    text = text.strip()

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise Exception(
            "Gemini did not return valid JSON."
        )

    json_text = text[
        start:end + 1
    ]

    # Validate JSON
    json.loads(
        json_text
    )

    return json_text


# =========================================================
# VALIDATE QUESTIONS
# =========================================================

def validate_questions(
    questions,
    expected_count
):

    valid_questions = []

    seen_questions = set()

    for q in questions:

        if not isinstance(
            q,
            dict
        ):
            continue

        question_text = str(
            q.get(
                "question",
                ""
            )
        ).strip()

        options = q.get(
            "options",
            []
        )

        answer = str(
            q.get(
                "answer",
                ""
            )
        ).strip()

        # Question check
        if not question_text:
            continue

        # Duplicate question check
        question_key = (
            question_text.lower()
        )

        if question_key in seen_questions:
            continue

        seen_questions.add(
            question_key
        )

        # Options check
        if not isinstance(
            options,
            list
        ):
            continue

        if len(options) != 4:
            continue

        options = [
            str(option).strip()
            for option in options
        ]

        # Duplicate options
        if len(set(options)) != 4:
            continue

        # Answer check
        if answer not in options:
            continue

        # Shuffle options
        random.shuffle(
            options
        )

        valid_questions.append({

            "question":
                question_text,

            "options":
                options,

            "answer":
                answer

        })

    return valid_questions


# =========================================================
# GEMINI REQUEST
# =========================================================

def call_gemini_with_retry(prompt):

    if client is None:
        raise Exception(
            "Gemini API key is missing."
        )

    models_to_try = [
        PRIMARY_MODEL,
        FALLBACK_MODEL
    ]

    last_error = None

    for model_name in models_to_try:

        for attempt in range(3):

            try:

                print(
                    f"Trying model: {model_name}"
                )

                print(
                    f"Attempt: {attempt + 1}/3"
                )

                response = (
                    client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "response_mime_type":
                                "application/json"
                        }
                    )
                )

                if response is None:
                    raise Exception(
                        "Empty Gemini response."
                    )

                text = response.text

                if not text:
                    raise Exception(
                        "Gemini returned empty text."
                    )

                print(
                    f"SUCCESS: {model_name}"
                )

                return text

            except Exception as e:

                last_error = e

                error_text = str(e)

                print(
                    "Gemini error:",
                    error_text
                )

                temporary_error = (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                    or "429" in error_text
                    or "RESOURCE_EXHAUSTED"
                    in error_text
                    or "500" in error_text
                    or "INTERNAL"
                    in error_text
                )

                if temporary_error:

                    wait_time = (
                        2 ** attempt
                    )

                    print(
                        f"Retrying in "
                        f"{wait_time} seconds..."
                    )

                    time.sleep(
                        wait_time
                    )

                    continue

                break

    raise Exception(
        f"Gemini generation failed: "
        f"{last_error}"
    )


# =========================================================
# GENERATE ONE BATCH
# =========================================================

def generate_quiz_batch(
    topic,
    batch_count,
    difficulty,
    batch_number
):

    prompt = f"""
You are QuizCraft AI.

You are ONLY a coding and computer-science quiz generator.

The user requested a quiz about:

{topic}

Generate exactly {batch_count} questions.

Difficulty:
{difficulty}

Batch:
{batch_number}

STRICT RULES:

1. Every question MUST be directly related to:
{topic}

2. Only coding, programming, software development,
computer science, databases, web development,
APIs, cloud, cybersecurity, machine learning,
or closely related technical subjects are allowed.

3. Do NOT create unrelated questions.

4. Every question MUST have exactly 4 options.

5. Exactly ONE option must be correct.

6. The correct answer must be randomly distributed
among the four options.

7. Do NOT always put the correct answer first.

8. Do NOT repeat questions.

9. Questions must be technically accurate.

10. Use different question styles:
- conceptual
- code output
- debugging
- practical programming
- problem solving
- scenario based

11. If difficulty is Hard, make questions genuinely challenging.

12. For Python, when appropriate include:
variables, data types, lists, tuples, dictionaries,
sets, loops, functions, lambda, exceptions,
classes, inheritance, decorators, generators,
iterators, modules, file handling,
comprehensions, async programming and debugging.

13. For Java, when appropriate include:
classes, objects, inheritance, polymorphism,
abstraction, interfaces, exceptions,
collections, generics, threads, JVM,
memory and streams.

14. For JavaScript, when appropriate include:
let, const, var, functions, closures,
arrays, objects, DOM, promises,
async/await, callbacks and event loop.

15. For C/C++, when appropriate include:
pointers, memory, arrays, functions,
classes, STL and references.

16. For SQL, when appropriate include:
queries, joins, subqueries, aggregation,
GROUP BY, HAVING and indexes.

17. For HTML/CSS, ask real technical
web-development questions.

18. Do NOT create meaningless questions.

19. Do NOT ask generic questions such as:
"What is an important topic related to X?"

20. Return ONLY valid JSON.

Use EXACTLY this structure:

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
            "answer": "Exactly one of the four options"
        }}
    ]
}}
"""

    text = call_gemini_with_retry(
        prompt
    )

    json_text = clean_json_response(
        text
    )

    data = json.loads(
        json_text
    )

    questions = data.get(
        "questions",
        []
    )

    if not isinstance(
        questions,
        list
    ):
        raise Exception(
            "Invalid questions format."
        )

    return validate_questions(
        questions,
        batch_count
    )


# =========================================================
# GENERATE QUIZ
# =========================================================

def generate_ai_quiz(
    user_request,
    count,
    difficulty
):

    topic = get_topic(
        user_request
    )

    all_questions = []

    BATCH_SIZE = 10

    total_batches = (
        (count + BATCH_SIZE - 1)
        // BATCH_SIZE
    )

    print(
        "===================================="
    )

    print(
        f"Topic: {topic}"
    )

    print(
        f"Total questions: {count}"
    )

    print(
        f"Total batches: {total_batches}"
    )

    print(
        "===================================="
    )

    for batch_index in range(
        total_batches
    ):

        remaining = (
            count
            - len(all_questions)
        )

        current_batch_size = min(
            BATCH_SIZE,
            remaining
        )

        if current_batch_size <= 0:
            break

        print(
            f"Generating batch "
            f"{batch_index + 1}/"
            f"{total_batches}"
        )

        try:

            batch_questions = (
                generate_quiz_batch(
                    topic,
                    current_batch_size,
                    difficulty,
                    batch_index + 1
                )
            )

            existing = {
                q["question"].lower()
                for q in all_questions
            }

            for q in batch_questions:

                question_key = (
                    q["question"].lower()
                )

                if question_key not in existing:

                    all_questions.append(
                        q
                    )

                    existing.add(
                        question_key
                    )

        except Exception as e:

            print(
                "Batch error:",
                repr(e)
            )

            if not all_questions:
                raise

    if not all_questions:
        raise Exception(
            "No valid questions generated."
        )

    return all_questions[:count]


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# GENERATE QUIZ API
# =========================================================

@app.route(
    "/generate-quiz",
    methods=["POST"]
)
def generate_quiz():

    try:

        # Get JSON
        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "error":
                    "No data received."
            }), 400

        user_request = data.get(
            "subject",
            ""
        ).strip()

        if not user_request:

            return jsonify({
                "success": False,
                "error":
                    "Please enter a coding topic."
            }), 400

        # Coding topic check
        if not is_coding_topic(
            user_request
        ):

            return jsonify({
                "success": False,
                "error":
                    "I don't know. "
                    "I can only help with "
                    "coding-related quizzes."
            }), 400

        # Question count
        count = get_question_count(
            user_request
        )

        # Difficulty
        difficulty = get_difficulty(
            user_request
        )

        print(
            "===================================="
        )

        print(
            f"User request: {user_request}"
        )

        print(
            f"Question count: {count}"
        )

        print(
            f"Difficulty: {difficulty}"
        )

        # Generate questions
        questions = generate_ai_quiz(
            user_request,
            count,
            difficulty
        )

        if not questions:

            return jsonify({
                "success": False,
                "error":
                    "Questions could not be generated. "
                    "Please try again."
            }), 500

        # =================================================
        # SAVE TO FIREBASE
        # =================================================

        if db is not None:

            try:

                quiz_data = {

                    "request":
                        user_request,

                    "topic":
                        get_topic(
                            user_request
                        ),

                    "question_count":
                        len(questions),

                    "difficulty":
                        difficulty,

                    "questions":
                        questions,

                    "created_at":
                        firestore.SERVER_TIMESTAMP
                }

                db.collection(
                    "quizzes"
                ).add(
                    quiz_data
                )

                print(
                    "Quiz saved to Firebase."
                )

            except Exception as firebase_error:

                print(
                    "Firebase error:",
                    firebase_error
                )

        else:

            print(
                "Firebase not connected. "
                "Quiz will still be returned."
            )

        # Send to HTML
        return jsonify({

            "success": True,

            "subject":
                get_topic(
                    user_request
                ),

            "count":
                len(questions),

            "difficulty":
                difficulty,

            "questions":
                questions

        })

    except json.JSONDecodeError as e:

        print(
            "JSON ERROR:",
            repr(e)
        )

        return jsonify({

            "success": False,

            "error":
                "AI returned invalid JSON. "
                "Please try again."

        }), 500

    except Exception as e:

        print(
            "===================================="
        )

        print(
            "ERROR:",
            repr(e)
        )

        print(
            "===================================="
        )

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    print(
        "===================================="
    )

    print(
        "QuizCraft AI"
    )

    print(
        "Flask + Firebase + Gemini"
    )

    print(
        f"Primary Model: {PRIMARY_MODEL}"
    )

    print(
        f"Fallback Model: {FALLBACK_MODEL}"
    )

    print(
        "===================================="
    )

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        debug=False,
        host="0.0.0.0",
        port=port
    )