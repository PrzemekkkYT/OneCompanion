from pathlib import Path
from peewee import (
    SqliteDatabase,
    Model,
    IntegerField,
)

database = SqliteDatabase("./database/configs.db")


class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(Model):
    class Meta:
        database = database


class GuildConfigs(BaseModel):
    guild_id = IntegerField(null=False, unique=True, primary_key=True)
    translator_enabled = IntegerField(null=False, default=0)

    class Meta:
        table_name = "GuildConfigs"
        without_rowid = True


if __name__ == "__main__":
    db_path = Path("./database/configs.db")
    if not db_path.is_file():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.open("w+").close()

    GuildConfigs.create_table()
