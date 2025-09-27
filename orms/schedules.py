from pathlib import Path
from peewee import (
    SqliteDatabase,
    Model,
    IntegerField,
    TextField,
    BareField,
    AutoField,
)

database = SqliteDatabase("./database/schedules.db")


class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(Model):
    class Meta:
        database = database


class Messages(BaseModel):
    id = AutoField()
    title = TextField(null=False)
    guild_id = IntegerField(null=False)
    interval = IntegerField(null=False)
    channel_id = IntegerField(null=False)
    initial_datetime = IntegerField(null=False)
    next_post = IntegerField(null=False)
    content = TextField(null=True)
    image = TextField(null=True)
    mention = IntegerField(null=True)
    is_active = IntegerField(null=True)

    class Meta:
        table_name = "messages"


class ScheduledForToday(BaseModel):
    id = IntegerField(null=False)
    next_post = IntegerField(null=False)
    is_active = IntegerField(null=True)

    class Meta:
        table_name = "ScheduledForToday"


class ScheduledEventNotifications(BaseModel):
    event_id = IntegerField(null=False, unique=True, primary_key=True)
    guild_id = IntegerField(null=False)
    event_time = IntegerField(null=False)
    channel_id = IntegerField(null=False)
    role_id = IntegerField(null=True)
    noti_5m = IntegerField(null=True)
    noti_10m = IntegerField(null=True)
    noti_15m = IntegerField(null=True)
    noti_30m = IntegerField(null=True)
    noti_custom = IntegerField(null=True)

    class Meta:
        table_name = "ScheduledEventNotifications"


class ScheduledEventRecurrence(BaseModel):
    event_id = IntegerField(null=False, unique=True, primary_key=True)
    recurrence_rule = TextField(null=False)

    class Meta:
        table_name = "ScheduledEventRecurrence"


class SqliteSequence(BaseModel):
    name = BareField(null=True)
    seq = BareField(null=True)

    class Meta:
        table_name = "sqlite_sequence"
        primary_key = False


if __name__ == "__main__":
    db_path = Path("./database/schedules.db")
    if not db_path.is_file():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.open("w+").close()

    Messages.create_table()
    ScheduledForToday.create_table()
    ScheduledEventNotifications.create_table()
    ScheduledEventRecurrence.create_table()
