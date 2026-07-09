from flask import Flask
from routes.auth import auth
from routes.posts import posts

app = Flask(__name__)
app.register_blueprint(auth)
app.register_blueprint(posts)

if __name__ == '__main__':
    app.run(debug=True)