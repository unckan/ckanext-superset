import pytest


@pytest.fixture
def superset_migrate(migrate_db_for):
    # Migrar la base de datos de Superset
    migrate_db_for('superset')
    return True
