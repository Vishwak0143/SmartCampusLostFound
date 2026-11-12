import os
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///lost_found.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    class User(UserMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        role = db.Column(db.String(20), nullable=False, default="student")

        def set_password(self, password):
            self.password_hash = generate_password_hash(password)

        def check_password(self, password):
            return check_password_hash(self.password_hash, password)

    class Item(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        report_type = db.Column(db.String(10), nullable=False)  # LOST or FOUND
        title = db.Column(db.String(120), nullable=False)
        description = db.Column(db.Text, nullable=False)
        category = db.Column(db.String(50), nullable=False)
        location = db.Column(db.String(100), nullable=False)
        report_date = db.Column(db.Date, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="OPEN")
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        owner = db.relationship("User", backref="items")

    class Claim(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
        claimant_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        message = db.Column(db.Text, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="PENDING")
        reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
        reviewed_at = db.Column(db.DateTime)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        item = db.relationship("Item", backref="claims")
        claimant = db.relationship("User", foreign_keys=[claimant_id], backref="claims")
        reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.get("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name or not email or len(password) < 8:
                flash("Enter your name, a valid email and a password of at least 8 characters.", "error")
            elif User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
            else:
                user = User(name=name, email=email, role="student")
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("Account created. Please sign in.", "success")
                return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        stats = {
            "lost": Item.query.filter_by(report_type="LOST").count(),
            "found": Item.query.filter_by(report_type="FOUND").count(),
            "pending": Claim.query.filter_by(status="PENDING").count(),
            "returned": Item.query.filter_by(status="RETURNED").count(),
        }
        recent = Item.query.order_by(Item.created_at.desc()).limit(5).all()
        return render_template("dashboard.html", stats=stats, recent=recent)

    @app.route("/items/new", methods=["GET", "POST"])
    @login_required
    def new_item():
        if request.method == "POST":
            report_type = request.form.get("report_type", "").upper()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            location = request.form.get("location", "").strip()
            date_text = request.form.get("report_date", "")
            try:
                report_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                report_date = None
            if report_type not in ("LOST", "FOUND") or not all([title, description, category, location, report_date]):
                flash("Complete all required fields with a valid date.", "error")
            else:
                item = Item(report_type=report_type, title=title, description=description,
                            category=category, location=location, report_date=report_date,
                            created_by=current_user.id)
                db.session.add(item)
                db.session.commit()
                flash("Your report was submitted successfully.", "success")
                return redirect(url_for("item_detail", item_id=item.id))
        return render_template("new_item.html")

    @app.get("/items")
    @login_required
    def items():
        query = Item.query
        category = request.args.get("category", "").strip()
        location = request.args.get("location", "").strip()
        report_type = request.args.get("type", "").upper()
        if category:
            query = query.filter(Item.category.ilike(f"%{category}%"))
        if location:
            query = query.filter(Item.location.ilike(f"%{location}%"))
        if report_type in ("LOST", "FOUND"):
            query = query.filter_by(report_type=report_type)
        results = query.order_by(Item.created_at.desc()).all()
        return render_template("items.html", items=results)

    @app.get("/items/<int:item_id>")
    @login_required
    def item_detail(item_id):
        item = db.get_or_404(Item, item_id)
        return render_template("item_detail.html", item=item)

    @app.post("/items/<int:item_id>/claims")
    @login_required
    def submit_claim(item_id):
        item = db.get_or_404(Item, item_id)
        message = request.form.get("message", "").strip()
        if item.report_type != "FOUND" or item.status != "OPEN":
            flash("Claims can only be submitted for open found-item reports.", "error")
        elif not message:
            flash("Please provide ownership details for the officer.", "error")
        elif Claim.query.filter_by(item_id=item.id, claimant_id=current_user.id, status="PENDING").first():
            flash("You already have a pending claim for this item.", "error")
        else:
            db.session.add(Claim(item_id=item.id, claimant_id=current_user.id, message=message))
            db.session.commit()
            flash("Claim submitted for officer review.", "success")
        return redirect(url_for("item_detail", item_id=item.id))

    @app.get("/my-activity")
    @login_required
    def my_activity():
        my_items = Item.query.filter_by(created_by=current_user.id).order_by(Item.created_at.desc()).all()
        my_claims = Claim.query.filter_by(claimant_id=current_user.id).order_by(Claim.created_at.desc()).all()
        return render_template("my_activity.html", items=my_items, claims=my_claims)

    @app.get("/officer")
    @role_required("officer", "admin")
    def officer_panel():
        claims = Claim.query.order_by(Claim.created_at.desc()).all()
        return render_template("officer.html", claims=claims)

    @app.post("/claims/<int:claim_id>/review")
    @role_required("officer", "admin")
    def review_claim(claim_id):
        claim = db.get_or_404(Claim, claim_id)
        decision = request.form.get("decision", "").upper()
        if claim.status != "PENDING" or decision not in ("APPROVED", "REJECTED"):
            flash("This claim cannot be reviewed with the supplied action.", "error")
        else:
            claim.status = decision
            claim.reviewed_by = current_user.id
            claim.reviewed_at = datetime.utcnow()
            if decision == "APPROVED":
                claim.item.status = "RETURNED"
            db.session.commit()
            flash(f"Claim {decision.lower()}.", "success")
        return redirect(url_for("officer_panel"))

    @app.get("/reports")
    @role_required("officer", "admin")
    def reports():
        summary = {
            "lost": Item.query.filter_by(report_type="LOST").count(),
            "found": Item.query.filter_by(report_type="FOUND").count(),
            "pending_claims": Claim.query.filter_by(status="PENDING").count(),
            "returned": Item.query.filter_by(status="RETURNED").count(),
        }
        categories = db.session.query(Item.category, db.func.count(Item.id)).group_by(Item.category).all()
        locations = db.session.query(Item.location, db.func.count(Item.id)).group_by(Item.location).all()
        return render_template("reports.html", summary=summary, categories=categories, locations=locations)

    @app.get("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}, 200
        except Exception:
            return {"status": "unhealthy", "database": "unavailable"}, 503

    @app.cli.command("promote-officer")
    def promote_officer():
        """Promote an existing registered account to officer (local academic setup only)."""
        import click
        email = click.prompt("Email of the registered account").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo("Account not found. Register the account first.")
            return
        user.role = "officer"
        db.session.commit()
        click.echo(f"{email} is now an officer.")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You do not have permission to access this page."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The requested page was not found."), 404

    return app

if __name__ == "__main__":
    create_app().run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
