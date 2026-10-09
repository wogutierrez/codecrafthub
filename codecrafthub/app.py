import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request


# Create the Flask application
app = Flask(__name__)

# Store courses.json in the same folder as app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "courses.json")

# Allowed course statuses
VALID_STATUSES = [
    "Not Started",
    "In Progress",
    "Completed",
]


# -------------------------------------------------------------------
# JSON file helper functions
# -------------------------------------------------------------------

def create_data_file_if_needed():
    """
    Create courses.json with an empty list if it does not exist.
    """
    if not os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as file:
                json.dump([], file, indent=4)
        except OSError as error:
            raise RuntimeError(
                f"Could not create courses.json: {error}"
            )


def read_courses():
    """
    Read all courses from courses.json.
    """
    create_data_file_if_needed()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            courses = json.load(file)

        if not isinstance(courses, list):
            raise RuntimeError(
                "courses.json must contain a JSON list."
            )

        return courses

    except FileNotFoundError:
        # This is unlikely because create_data_file_if_needed() runs first,
        # but it is handled for safety.
        create_data_file_if_needed()
        return []

    except json.JSONDecodeError:
        raise RuntimeError(
            "courses.json contains invalid JSON."
        )

    except OSError as error:
        raise RuntimeError(
            f"Could not read courses.json: {error}"
        )


def write_courses(courses):
    """
    Save all courses to courses.json.
    """
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(courses, file, indent=4)
    except OSError as error:
        raise RuntimeError(
            f"Could not write to courses.json: {error}"
        )


# -------------------------------------------------------------------
# Validation helper functions
# -------------------------------------------------------------------

def validate_course_data(data):
    """
    Validate the data received when creating or updating a course.

    Returns:
        A tuple containing either:
        - an error response dictionary and HTTP status code, or
        - None if the data is valid
    """

    if not isinstance(data, dict):
        return {
            "error": "Request body must contain a JSON object."
        }, 400

    required_fields = [
        "name",
        "description",
        "target_date",
        "status",
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return {
            "error": (
                "Missing required fields: "
                + ", ".join(missing_fields)
            )
        }, 400

    # Make sure required text fields are not empty
    for field in required_fields:
        if not isinstance(data[field], str):
            return {
                "error": f"'{field}' must be a string."
            }, 400

        if not data[field].strip():
            return {
                "error": f"'{field}' cannot be empty."
            }, 400

    # Check status
    if data["status"] not in VALID_STATUSES:
        return {
            "error": (
                "Invalid status. Status must be one of: "
                + ", ".join(VALID_STATUSES)
            )
        }, 400

    # Check target date
    try:
        datetime.strptime(data["target_date"], "%Y-%m-%d")
    except ValueError:
        return {
            "error": (
                "'target_date' must be a valid date "
                "using the YYYY-MM-DD format."
            )
        }, 400

    return None


def find_course(courses, course_id):
    """
    Find a course by ID.

    Returns:
        The course if found, otherwise None.
    """
    for course in courses:
        if course.get("id") == course_id:
            return course

    return None


def get_next_id(courses):
    """
    Generate the next course ID, starting at 1.
    """
    if not courses:
        return 1

    highest_id = max(
        course.get("id", 0)
        for course in courses
    )

    return highest_id + 1


# -------------------------------------------------------------------
# Error handling
# -------------------------------------------------------------------

@app.errorhandler(404)
def handle_404(error):
    """
    Return JSON instead of Flask's default HTML 404 page.
    """
    return jsonify({
        "error": "The requested endpoint was not found."
    }), 404


@app.errorhandler(500)
def handle_500(error):
    """
    Return JSON for unexpected server errors.
    """
    return jsonify({
        "error": "An internal server error occurred."
    }), 500


# -------------------------------------------------------------------
# API endpoints
# -------------------------------------------------------------------

@app.route("/api/courses", methods=["POST"])
@app.route("/api/courses/", methods=["POST"])
def create_course():
    """
    Create a new course.

    POST /api/courses
    """

    data = request.get_json(silent=True)

    if data is None:
        return jsonify({
            "error": "Request body must contain valid JSON."
        }), 400

    validation_error = validate_course_data(data)

    if validation_error:
        error_response, status_code = validation_error
        return jsonify(error_response), status_code

    try:
        courses = read_courses()

        new_course = {
            "id": get_next_id(courses),
            "name": data["name"].strip(),
            "description": data["description"].strip(),
            "target_date": data["target_date"].strip(),
            "status": data["status"].strip(),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        courses.append(new_course)
        write_courses(courses)

        return jsonify({
            "message": "Course created successfully.",
            "course": new_course
        }), 201

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 500


@app.route("/api/courses", methods=["GET"])
@app.route("/api/courses/", methods=["GET"])
def get_all_courses():
    """
    Get all courses.

    GET /api/courses
    """
    try:
        courses = read_courses()
        return jsonify(courses), 200

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 500


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """
    Get one course by ID.

    GET /api/courses/1
    """
    try:
        courses = read_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        return jsonify(course), 200

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 500


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """
    Update an existing course.

    PUT /api/courses/1
    """

    data = request.get_json(silent=True)

    if data is None:
        return jsonify({
            "error": "Request body must contain valid JSON."
        }), 400

    validation_error = validate_course_data(data)

    if validation_error:
        error_response, status_code = validation_error
        return jsonify(error_response), status_code

    try:
        courses = read_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        # Keep the original id and created_at values.
        course["name"] = data["name"].strip()
        course["description"] = data["description"].strip()
        course["target_date"] = data["target_date"].strip()
        course["status"] = data["status"].strip()

        write_courses(courses)

        return jsonify({
            "message": "Course updated successfully.",
            "course": course
        }), 200

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 500


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """
    Delete a course by ID.

    DELETE /api/courses/1
    """
    try:
        courses = read_courses()
        course = find_course(courses, course_id)

        if course is None:
            return jsonify({
                "error": f"Course with ID {course_id} was not found."
            }), 404

        courses.remove(course)
        write_courses(courses)

        return jsonify({
            "message": "Course deleted successfully.",
            "course": course
        }), 200

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 500


# -------------------------------------------------------------------
# Start the application
# -------------------------------------------------------------------


if __name__ == "__main__":
    try:
        create_data_file_if_needed()
        print(f"Using data file: {DATA_FILE}")
    except RuntimeError as error:
        print(f"Startup error: {error}")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )