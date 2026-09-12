from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


@contextmanager
def checkpoint_saver(database_url: str, *, schema: str | None = None, setup: bool = False):
    options = {}
    if schema:
        if not schema.replace("_", "").isalnum():
            raise ValueError("Invalid checkpoint schema")
        options["options"] = f"-csearch_path={schema}"
    with psycopg.connect(database_url.replace("postgresql+psycopg://", "postgresql://", 1), autocommit=True, prepare_threshold=0, row_factory=dict_row, connect_timeout=5, **options) as connection:
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_json_modules=[], allowed_msgpack_modules=[("langgraph.types", "Interrupt"), ("langgraph.types", "Send")])
        saver = PostgresSaver(connection, serde=serde)
        if setup:
            saver.setup()
        yield saver


if __name__ == "__main__":
    import os
    with checkpoint_saver(os.environ["AGENT_DATABASE_URL"], setup=True):
        print("Agent PostgreSQL checkpoint migrations applied")
