# Si mysqlclient no está instalado (por ejemplo, en Windows sin compilador), se usa PyMySQL como reemplazo.
try:  # pragma: no cover - depende del entorno
    import MySQLdb  # noqa: F401
except ImportError:  # pragma: no cover
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
