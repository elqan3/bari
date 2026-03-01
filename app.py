import os
import sqlite3
import uuid
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename


# ---- Basic app setup ----
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "portfolio.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB max upload size


def get_db():
    """Open SQLite connection for current request context."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    """Close DB connection after request completes."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and seed default categories if needed."""
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            image_filename TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        );
        """
    )

    default_categories = [
        "تصميم مطاعم",
        "محال تجارية",
        "مؤسسات",
        "تصاميم شخصية",
    ]

    for category in default_categories:
        db.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            (category,),
        )

    db.commit()


def allowed_file(filename):
    """Allow only known image extensions."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(view_function):
    """Simple decorator to protect admin routes."""
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("يرجى تسجيل الدخول أولاً.", "warning")
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)

    return wrapped


def get_admin_credentials():
    """
    Read admin credentials from environment.
    Fallback values are beginner-friendly defaults.
    """
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    return username, password


def save_uploaded_image(file_storage):
    """Save uploaded image with unique filename and return saved name."""
    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{extension}"
    file_storage.save(UPLOAD_FOLDER / unique_name)
    return unique_name


def remove_image_file(filename):
    """Delete image from disk safely if it exists."""
    file_path = UPLOAD_FOLDER / filename
    if file_path.exists() and file_path.is_file():
        file_path.unlink()


@app.route("/")
def index():
    """Public portfolio page with categories and image works."""
    db = get_db()
    categories = db.execute(
        """
        SELECT c.id, c.name
        FROM categories c
        ORDER BY c.id ASC
        """
    ).fetchall()

    works = db.execute(
        """
        SELECT w.id, w.title, w.image_filename, w.category_id, c.name AS category_name
        FROM works w
        JOIN categories c ON c.id = w.category_id
        ORDER BY w.created_at DESC
        """
    ).fetchall()

    works_by_category = {category["id"]: [] for category in categories}
    for work in works:
        works_by_category.setdefault(work["category_id"], []).append(work)

    return render_template(
        "index.html",
        categories=categories,
        works_by_category=works_by_category,
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Simple admin login form."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        valid_username, valid_password = get_admin_credentials()

        if username == valid_username and password == valid_password:
            session["admin_logged_in"] = True
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("بيانات الدخول غير صحيحة.", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout")
@admin_required
def admin_logout():
    """Log out admin user."""
    session.clear()
    flash("تم تسجيل الخروج.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    """Dashboard to view works and categories."""
    db = get_db()
    works = db.execute(
        """
        SELECT w.id, w.title, w.image_filename, c.name AS category_name
        FROM works w
        JOIN categories c ON c.id = w.category_id
        ORDER BY w.created_at DESC
        """
    ).fetchall()

    categories = db.execute(
        """
        SELECT c.id, c.name,
               (SELECT COUNT(*) FROM works w WHERE w.category_id = c.id) AS work_count
        FROM categories c
        ORDER BY c.id ASC
        """
    ).fetchall()

    return render_template(
        "admin_dashboard.html",
        works=works,
        categories=categories,
    )


@app.route("/admin/categories/new", methods=["POST"])
@admin_required
def create_category():
    """Create a new category from dashboard."""
    category_name = request.form.get("name", "").strip()
    if not category_name:
        flash("اسم التصنيف مطلوب.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    try:
        db.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        db.commit()
        flash("تم إضافة التصنيف بنجاح.", "success")
    except sqlite3.IntegrityError:
        flash("هذا التصنيف موجود بالفعل.", "warning")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id):
    """Delete category only if there are no works attached."""
    db = get_db()
    category = db.execute(
        "SELECT id, name FROM categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    if not category:
        flash("التصنيف غير موجود.", "error")
        return redirect(url_for("admin_dashboard"))

    work_count = db.execute(
        "SELECT COUNT(*) AS count FROM works WHERE category_id = ?",
        (category_id,),
    ).fetchone()["count"]
    if work_count > 0:
        flash("لا يمكن حذف تصنيف يحتوي على أعمال.", "warning")
        return redirect(url_for("admin_dashboard"))

    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    flash("تم حذف التصنيف.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/works/new", methods=["GET", "POST"])
@admin_required
def create_work():
    """Create a new portfolio work."""
    db = get_db()
    categories = db.execute(
        "SELECT id, name FROM categories ORDER BY id ASC"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id = request.form.get("category_id", "").strip()
        image_file = request.files.get("image")

        if not title or not category_id:
            flash("العنوان والتصنيف مطلوبان.", "error")
            return render_template("admin_work_form.html", categories=categories, work=None)

        if not image_file or not image_file.filename:
            flash("يرجى اختيار صورة.", "error")
            return render_template("admin_work_form.html", categories=categories, work=None)

        if not allowed_file(image_file.filename):
            flash("نوع الصورة غير مدعوم. استخدم JPG/PNG/WEBP.", "error")
            return render_template("admin_work_form.html", categories=categories, work=None)

        filename = save_uploaded_image(image_file)
        db.execute(
            """
            INSERT INTO works (title, category_id, image_filename)
            VALUES (?, ?, ?)
            """,
            (title, category_id, filename),
        )
        db.commit()
        flash("تم إضافة العمل بنجاح.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_work_form.html", categories=categories, work=None)


@app.route("/admin/works/<int:work_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_work(work_id):
    """Edit work title/category and optionally replace image."""
    db = get_db()
    work = db.execute(
        """
        SELECT id, title, category_id, image_filename
        FROM works
        WHERE id = ?
        """,
        (work_id,),
    ).fetchone()

    if not work:
        flash("العمل غير موجود.", "error")
        return redirect(url_for("admin_dashboard"))

    categories = db.execute(
        "SELECT id, name FROM categories ORDER BY id ASC"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id = request.form.get("category_id", "").strip()
        image_file = request.files.get("image")

        if not title or not category_id:
            flash("العنوان والتصنيف مطلوبان.", "error")
            return render_template("admin_work_form.html", categories=categories, work=work)

        new_filename = work["image_filename"]
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("نوع الصورة غير مدعوم. استخدم JPG/PNG/WEBP.", "error")
                return render_template("admin_work_form.html", categories=categories, work=work)

            new_filename = save_uploaded_image(image_file)
            remove_image_file(work["image_filename"])

        db.execute(
            """
            UPDATE works
            SET title = ?, category_id = ?, image_filename = ?
            WHERE id = ?
            """,
            (title, category_id, new_filename, work_id),
        )
        db.commit()
        flash("تم تحديث العمل بنجاح.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_work_form.html", categories=categories, work=work)


@app.route("/admin/works/<int:work_id>/delete", methods=["POST"])
@admin_required
def delete_work(work_id):
    """Delete a work and its image file."""
    db = get_db()
    work = db.execute(
        "SELECT id, image_filename FROM works WHERE id = ?",
        (work_id,),
    ).fetchone()
    if not work:
        flash("العمل غير موجود.", "error")
        return redirect(url_for("admin_dashboard"))

    db.execute("DELETE FROM works WHERE id = ?", (work_id,))
    db.commit()
    remove_image_file(work["image_filename"])
    flash("تم حذف العمل.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(413)
def file_too_large(_error):
    """Friendly message when image exceeds upload limit."""
    flash("حجم الملف كبير جدًا. الحد الأقصى 8MB.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.errorhandler(404)
def page_not_found(_error):
    """Custom simple 404 page."""
    return render_template("404.html"), 404


def bootstrap():
    """Create required folders and initialize database."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        init_db()


if __name__ == "__main__":
    bootstrap()
    app.run(debug=True)
