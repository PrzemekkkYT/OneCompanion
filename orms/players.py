from pathlib import Path
import re
from peewee import (
    SqliteDatabase,
    Model,
    IntegerField,
    TextField,
)

database = SqliteDatabase("./database/players.db")


class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(Model):
    class Meta:
        database = database


class Players(BaseModel):
    player_id = IntegerField(unique=True, primary_key=True)
    player_state = IntegerField(null=False)
    name = TextField(null=True)

    class Meta:
        table_name = "Players"
        without_rowid = True


if __name__ == "__main__":
    db_path = Path("./database/players.db")
    if not db_path.is_file():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.open("w+").close()

    Players.create_table()
