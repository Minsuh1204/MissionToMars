from datetime import datetime

from flask import Flask, render_template, request, jsonify

from MarsTime import ltst_from_utc_lon, _hhmmss

app = Flask(__name__)


@app.route("/")
def homepage():
    return render_template("home.html")


@app.route("/api/mars_time", methods=["POST"])
def get_mars_time_for_station():
    data = request.get_json()
    earth_time: datetime = datetime.fromisoformat(data["earth_time"])
    longitude: float = float(data["lon"])
    mars_time: float = ltst_from_utc_lon(earth_time, longitude)
    return jsonify(ltst=_hhmmss(mars_time))


if __name__ == "__main__":
    app.run(debug=True, port=8080)
