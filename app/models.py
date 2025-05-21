from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, UTC
import json

user_group_association = db.Table('user_group_association',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('study_group.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    availability = db.Column(db.String(100), nullable=False)
    preference = db.Column(db.String(100), nullable=True)

    created_groups = db.relationship('StudyGroup', backref='creator', lazy=True, foreign_keys='StudyGroup.created_by_id')
    member_of_groups = db.relationship('StudyGroup', secondary=user_group_association, lazy='subquery',backref=db.backref('members', lazy=True))

    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='author', lazy='dynamic')

    def __repr__(self):
        return f'<User id={self.id} name={self.name} email={self.email}>'

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        else:
            self.password_hash = None

    def check_password(self, password):
        if not self.password_hash or not password:
             return False
        return check_password_hash(self.password_hash, password)

class StudyGroup(db.Model):
    __tablename__ = 'study_group'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False, index=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    messages = db.relationship('Message', backref='group', lazy='dynamic', foreign_keys='Message.group_id')

    def __repr__(self):
        return f'<StudyGroup id={self.id} name={self.group_name} subject={self.subject}>'

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=True, index=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(UTC))

    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_direct_messages')

    def __repr__(self):
        target = f"User {self.recipient_id}" if self.recipient_id else f"Group {self.group_id}"
        return f'<Message id={self.id} from={self.sender_id} to={target} time={self.timestamp}>'

class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False, index=True)
    content = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, index=True, default=lambda: datetime.now(UTC))

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic', order_by="desc(Notification.created_at)"))

    def __repr__(self):
        return f'<Notification id={self.id} user_id={self.user_id} type={self.type} read={self.is_read}>'
