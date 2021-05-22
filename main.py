from flask import Flask, current_app, render_template
from flask_cors import CORS
from flask_caching import Cache
import ujson as json
from ratelimit import limits
from api.scrape import Vlr

app = Flask(__name__, template_folder="frontpage")
cache = Cache(app, config={"CACHE_TYPE": "simple"})
CORS(app)
vlr = Vlr()

TEN_MINUTES = 600


@app.route("/")
def home():
    return render_template("index.html")


@limits(calls=50, period=TEN_MINUTES)
@cache.cached(timeout=300)
@app.route("/news", methods=["GET"])
def vlr_news():
    return current_app.response_class(
        json.dumps(vlr.vlr_recent(), indent=4, escape_forward_slashes=False),
        mimetype="application/json",
    )


@limits(calls=50, period=TEN_MINUTES)
@cache.cached(timeout=300)
@app.route("/match/results", methods=["GET"])
def vlr_scores():
    return current_app.response_class(
        json.dumps(vlr.vlr_score(), indent=4, escape_forward_slashes=False),
        mimetype="application/json",
    )


@limits(calls=50, period=TEN_MINUTES)
@cache.cached(timeout=300)
@app.route("/rankings/<region>", methods=["GET"])
def vlr_ranks(region):
    return current_app.response_class(
        json.dumps(vlr.vlr_rankings(region), indent=4, escape_forward_slashes=False),
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
