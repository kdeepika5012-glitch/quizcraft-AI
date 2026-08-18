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

app = Flask(__name__)

# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found.")

client = None

if GEMINI_API_KEY:
    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


# =========================================================
# FIREBASE
# =========================================================

db = None

firebase_paths = [
    "/etc/secrets/firebase-key.json",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "firebase-key.json"
    ),
    "firebase-key.json"
]

firebase_key_path = None

for path in firebase_paths:
    if os.path.exists(path):
        firebase_key_path = path
        break

try:

    if firebase_admin._apps:

        db = firestore.client()

        print(
            "Firebase already initialized."
        )

    elif firebase_key_path:

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

        db = firestore.client()

        print(
            "Firebase connected successfully."
        )

    else:

        print(
            "WARNING: firebase-key.json not found."
        )

except Exception as e:

    db = None

    print(
        "Firebase connection error:",
        e
    )


# =========================================================
# CODING KEYWORDS
# =========================================================

CODING_KEYWORDS = [

    # Programming Languages
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "cpp",
    "c#",
    "csharp",
    "php",
    "ruby",
    "golang",
    "rust",
    "kotlin",
    "swift",

    # Web
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

    # Computer Science
    "dsa",
    "data structures",
    "data structure",
    "algorithms",
    "algorithm",
    "oops",
    "oop",
    "object oriented programming",

    # Systems
    "operating system",
    "operating systems",
    "computer networks",
    "networking",

    # Development
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

    # AI
    "machine learning",
    "artificial intelligence",
    "deep learning",
    "neural network",

    # Security
    "cyber security",
    "cybersecurity",

    # Other
    "linux",
    "computer science",
    "programming",
    "coding",
    "software engineering",
    "software development",
    "debugging",
    "debug",
    "data science",
    "computer architecture",
    "compiler",
    "jvm",
    "jre",
    "jdk",
    "microservices",
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

        if keyword in text_lower:

            return True

    return False


# =========================================================
# QUESTION COUNT
# =========================================================

def get_question_count(text):

    match = re.search(
        r"\b(\d+)\b",
        text
    )

    if not match:

        return 5

    count = int(
        match.group(1)
    )

    if count < 1:

        return 5

    if count > 100:

        return 100

    return count


# =========================================================
# DIFFICULTY
# =========================================================

def get_difficulty(text):

    text_lower = text.lower()

    if any(
        word in text_lower
        for word in [
            "hard",
            "complex",
            "difficult",
            "advanced",
            "challenging"
        ]
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

    topic = text.lower()

    remove_words = [
        "give",
        "me",
        "a",
        "an",
        "the",
        "question",
        "questions",
        "quiz",
        "for",
        "about",
        "please",
        "can",
        "you",
        "create",
        "generate",
        "make",
        "easy",
        "medium",
        "hard",
        "complex",
        "difficult",
        "advanced",
        "challenging"
    ]

    for word in remove_words:

        topic = re.sub(
            r"\b" + re.escape(word) + r"\b",
            " ",
            topic
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

        return text.strip()

    return topic


# =========================================================
# CLEAN JSON RESPONSE
# =========================================================

def clean_json_response(text):

    if not text:

        raise Exception(
            "Gemini returned an empty response."
        )

    text = text.strip()

    # Remove markdown code blocks
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

    # Test JSON
    json.loads(
        json_text
    )

    return json_text


# =========================================================
# VALIDATE QUESTIONS
# =========================================================

def validate_questions(questions):

    valid_questions = []

    seen = set()

    for item in questions:

        if not isinstance(
            item,
            dict
        ):

            continue

        question = str(
            item.get(
                "question",
                ""
            )
        ).strip()

        options = item.get(
            "options",
            []
        )

        answer = str(
            item.get(
                "answer",
                ""
            )
        ).strip()

        if not question:

            continue

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

        if len(
            set(options)
        ) != 4:

            continue

        if answer not in options:

            continue

        question_key = (
            question.lower()
        )

        if question_key in seen:

            continue

        seen.add(
            question_key
        )

        # Randomize correct answer position
        random.shuffle(
            options
        )

        valid_questions.append({

            "question":
                question,

            "options":
                options,

            "answer":
                answer

        })

    return valid_questions


# =========================================================
# CALL GEMINI
# =========================================================

def call_gemini(prompt):

    if client is None:

        raise Exception(
            "GEMINI_API_KEY is missing."
        )

    models = [
        PRIMARY_MODEL,
        FALLBACK_MODEL
    ]

    last_error = None

    for model_name in models:

        for attempt in range(3):

            try:

                print(
                    "Gemini model:",
                    model_name
                )

                print(
                    "Attempt:",
                    attempt + 1
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

                return text

            except Exception as e:

                last_error = e

                print(
                    "Gemini error:",
                    e
                )

                error_text = str(e).upper()

                temporary = (
                    "429" in error_text
                    or "500" in error_text
                    or "503" in error_text
                    or "UNAVAILABLE"
                    in error_text
                    or "RESOURCE_EXHAUSTED"
                    in error_text
                    or "INTERNAL"
                    in error_text
                )

                if temporary:

                    wait_time = (
                        2 ** attempt
                    )

                    time.sleep(
                        wait_time
                    )

                else:

                    break

    raise Exception(
        f"Gemini generation failed: {last_error}"
    )


# =========================================================
# GENERATE ONE BATCH
# =========================================================

def generate_quiz_batch(
    topic,
    count,
    difficulty
):

    prompt = f"""
You are QuizCraft AI.

Generate a multiple-choice programming quiz.

Topic:
{topic}

Difficulty:
{difficulty}

Number of questions:
{count}

STRICT RULES:

1. Generate EXACTLY {count} questions.

2. Questions MUST be directly related to:
{topic}

3. Only technical/coding questions.

4. Every question must have EXACTLY
4 different options.

5. Exactly ONE option must be correct.

6. The answer must exactly match
one of the four options.

7. Randomize the correct answer position.

8. Do not always put the correct answer
as Option A.

9. Do not repeat questions.

10. Questions must be technically accurate.

11. Include conceptual, practical,
debugging, code-output and
problem-solving questions when suitable.

12. Hard questions must genuinely
be challenging.

13. Return ONLY valid JSON.

Return EXACTLY this structure:

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

    raw_response = call_gemini(
        prompt
    )

    json_text = clean_json_response(
        raw_response
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
        questions
    )


# =========================================================
# GENERATE COMPLETE QUIZ
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

    batch_size = 10

    required_batches = (
        (count + batch_size - 1)
        // batch_size
    )

    # Extra attempts if Gemini returns fewer
    max_batches = (
        required_batches + 3
    )

    for batch_number in range(
        max_batches
    ):

        remaining = (
            count
            - len(all_questions)
        )

        if remaining <= 0:

            break

        current_count = min(
            batch_size,
            remaining
        )

        try:

            batch = generate_quiz_batch(
                topic,
                current_count,
                difficulty
            )

            existing_questions = {
                q["question"].lower()
                for q in all_questions
            }

            for question in batch:

                key = (
                    question["question"]
                    .lower()
                )

                if key not in existing_questions:

                    all_questions.append(
                        question
                    )

                    existing_questions.add(
                        key
                    )

                    if len(
                        all_questions
                    ) >= count:

                        break

        except Exception as e:

            print(
                "Batch error:",
                e
            )

            # Continue trying another batch
            continue

    if not all_questions:

        raise Exception(
            "No valid questions generated."
        )

    return all_questions[
        :count
    ]


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# GENERATE QUIZ
# =========================================================

@app.route(
    "/generate-quiz",
    methods=["POST"]
)
def generate_quiz():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({

                "success":
                    False,

                "error":
                    "No data received."

            }), 400

        user_request = str(
            data.get(
                "subject",
                ""
            )
        ).strip()

        if not user_request:

            return jsonify({

                "success":
                    False,

                "error":
                    "Please enter a coding topic."

            }), 400

        # Only coding topics
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

        count = get_question_count(
            user_request
        )

        difficulty = get_difficulty(
            user_request
        )

        print(
            "================================"
        )

        print(
            "User request:",
            user_request
        )

        print(
            "Topic:",
            get_topic(
                user_request
            )
        )

        print(
            "Questions:",
            count
        )

        print(
            "Difficulty:",
            difficulty
        )

        print(
            "================================"
        )

        # Generate quiz
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
                    "No questions generated."

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
                    "Firebase save error:",
                    firebase_error
                )

        # Return quiz
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

    except Exception as e:

        print(
            "================================"
        )

        print(
            "SERVER ERROR:",
            repr(e)
        )

        print(
            "================================"
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "QuizCraft AI"
    )

    print(
        "Flask + Firebase + Gemini"
    )

    print(
        "================================"
    )

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )