-- src/chatddx/django/repo/sql/trail_triggers.sql
DROP TRIGGER IF EXISTS trg_protect_trail_{table_name} ON "{table_name}";

CREATE TRIGGER trg_protect_trail_{table_name}
BEFORE UPDATE OR DELETE ON "{table_name}"
FOR EACH ROW
EXECUTE FUNCTION protect_trail_{table_name}();
