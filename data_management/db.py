from surrealdb import Surreal

class DB():
    def __init__(self) -> None:
        with Surreal("ws://localhost:8080/rpc") as db:
            db.signin({"user": "root", "password" : "root"})
            db.use("vlr", "vlr")