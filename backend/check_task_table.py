from sqlalchemy import inspect

from app.db.engine import engine

try:
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns(
            "ppt_tasks", schema="public"
        )
    }

    for name in ("outline_json", "artifact_path", "error_message"):
        column = columns[name]
        print(name, column["type"], "允许空：", column["nullable"])
finally:
    engine.dispose()