-- src/chatddx/django/repo/sql/trail_functions.sql
CREATE OR REPLACE FUNCTION protect_trail_{table_name}()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Operation denied: Records with a fingerprint are immutable.';
END;
$$ LANGUAGE plpgsql;
