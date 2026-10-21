\set ON_ERROR_STOP on

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'ppt_tasks';

SELECT version_num FROM migrations.alembic_version;

SELECT
    has_table_privilege('ppt_app', 'public.ppt_tasks', 'SELECT') AS can_read,
    has_table_privilege('ppt_app', 'public.ppt_tasks', 'INSERT') AS can_insert,
    has_table_privilege('ppt_app', 'public.ppt_tasks', 'UPDATE') AS can_update,
    has_table_privilege('ppt_app', 'public.ppt_tasks', 'DELETE') AS can_delete,
    has_schema_privilege('ppt_app', 'public', 'CREATE') AS can_change_structure,
    has_schema_privilege('ppt_app', 'migrations', 'USAGE') AS can_access_migrations;
