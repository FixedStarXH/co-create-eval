from alembic import context
from sqlmodel import SQLModel

from app.config import database_url
from app.db import build_engine
from app import models  # noqa: F401 -- register SQLModel metadata

target_metadata = SQLModel.metadata

if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
