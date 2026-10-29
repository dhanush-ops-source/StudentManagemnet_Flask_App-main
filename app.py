from flask import Flask
 
from config import Config
from extensions import mysql
from routes.student_routes import student_bp
 
app = Flask(__name__, template_folder="Templates")
 
# Load configuration
app.config.from_object(Config)
 
# Initialize MySQL with Flask
mysql.init_app(app)
 
# Register student routes
app.register_blueprint(student_bp)
 
 
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)