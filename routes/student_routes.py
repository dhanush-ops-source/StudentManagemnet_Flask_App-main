import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import mysql

student_bp = Blueprint("students", __name__)


def validate_student_data(name, email, phone, department=None, course=None, admission_year=None):
    """Validate student inputs. Returns (is_valid, error_message, phone_clean, dept_clean, crs_clean, yr_clean)"""
    if not name or not name.strip():
        return False, "Student name is required.", None, None, None, None

    if len(name.strip()) > 100:
        return False, "Student name cannot exceed 100 characters.", None, None, None, None

    if not email or not email.strip():
        return False, "Email address is required.", None, None, None, None

    email_clean = email.strip()
    if len(email_clean) > 150:
        return False, "Email address cannot exceed 150 characters.", None, None, None, None

    email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_pattern, email_clean):
        return False, "Please provide a valid email address.", None, None, None, None

    if not phone or not phone.strip():
        return False, "Phone number is required.", None, None, None, None

    phone_clean = re.sub(r"[\s\-\(\)\.]", "", phone.strip())
    if not re.match(r"^\+?[0-9]{10,15}$", phone_clean):
        return False, "Please enter a valid phone number (10 to 15 digits).", None, None, None, None

    dept_clean = department.strip() if department and department.strip() else "Computer Science"
    if len(dept_clean) > 100:
        return False, "Department name cannot exceed 100 characters.", None, None, None, None

    crs_clean = course.strip() if course and course.strip() else "B.Tech"
    if len(crs_clean) > 100:
        return False, "Course name cannot exceed 100 characters.", None, None, None, None

    try:
        yr_clean = int(admission_year) if admission_year else 2024
        if yr_clean < 1950 or yr_clean > 2100:
            return False, "Please enter a valid admission year (e.g. 2024).", None, None, None, None
    except (ValueError, TypeError):
        return False, "Admission year must be a valid number.", None, None, None, None

    return True, None, phone_clean, dept_clean, crs_clean, yr_clean


@student_bp.route("/")
def home():
    try:
        search = request.args.get("search", "").strip()
        department = request.args.get("department", "").strip()
        course = request.args.get("course", "").strip()
        year = request.args.get("year", "").strip()
        sort = request.args.get("sort", "id_asc").strip().lower()

        # Determine sort column and direction
        if sort == "name_asc":
            sort_by = "name"
            order = "ASC"
        elif sort == "name_desc":
            sort_by = "name"
            order = "DESC"
        elif sort == "id_desc":
            sort_by = "id"
            order = "DESC"
        else:  # default id_asc
            sort_by = "id"
            order = "ASC"
            sort = "id_asc"

        cur = mysql.connection.cursor()

        # Overall totals (unfiltered) for statistics cards
        cur.execute("SELECT COUNT(*) FROM students")
        total_students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM students WHERE email IS NOT NULL AND email != ''")
        email_records = cur.fetchone()[0]
        active_records = total_students

        # Distinct dropdown values for filter selects
        cur.execute("SELECT DISTINCT department FROM students WHERE department IS NOT NULL AND department != '' ORDER BY department ASC")
        all_departments = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != '' ORDER BY course ASC")
        all_courses = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT admission_year FROM students WHERE admission_year IS NOT NULL ORDER BY admission_year DESC")
        all_years = [r[0] for r in cur.fetchall()]

        # Build dynamic query for students directory
        where_conditions = ["1=1"]
        params = []

        if search:
            where_conditions.append("(name LIKE %s OR email LIKE %s OR phone LIKE %s)")
            like_term = f"%{search}%"
            params.extend([like_term, like_term, like_term])

        if department and department != "all":
            where_conditions.append("department = %s")
            params.append(department)

        if course and course != "all":
            where_conditions.append("course = %s")
            params.append(course)

        if year and year != "all":
            try:
                where_conditions.append("admission_year = %s")
                params.append(int(year))
            except ValueError:
                pass

        where_clause = " AND ".join(where_conditions)
        sql = f"""SELECT id, name, email, phone, department, course, admission_year, created_at 
                  FROM students 
                  WHERE {where_clause} 
                  ORDER BY {sort_by} {order}"""
        cur.execute(sql, tuple(params))
        students = cur.fetchall()
        cur.close()

        is_filtered = bool(
            search
            or (department and department != "all")
            or (course and course != "all")
            or (year and year != "all")
            or sort != "id_asc"
        )

        return render_template(
            "index.html",
            students=students,
            total_students=total_students,
            active_records=active_records,
            email_records=email_records,
            all_departments=all_departments,
            all_courses=all_courses,
            all_years=all_years,
            current_search=search,
            current_department=department,
            current_course=course,
            current_year=year,
            current_sort=sort,
            is_filtered=is_filtered,
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "danger")
        return render_template(
            "index.html",
            students=[],
            total_students=0,
            active_records=0,
            email_records=0,
            all_departments=[],
            all_courses=[],
            all_years=[],
            current_search="",
            current_department="",
            current_course="",
            current_year="",
            current_sort="id_asc",
            is_filtered=False,
        )


