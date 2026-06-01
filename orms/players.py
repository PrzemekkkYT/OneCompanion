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

    # Data migration from jsonc
    jsonc_file = Path("./data/ids.jsonc")
    if not jsonc_file.exists():
        # Fallback if script is run from inside the orms directory
        jsonc_file = Path("../data/ids.jsonc")

    if jsonc_file.exists():
        with open(jsonc_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find numbers and optional comments on the same line
        # Handles formats like: "349152501, // ajatolla" or "349430905 // Luciopazz"
        pattern = re.compile(r"^\s*(\d+)\s*,?\s*(?://\s*(.*))?$", re.MULTILINE)

        records = []
        for match in pattern.finditer(content):
            player_id = int(match.group(1))
            name = match.group(2)
            name = name.strip() if name else None
            records.append({"player_id": player_id, "name": name})

        if records:
            with database.atomic():
                Players.insert_many(records).on_conflict_ignore().execute()

            print(f"Successfully migrated {len(records)} player IDs into the database.")
    else:
        print("Could not find ids.jsonc to migrate data.")
