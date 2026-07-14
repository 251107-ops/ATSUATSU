from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

skills = Blueprint('skills', __name__)

