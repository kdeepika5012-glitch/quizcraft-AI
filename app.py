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
# LOAD .ENV
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in .env")


# =========================================================
# GEMINI CONNECTION
# =========================================================

client = None

if GEMINI_API_KEY:
    client = genai.Client(
        api_key=GEMINI_API_KEY
    )


# =========================================================
# GEMINI MODELS
# =========================================================

# Main model = better for complex coding questions
PRIMARY_MODEL = "gemini-3.6-flash"

# Fallback model = faster / high-throughput
FALLBACK_MODEL = "gemini-3.5-flash-lite"


# =========================================================
# FIREBASE CONNECTION
# =========================================================

try:

    firebase_admin.get_app()

except ValueError:

    cred = credentials.Certificate(
        "firebase-key.json"
    )

    firebase_admin.initialize_app(cred)


db = firestore.client()


# =========================================================
# CODING / TECHNICAL KEYWORDS
# =========================================================

CODING_KEYWORDS = [

    # -------------------------
    # Programming languages
    # -------------------------

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

    # -------------------------
    # Web development
    # -------------------------

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

    # -------------------------
    # Backend
    # -------------------------

    "flask",
    "django",
    "spring",
    "spring boot",
    "fastapi",

    # -------------------------
    # Database
    # -------------------------

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

    # -------------------------
    # Computer science
    # -------------------------

    "dsa",
    "data structures",
    "data structure",
    "algorithms",
    "algorithm",
    "oops",
    "oop",
    "object oriented programming",

    # -------------------------
    # Technical
    # -------------------------

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

    # -------------------------
    # Software engineering
    # -------------------------

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
    "oop",
    "oop concepts",
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
# GET CODING TOPIC
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
# CLEAN GEMINI JSON
# =========================================================

def clean_json_response(text):

    if not text:

        raise Exception(
            "Gemini returned an empty response."
        )

    text = text.strip()

    # Remove ```json
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Remove ```
    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:

        raise Exception(
            "Gemini did not return valid JSON."
        )

    return text[
        start:end + 1
    ]


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

        # -------------------------
        # Question validation
        # -------------------------

        if not question_text:

            continue

        # -------------------------
        # Duplicate question check
        # -------------------------

        question_key = (
            question_text.lower()
        )

        if question_key in seen_questions:

            continue

        seen_questions.add(
            question_key
        )

        # -------------------------
        # Options validation
        # -------------------------

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

        # No duplicate options
        if len(
            set(options)
        ) != 4:

            continue

        # -------------------------
        # Answer validation
        # -------------------------

        if answer not in options:

            continue

        # -------------------------
        # Randomize options
        # -------------------------

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
# GEMINI REQUEST WITH RETRY + FALLBACK
# =========================================================

def call_gemini_with_retry(
    prompt
):

    if client is None:

        raise Exception(
            "Gemini API key is missing. "
            "Check GEMINI_API_KEY in .env"
        )


    models_to_try = [

        PRIMARY_MODEL,

        FALLBACK_MODEL

    ]


    last_error = None


    for model_name in models_to_try:

        # -----------------------------------------
        # Try each model up to 3 times
        # -----------------------------------------

        for attempt in range(3):

            try:

                print(
                    f"Trying model: {model_name}"
                )

                print(
                    f"Attempt: {attempt + 1}/3"
                )


                response = (
                    client
                    .models
                    .generate_content(

                        model=model_name,

                        contents=prompt
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
                    f"SUCCESS using {model_name}"
                )


                return text


            except Exception as e:

                last_error = e

                error_text = str(e)

                print(
                    "Gemini error:",
                    error_text
                )


                # ---------------------------------
                # Check if temporary error
                # ---------------------------------

                temporary_error = (

                    "503" in error_text

                    or

                    "UNAVAILABLE"
                    in error_text

                    or

                    "429" in error_text

                    or

                    "RESOURCE_EXHAUSTED"
                    in error_text

                    or

                    "500" in error_text

                    or

                    "INTERNAL"
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


                # ---------------------------------
                # Non-temporary error
                # ---------------------------------

                break


    # Both models failed
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

Generate exactly:

{batch_count}

questions.

Difficulty:

{difficulty}

This is batch number:

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
among option 1, 2, 3, and 4.

7. Do NOT always put the correct answer first.

8. Do not repeat questions.

9. Questions must be technically accurate.

10. Include different question styles:

- conceptual
- code output
- debugging
- practical programming
- problem solving
- scenario based

11. If difficulty is Hard or Complex,
make questions genuinely challenging.

12. For Python questions, when appropriate,
include:

- variables
- data types
- lists
- tuples
- dictionaries
- sets
- loops
- functions
- lambda
- exceptions
- classes
- inheritance
- decorators
- generators
- iterators
- modules
- file handling
- comprehensions
- async programming
- debugging
- code output

13. For Java questions, when appropriate,
include:

- classes
- objects
- inheritance
- polymorphism
- abstraction
- interfaces
- exceptions
- collections
- generics
- threads
- JVM
- memory
- streams

14. For JavaScript questions, when appropriate,
include:

- let
- const
- var
- functions
- closures
- arrays
- objects
- DOM
- promises
- async/await
- callbacks
- event loop

15. For C/C++ questions, include appropriate
pointers, memory, arrays, functions,
classes, STL, references, etc.

16. For SQL questions, include queries,
joins, subqueries, aggregation,
GROUP BY, HAVING, indexes, etc.

17. For HTML/CSS questions, ask technical
questions related to actual web development.

18. Do NOT use fake or meaningless questions.

19. Do NOT ask questions like:
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


    valid_questions = (
        validate_questions(
            questions,
            batch_count
        )
    )


    return valid_questions


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

    # -----------------------------------------
    # Batch size
    # -----------------------------------------

    # Instead of asking Gemini for 100 questions
    # in one huge request, generate smaller batches.

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
        f"Batch size: {BATCH_SIZE}"
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


            # -------------------------------------
            # Add only unique questions
            # -------------------------------------

            existing = {
                q["question"].lower()
                for q in all_questions
            }


            for q in batch_questions:

                if (
                    q["question"].lower()
                    not in existing
                ):

                    all_questions.append(
                        q
                    )

                    existing.add(
                        q["question"].lower()
                    )


        except Exception as e:

            print(
                "Batch error:",
                repr(e)
            )

            # If one batch fails, continue
            # only if we already have questions.

            if not all_questions:

                raise


    # -----------------------------------------
    # Final check
    # -----------------------------------------

    if not all_questions:

        raise Exception(
            "No valid questions generated."
        )


    # -----------------------------------------
    # Return requested count if available
    # -----------------------------------------

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

        # -----------------------------------------
        # GET REQUEST
        # -----------------------------------------

        data = request.get_json()


        if not data:

            return jsonify({

                "success":
                    False,

                "error":
                    "No data received."

            }), 400


        user_request = data.get(
            "subject",
            ""
        ).strip()


        if not user_request:

            return jsonify({

                "success":
                    False,

                "error":
                    "Please enter a coding topic."

            }), 400


        # -----------------------------------------
        # CODING CHECK
        # -----------------------------------------

        if not is_coding_topic(
            user_request
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "I don't know. "
                    "I can only help with "
                    "coding-related quizzes."

            }), 400


        # -----------------------------------------
        # QUESTION COUNT
        # -----------------------------------------

        count = get_question_count(
            user_request
        )


        # -----------------------------------------
        # DIFFICULTY
        # -----------------------------------------

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


        # -----------------------------------------
        # GENERATE QUESTIONS
        # -----------------------------------------

        questions = generate_ai_quiz(

            user_request,

            count,

            difficulty

        )


        if not questions:

            return jsonify({

                "success":
                    False,

                "error":
                    "Questions could not be generated. "
                    "Please try again."

            }), 500


        # -----------------------------------------
        # FIREBASE SAVE
        # -----------------------------------------

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


        # -----------------------------------------
        # SEND TO HTML
        # -----------------------------------------

        return jsonify({

            "success":
                True,

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


    # =====================================================
    # JSON ERROR
    # =====================================================

    except json.JSONDecodeError as e:

        print(
            "JSON ERROR:",
            repr(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                "AI returned invalid JSON. "
                "Please try again."

        }), 500


    # =====================================================
    # GENERAL ERROR
    # =====================================================

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

            "success":
                False,

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


    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000
    )