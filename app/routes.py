from flask import (Blueprint, render_template, request,redirect, url_for, flash, session, current_app)
from functools import wraps
from .models import db, User, StudyGroup, Message, Notification 
from .algorithms.search_sort import search_users_by_query
from .algorithms.matching import (build_user_graph, dijkstra_find_partners,kmeans_cluster_users)
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload 
import traceback
import json

main_bp = Blueprint('main', __name__)


def login_required(f):
    """Ensures a regular user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('is_admin'): 
            flash("Please log in as a regular user to access this page.", "warning")
            return redirect(url_for('main.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def create_notification(recipient_user_id, notif_type, content_dict, link=None):
    try:
        user_exists = db.session.query(User.id).filter_by(id=recipient_user_id).scalar() is not None
        if not user_exists:
            current_app.logger.warning(f"Attempted to create notification for non-existent user ID: {recipient_user_id}")
            return

        notification = Notification(
            user_id=recipient_user_id,
            type=notif_type,
            content=json.dumps(content_dict) if content_dict else None,
            link=link,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        current_app.logger.info(f"Notification created for user {recipient_user_id}, type {notif_type}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating notification: {e}\n{traceback.format_exc()}")


@main_bp.route("/", methods=["GET", "POST"]) 
def index():
    if session.get('user_id') and not session.get('is_admin'): 
        return redirect(url_for('main.dashboard'))
    if session.get('is_admin'): 
        return redirect(url_for('admin.admin_home'))

    form_data_to_pass = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name = form_data_to_pass.get('name')
        email = form_data_to_pass.get('email')
        subject = form_data_to_pass.get('subject')
        availability = form_data_to_pass.get('availability')
        preference = form_data_to_pass.get('preference')
        password = form_data_to_pass.get('password')

        if not all([name, email, subject, availability, password]):
            flash("Please fill out all required fields.", "danger")
            return render_template('index.html', form_data=form_data_to_pass)
        
        existing_user = User.query.filter(func.lower(User.email) == func.lower(email)).first()
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('main.login'))
        try:
            new_user = User(name=name, email=email, subject=subject, availability=availability, preference=preference)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash(f"Account created successfully for {name}! Please log in.", "success")
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Signup Error: {e}\n{traceback.format_exc()}")
            flash("An unexpected error occurred during signup. Please try again.", "danger")
            return render_template('index.html', form_data=form_data_to_pass)
            
    return render_template('index.html', form_data=form_data_to_pass) 

@main_bp.route("/login", methods=["GET", "POST"])
def login(): 
    if session.get('user_id') and not session.get('is_admin'): return redirect(url_for('main.dashboard'))
    if session.get('is_admin'): return redirect(url_for('admin.admin_home'))

    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash("Please enter both email and password.", "warning")
            return redirect(url_for('main.login'))

        user = User.query.filter(func.lower(User.email) == func.lower(email)).first()
        if user and user.check_password(password):
            session.clear() 
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = False 
            session.permanent = remember
            flash(f"Welcome back, {user.name}!", "success")
            
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('main.dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "danger")
            return redirect(url_for('main.login')) 
            
    return render_template("login.html")

@main_bp.route("/logout")

def logout(): 
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('unread_notifications', None)
    session.pop('is_admin', None)
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('main.login'))

@main_bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session['user_id']
    current_user = User.query.options(
        selectinload(User.member_of_groups), 
        selectinload(User.created_groups)
    ).get(user_id)
    
    if not current_user: 
        flash("User data could not be loaded. Please log in again.", "warning")
        return redirect(url_for('main.logout'))
    
    try:
        unread_notifications_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        session['unread_notifications'] = unread_notifications_count
    except Exception as e:
        current_app.logger.error(f"Error fetching notification count for user {user_id}: {e}")
        session['unread_notifications'] = 0

    return render_template("dashboard.html", current_user=current_user)

@main_bp.route("/profile/<int:view_user_id>")
@login_required
def view_profile(view_user_id):
    profile_user = User.query.options(
        selectinload(User.member_of_groups), 
        selectinload(User.created_groups)
    ).get_or_404(view_user_id)
    return render_template("profile_view.html", profile_user=profile_user)

@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user_id = session['user_id']
    user_to_edit = User.query.get_or_404(user_id)
    
    
    form_data = request.form if request.method == "POST" else {}

    if request.method == "POST":
        user_to_edit.name = form_data.get('name', user_to_edit.name).strip()
        user_to_edit.subject = form_data.get('subject', user_to_edit.subject).strip()
        user_to_edit.availability = form_data.get('availability', user_to_edit.availability).strip()
        user_to_edit.preference = form_data.get('preference', user_to_edit.preference).strip()
        
        new_password = form_data.get('new_password')
        confirm_password = form_data.get('confirm_password')
        password_error = False

        if new_password: 
            if new_password == confirm_password:
                user_to_edit.set_password(new_password)
            else:
                flash("New passwords do not match. Password not changed.", "danger")
                password_error = True
        
        if not password_error:
            try:
                db.session.commit()
                flash("Profile updated successfully.", "success")
                session['user_name'] = user_to_edit.name 
                return redirect(url_for('main.view_profile', view_user_id=user_id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Profile Update Error (User ID: {user_id}): {e}\n{traceback.format_exc()}")
                flash("An error occurred while updating your profile.", "danger")
        return render_template("profile_edit.html", user=user_to_edit, form_data=form_data) 
        
    return render_template("profile_edit.html", user=user_to_edit, form_data=form_data)


@main_bp.route("/search")
@login_required 
def search():
    query = request.args.get("q", "").strip()
    results = []
    if query:
        try:
            results = search_users_by_query(query) 
        except Exception as e:
            flash("An error occurred during the search.", "danger")
            current_app.logger.error(f"Search Error for query '{query}': {e}\n{traceback.format_exc()}")
    return render_template("search_results.html", results=results, query=query)



@main_bp.route("/groups")
@login_required
def list_groups():
    current_user = User.query.get(session['user_id']) 
    all_groups = StudyGroup.query.options(joinedload(StudyGroup.creator))\
                                .order_by(StudyGroup.subject, StudyGroup.group_name).all()
    return render_template("group_list.html", groups=all_groups, current_user=current_user)

@main_bp.route("/group/<int:group_id>")
@login_required
def view_group(group_id):
    group = StudyGroup.query.options(
        selectinload(StudyGroup.members), 
        joinedload(StudyGroup.creator)    
    ).get_or_404(group_id)
    
    current_user = User.query.get(session['user_id']) 
    is_member = current_user in group.members if current_user else False
    
    return render_template("group_view.html", group=group, is_member=is_member, current_user_id=session['user_id'])

@main_bp.route("/create-group", methods=["GET", "POST"])
@login_required
def create_group():
    user_id = session['user_id']
    form_data_to_pass = request.form if request.method == "POST" else {}

    if request.method == "POST":
        group_name = form_data_to_pass.get('group_name')
        subject = form_data_to_pass.get('subject')
        description = form_data_to_pass.get('description')

        if not group_name or not subject:
            flash("Group Name and Subject are required fields.", "danger")
            return render_template("create_group.html", form_data=form_data_to_pass)
        try:
            creator = User.query.get(user_id) 
            
            group = StudyGroup(group_name=group_name, subject=subject, description=description, created_by_id=creator.id)
            db.session.add(group)
            group.members.append(creator) 
            db.session.commit()
            flash(f"Study group '{group.group_name}' created successfully!", "success")
            return redirect(url_for('main.view_group', group_id=group.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating group: {e}\n{traceback.format_exc()}")
            flash("An error occurred while creating the group. Please try again.", "danger")
            return render_template("create_group.html", form_data=form_data_to_pass)
            
    return render_template("create_group.html", form_data=form_data_to_pass) 

@main_bp.route("/group/join/<int:group_id>", methods=["POST"])
@login_required
def join_group(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    user = User.query.get(session['user_id'])
    
    if user in group.members:
        flash("You are already a member of this group.", "info")
    else:
        group.members.append(user)
        db.session.commit()
        flash(f"Successfully joined '{group.group_name}'!", "success")
        if group.created_by_id != user.id: 
            create_notification(
                recipient_user_id=group.created_by_id,
                notif_type='user_joined_group',
                content_dict={'user_name': user.name, 'user_id': user.id, 'group_name': group.group_name, 'group_id': group.id},
                link=url_for('main.view_group', group_id=group.id, _external=True) 
            )
    return redirect(url_for('main.view_group', group_id=group_id))

@main_bp.route("/group/leave/<int:group_id>", methods=["POST"])
@login_required
def leave_group(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    user = User.query.get(session['user_id'])

    if user in group.members:
        group.members.remove(user)
        message = f"You have left '{group.group_name}'."
        if not group.members:
            message += " The group is now empty."
        db.session.commit()
        flash(message, "success")
    else:
        flash("You are not a member of this group.", "info")
    return redirect(url_for('main.list_groups'))

@main_bp.route("/find-partner")
@login_required
def find_partner():
    user_id = session['user_id']
    try:
        current_user = User.query.get_or_404(user_id)
        potential_partners = User.query.filter(
            User.id != user_id, 
            func.lower(User.subject) == func.lower(current_user.subject)
        ).limit(100).all() 

        if len(potential_partners) < 1: 
            flash(f"Not enough potential partners studying '{current_user.subject}' found in the system at this time.", "info")
            return render_template("partner_results.html", matches=[], current_user_subject=current_user.subject)

        all_users_for_graph = [current_user] + potential_partners
        graph, user_map = build_user_graph(all_users_for_graph)

        if not graph or not user_map: 
            flash("Could not prepare data for partner matching. This might be due to very few users.", "warning")
            return redirect(url_for('main.dashboard'))

        distances = dijkstra_find_partners(graph, user_id)
        if distances is None: 
            flash("Partner matching algorithm encountered an issue. Please try again.", "danger")
            return redirect(url_for('main.dashboard'))

        sorted_partners = sorted(distances.items(), key=lambda item: item[1])
        top_matches_data = []
        for partner_id, distance in sorted_partners:
            if distance == float('inf'): continue 
            partner_user_obj = user_map.get(partner_id)
            if partner_user_obj: 
                top_matches_data.append({'user': partner_user_obj, 'compatibility_score': distance})
            if len(top_matches_data) >= 5: break 

        if not top_matches_data:
            flash("No compatible partners found based on the current criteria and your profile.", "info")
        return render_template("partner_results.html", matches=top_matches_data, current_user_subject=current_user.subject)

    except Exception as e:
        current_app.logger.error(f"Find Partner Error (User ID: {user_id}): {e}\n{traceback.format_exc()}")
        flash("An unexpected error occurred while trying to find partners.", "danger")
        return redirect(url_for('main.dashboard'))

@main_bp.route("/suggest-groups")
@login_required
def suggest_groups():
    user_id = session['user_id']
    try:
        current_user = User.query.get_or_404(user_id)
        users_to_cluster = User.query.filter(func.lower(User.subject) == func.lower(current_user.subject))\
                                  .limit(200).all() 

        num_users = len(users_to_cluster)
        if num_users < 2:
            flash(f"Not enough users studying '{current_user.subject}' to suggest distinct groups.", "info")
            return render_template("group_suggestions.html", suggested_groups=[], current_user_subject=current_user.subject)
        
        k_ideal = num_users // 3 
        k = min(5, max(2, k_ideal if k_ideal >= 2 else 2))
        k = min(k, num_users) 

        clusters_of_ids = kmeans_cluster_users(users_to_cluster, k=k)
        if clusters_of_ids is None:
            flash("Group suggestion algorithm failed. Please check server logs or ensure dependencies are installed.", "warning")
            return redirect(url_for('main.dashboard'))

        suggested_groups_data = []
        user_map_for_kmeans = {u.id: u for u in users_to_cluster} 
        for cluster_ids in clusters_of_ids:
            if len(cluster_ids) > 1: 
                group_members = [user_map_for_kmeans.get(uid) for uid in cluster_ids if user_map_for_kmeans.get(uid)]
                if group_members:
                    suggested_groups_data.append(group_members)
        
        if not suggested_groups_data:
            flash("No distinct groups could be suggested by clustering at this time. Try finding partners individually.", "info")
        return render_template("group_suggestions.html", suggested_groups=suggested_groups_data, current_user_subject=current_user.subject)

    except Exception as e:
        current_app.logger.error(f"Suggest Groups Error (User ID: {user_id}): {e}\n{traceback.format_exc()}")
        flash("An error occurred while suggesting groups.", "danger")
        return redirect(url_for('main.dashboard'))


@main_bp.route("/chat/<string:chat_type>/<int:target_id>")
@login_required
def chat(chat_type, target_id):
    user_id = session['user_id']
    room_name, target_name, message_history_list = None, None, []

    try:
        if chat_type == 'user':
            partner = User.query.get(target_id)
            if partner and partner.id != user_id:
                ids = sorted([user_id, target_id])
                room_name = f"user_{ids[0]}_{ids[1]}"
                target_name = partner.name
            elif partner and partner.id == user_id:
                flash("You cannot open a chat with yourself.", "warning")
                return redirect(url_for('main.dashboard'))
            else: 
                flash(f"User with ID {target_id} not found.", "error")
                return redirect(url_for('main.dashboard')) 
                
        elif chat_type == 'group':
            group = StudyGroup.query.options(selectinload(StudyGroup.members)).get(target_id)
            if group:
                current_user_obj = User.query.get(user_id) 
                if current_user_obj and current_user_obj in group.members:
                    room_name = f"group_{target_id}"
                    target_name = group.group_name
                else: 
                    flash("You are not a member of this group or cannot access its chat.", "warning")
                    return redirect(url_for('main.view_group', group_id=target_id))
            else: 
                flash(f"Group with ID {target_id} not found.", "error")
                return redirect(url_for('main.list_groups'))
        else:
            flash("Invalid chat type specified.", "error")
            return redirect(url_for('main.dashboard'))
        
        if room_name:
            limit = 50 
            query = None
            if chat_type == 'user':
                ids = sorted([user_id, target_id]) 
                query = Message.query.options(joinedload(Message.author))\
                    .filter(Message.group_id.is_(None)) \
                    .filter(((Message.sender_id == ids[0]) & (Message.recipient_id == ids[1])) | \
                           ((Message.sender_id == ids[1]) & (Message.recipient_id == ids[0])))
            elif chat_type == 'group':
                query = Message.query.options(joinedload(Message.author))\
                    .filter_by(group_id=target_id)
            
            if query: 
                message_history_list = query.order_by(Message.timestamp.asc()).limit(limit).all()

    except Exception as e:
        current_app.logger.error(f"Chat Page Loading Error (User: {user_id}, Type: {chat_type}, Target: {target_id}): {e}\n{traceback.format_exc()}")
        flash("An error occurred while trying to load the chat page.", "danger")
        return redirect(url_for('main.dashboard')) 
        
    return render_template("chat.html", room_name=room_name, target_name=target_name, message_history=message_history_list)



@main_bp.route("/notifications")
@login_required
def view_notifications():
    user_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    
    notifications_query = Notification.query.filter_by(user_id=user_id)\
                                           .order_by(Notification.is_read.asc(), Notification.created_at.desc())
    notifications_pagination = notifications_query.paginate(page=page, per_page=10, error_out=False)
    
    notifications_for_template = []
    for notif_obj in notifications_pagination.items:
        content_data = {}
        if notif_obj.content:
            try:
                content_data = json.loads(notif_obj.content)
            except json.JSONDecodeError:
                current_app.logger.error(f"JSONDecodeError for notification ID {notif_obj.id}: Content was '{notif_obj.content}'")
        notifications_for_template.append({'obj': notif_obj, 'content_data': content_data})
    return render_template("notifications.html", 
                           notifications_page=notifications_for_template, 
                           pagination=notifications_pagination)

@main_bp.route("/notifications/mark-read/<int:notification_id>", methods=["POST", "GET"]) 
@login_required
def mark_notification_read(notification_id):
    user_id = session['user_id']
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first_or_404()
        
    if not notification.is_read:
        notification.is_read = True
        db.session.commit()
        if request.method == "POST": 
            flash("Notification marked as read.", "info")
    
        unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        session['unread_notifications'] = unread_count
    
    next_url_from_form = request.form.get('next_url') 
    next_url_from_args = request.args.get('next_url') 
    next_url = next_url_from_form or next_url_from_args or request.referrer or url_for('main.view_notifications')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect(url_for('main.view_notifications'))


@main_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user_id = session['user_id']
    try:
        updated_count = db.session.query(Notification).filter_by(user_id=user_id, is_read=False)\
                                      .update({'is_read': True}, synchronize_session=False) 
        db.session.commit()
        session['unread_notifications'] = 0 
        if updated_count > 0:
            flash(f"{updated_count} notification(s) marked as read.", "success")
        else:
            flash("No unread notifications to mark.", "info")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking all notifications read for user {user_id}: {e}")
        flash("An error occurred while trying to mark all notifications as read.", "danger")
    return redirect(url_for('main.view_notifications'))