@student_bp.route("/add", methods=["POST"])
def add_student():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "Computer Science").strip()
    course = request.form.get("course", "B.Tech").strip()
    admission_year = request.form.get("admission_year", "2024").strip()

    is_valid, error_msg, phone_clean, dept_clean, crs_clean, yr_clean = validate_student_data(
        name, email, phone, department, course, admission_year
    )
    if not is_valid:
        flash(error_msg, "danger")
        return redirect(url_for("students.home"))

    cur = None
    try:
        cur = mysql.connection.cursor()
        # Check if email is already registered
        cur.execute("SELECT id FROM students WHERE email = %s", (email,))
        existing_student = cur.fetchone()
        if existing_student:
            flash(f"A student with email '{email}' already exists. Please use a unique email.", "danger")
            return redirect(url_for("students.home"))

        cur.execute(
            """INSERT INTO students (name, email, phone, department, course, admission_year) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (name, email, phone_clean, dept_clean, crs_clean, yr_clean),
        )
        mysql.connection.commit()
        flash("Student added successfully!", "success")
    except Exception as e:
        if mysql.connection:
            mysql.connection.rollback()
        flash(f"Failed to add student: {str(e)}", "danger")
    finally:
        if cur:
            cur.close()

    return redirect(url_for("students.home"))


@student_bp.route("/edit/<int:id>", methods=["POST"])
@student_bp.route("/edit", methods=["POST"])
def edit_student(id=None):
    if id is None:
        id = request.form.get("id")

    if not id:
        flash("Invalid student ID for update.", "danger")
        return redirect(url_for("students.home"))

    try:
        id = int(id)
    except ValueError:
        flash("Invalid student ID format.", "danger")
        return redirect(url_for("students.home"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    course = request.form.get("course", "").strip()
    admission_year = request.form.get("admission_year", "").strip()

    is_valid, error_msg, phone_clean, dept_clean, crs_clean, yr_clean = validate_student_data(
        name, email, phone, department, course, admission_year
    )
    if not is_valid:
        flash(error_msg, "danger")
        return redirect(url_for("students.home"))

    cur = None
    try:
        cur = mysql.connection.cursor()

        # Check if student exists
        cur.execute("SELECT id FROM students WHERE id = %s", (id,))
        if not cur.fetchone():
            flash("Student record not found.", "danger")
            return redirect(url_for("students.home"))

        # Check if email belongs to another student
        cur.execute("SELECT id FROM students WHERE email = %s AND id != %s", (email, id))
        duplicate_email = cur.fetchone()
        if duplicate_email:
            flash(f"A student with email '{email}' already exists. Please use a unique email.", "danger")
            return redirect(url_for("students.home"))

        cur.execute(
            """UPDATE students 
               SET name = %s, email = %s, phone = %s, department = %s, course = %s, admission_year = %s 
               WHERE id = %s""",
            (name, email, phone_clean, dept_clean, crs_clean, yr_clean, id),
        )
        mysql.connection.commit()
        flash("Student details updated successfully!", "success")
    except Exception as e:
        if mysql.connection:
            mysql.connection.rollback()
        flash(f"Failed to update student: {str(e)}", "danger")
    finally:
        if cur:
            cur.close()

    return redirect(url_for("students.home"))


@student_bp.route("/delete/<int:id>", methods=["GET", "POST"])
@student_bp.route("/delete", methods=["POST"])
def delete_student(id=None):
    if id is None:
        id = request.form.get("id")

    if not id:
        flash("Invalid student ID for deletion.", "danger")
        return redirect(url_for("students.home"))

    try:
        id = int(id)
    except ValueError:
        flash("Invalid student ID format.", "danger")
        return redirect(url_for("students.home"))

    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name FROM students WHERE id = %s", (id,))
        student = cur.fetchone()
        if not student:
            flash("Student record not found or already deleted.", "warning")
            return redirect(url_for("students.home"))

        cur.execute("DELETE FROM students WHERE id = %s", (id,))
        mysql.connection.commit()
        flash("Student deleted successfully!", "success")
    except Exception as e:
        if mysql.connection:
            mysql.connection.rollback()
        flash(f"Failed to delete student: {str(e)}", "danger")
    finally:
        if cur:
            cur.close()

    return redirect(url_for("students.home"))