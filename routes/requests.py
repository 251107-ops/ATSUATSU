from flask import Blueprint, render_template, redirect, session, request, url_for, jsonify
from routes.auth import get_db
from flask_socketio import emit, join_room, leave_room
import secrets
from flask import Flask
from flask_notifications import Notifications

requests = Blueprint('requests', __name__)

notifications = Notifications(requests=requests)

