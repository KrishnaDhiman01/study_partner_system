from flask import Blueprint, render_template, session, flash, redirect, url_for, current_app, request
from functools import wraps
from ..models import db, User, StudyGroup 
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash
import traceback

admin_bp = Blueprint('admin', __name__, template_folder='templates')

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Administrator login required to access this page.", "warning")
            return redirect(url_for('admin.admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin.admin_home'))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        config_admin_user = current_app.config.get('ADMIN_USERNAME')
        config_admin_pass_hash = current_app.config.get('ADMIN_PASSWORD_HASH')

        if not config_admin_user or not config_admin_pass_hash:
            flash("Admin account is not configured on the server.", "danger")
            current_app.logger.error("ADMIN_USERNAME or ADMIN_PASSWORD_HASH not set in config.")
            return render_template("admin_login.html")

        if username == config_admin_user and check_password_hash(config_admin_pass_hash, password):
            session.clear()
            session['is_admin'] = True
            session['admin_username'] = username
            flash("Admin login successful.", "success")
            
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('admin.admin_home'))
        else:
            flash("Invalid admin username or password.", "danger")
    return render_template("admin_login.html")

@admin_bp.route("/logout")
@admin_login_required
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_username', None)
    flash("Admin logged out successfully.", "success")
    return redirect(url_for('admin.admin_login'))

@admin_bp.route("/")
@admin_login_required
def admin_home():
    return render_template("admin.html")

@admin_bp.route("/users")
@admin_login_required
def view_users():
    page = request.args.get('page', 1, type=int)
    try:
        users_pagination = User.query.order_by(User.name).paginate(page=page, per_page=15, error_out=False)
    except Exception as e:
        flash("Error retrieving user list.", "danger")
        current_app.logger.error(f"Admin view users error: {e}")
        users_pagination = None
    return render_template("view_users.html", users_pagination=users_pagination)

@admin_bp.route("/groups")
@admin_login_required
def view_groups():
    page = request.args.get('page', 1, type=int)
    try:
        groups_pagination = StudyGroup.query.options(joinedload(StudyGroup.creator))\
                               .order_by(StudyGroup.subject, StudyGroup.group_name)\
                               .paginate(page=page, per_page=15, error_out=False)
    except Exception as e:
        flash("Error retrieving group list.", "danger")
        current_app.logger.error(f"Admin view groups error: {e}")
        groups_pagination = None
    return render_template("view_groups.html", groups_pagination=groups_pagination)

@admin_bp.route("/user/delete/<int:user_id>", methods=["POST"])
@admin_login_required
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    username = user_to_delete.name
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f"User '{username}' (ID: {user_id}) has been deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "danger")
        current_app.logger.error(f"Error deleting user {user_id}: {e}\n{traceback.format_exc()}")
    return redirect(url_for('admin.view_users'))

@admin_bp.route("/group/delete/<int:group_id>", methods=["POST"])
@admin_login_required
def delete_group(group_id):
    group_to_delete = StudyGroup.query.get_or_404(group_id)
    groupname = group_to_delete.group_name
    try:
        db.session.delete(group_to_delete)
        db.session.commit()
        flash(f"Group '{groupname}' (ID: {group_id}) has been deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting group: {str(e)}", "danger")
        current_app.logger.error(f"Error deleting group {group_id}: {e}\n{traceback.format_exc()}")
    return redirect(url_for('admin.view_groups'))
