from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import settings
from app.db import Base
import app.models  # noqa: F401

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_online():
    # Built directly from settings.database_url via create_engine, not
    # config.set_main_option/engine_from_config — those round-trip the URL
    # through configparser, which treats a bare "%" (e.g. a percent-encoded
    # character in the DB password, like "%26" for "&") as invalid
    # interpolation syntax and raises. create_engine takes the raw string
    # as-is, sidestepping that entirely.
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
