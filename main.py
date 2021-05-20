from flask import Flask, current_app, jsonify
from flask_cors import CORS
from flask_caching import Cache
import ujson as json
from ratelimit import limits
from api.scrape import Vlr

app = Flask(__name__)
cache = Cache(app, config={"CACHE_TYPE": "simple"})
CORS(app)
vlr = Vlr()

TEN_MINUTES = 600


@app.route("/")
def home():
    return jsonify({"hello": "world"})


@limits(calls=50, period=TEN_MINUTES)
@cache.cached(timeout=300)
@app.route("/news", methods=["GET"])
def vlr_news():
    return current_app.response_class(
        json.dumps(vlr.vlr_recent(), indent=4, escape_forward_slashes=False),
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
