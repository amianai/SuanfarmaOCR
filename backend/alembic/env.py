from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import dei model e della config applicativa per usare lo stesso DB e metadata.
from app.core.config import settings
from app.core.db import Base
from app.models import chunk, collab, documento  # noqa: F401  (registra i model su Base.metadata)

config = context.config

# URL del DB preso dalla config dell'app (non dall'alembic.ini).
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


MANAGED_TABLES = {"documenti", "utenti", "preferiti_utente", "commenti", "eventi_audit", "chunks"}


def include_object(obj, name, type_, reflected, compare_to):
    """Alembic gestisce solo le tabelle applicative.

    Le tabelle/trigger FTS5 (documenti_fts, *_data, *_idx, *_docsize, *_config)
    sono gestite dai trigger SQLite e non devono finire nell'autogenerate.
    """
    if type_ == "table" and name not in MANAGED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
