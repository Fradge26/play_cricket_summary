from flask import Flask, render_template, request, jsonify, url_for
import os
from play_cricket_summary_generator import generate_graphic_for_flask

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join("static")


@app.route("/")
def home():
    return render_template("index_first.html")


@app.route("/graphic", methods=["POST"])
def graphic():
    match_id = request.form["match_id"]
    template_name = request.form["template_name"]
    print(request.form)
    graphic_filename = generate_graphic_for_flask(match_id, template_name)
    response_data = {'image_path': url_for("static", filename=graphic_filename)}
    return jsonify(response_data)


if __name__ == "__main__":
    app.run(debug=True, port=5555)
