from peewee import (
    SqliteDatabase,
    Model,
    IntegerField,
    TextField,
    ForeignKeyField,
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


class SqliteSequence(BaseModel):
    name = BareField(null=True)
    seq = BareField(null=True)

    class Meta:
        table_name = "sqlite_sequence"
        primary_key = False
