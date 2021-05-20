# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/rehkloos/)

<p><a href="https://heroku.com/deploy" rel="nofollow"><img src="https://camo.githubusercontent.com/c0824806f5221ebb7d25e559568582dd39dd1170/68747470733a2f2f7777772e6865726f6b7563646e2e636f6d2f6465706c6f792f627574746f6e2e706e67" alt="Deploy to Heroku" data-canonical-src="https://www.herokucdn.com/deploy/button.png" style="max-width:100%;"></a></p>

## Current Endpoints

All endpoints are relative to https://vlrggapi.herokuapp.com.

### `/news`

- Method: `GET`
- Cached Time: 300 seconds (5 Minutes)
- Response:
  ```python
  {
      "data": {
          "status": 200,
          'segments': [
              {
                  'title': str,
                  'description': str,
                  'date': str,
                  'author': str,
                  'url_path': str
              }
          ],
      }
  }
  ```

## Installation

### Source

```
$ git clone https://github.com/rehkloos/vlrggapi/
$ cd vlrggapi
$ pip3 install -r requirements.txt
```

### Usage

```
python3 main.py
```

## Built With

- [Flask](https://flask.palletsprojects.com/en/1.1.x/)
- [Requests](https://requests.readthedocs.io/en/master/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- [Flask-Caching](https://github.com/sh4nks/flask-caching)
- [gunicorn](https://gunicorn.org/)

## Contributing

Feel free to submit a [pull request](https://github.com/rehkloos/vlrggapi/pull/new/master) or an [issue](https://github.com/rehkloos/vlrggapi/issues/new)!

## License

The MIT License (MIT)
