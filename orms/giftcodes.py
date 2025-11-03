from pathlib import Path
from peewee import (
    SqliteDatabase,
    Model,
    AutoField,
    IntegerField,
    TextField,
    BooleanField,
)

database = SqliteDatabase("./database/giftcodes.db")


class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(Model):
    class Meta:
        database = database


class GiftCodes(BaseModel):
    id = AutoField()
    code_line = TextField(null=False)
    active = BooleanField(default=True)

    class Meta:
        table_name = "GiftCodes"


class RedeemedCodes(BaseModel):
    id = AutoField()
    code_line = IntegerField(null=False)
    player_id = IntegerField(null=False)

    class Meta:
        table_name = "RedeemedCodes"


if __name__ == "__main__":
    db_path = Path("./database/giftcodes.db")
    if not db_path.is_file():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.open("w+").close()

    GiftCodes.create_table()
    RedeemedCodes.create_table()
