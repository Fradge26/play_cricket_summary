from flask import Flask, render_template, request
import os
from play_cricket_summary_generator import generate_graphic_for_flask

IMAGE_FOLDER = os.path.join("static")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = IMAGE_FOLDER


@app.route("/")
def home():
    return render_template("index_first.html")


@app.route("/graphic", methods=["POST"])
def graphic():
    match_id = request.form["user_input"]
    graphic_filename = generate_graphic_for_flask(match_id)
    full_filename = os.path.join(app.config["UPLOAD_FOLDER"], graphic_filename)
    return render_template("index.html", user_image=full_filename)


if __name__ == "__main__":
    app.run(debug=True, port=5555)
