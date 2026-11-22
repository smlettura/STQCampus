"""Operación de migración que cifra, en su lugar, una columna que antes guardaba texto plano.

Se usa junto con un AlterField a TextoCifrado: primero cambia el tipo de la columna (en MySQL, LONGTEXT a LONGBLOB conserva
los bytes UTF-8) y luego esta operación cifra cada valor con AES-256-GCM, usando como contexto «tabla.columna», igual que el
campo. Es idempotente: un valor que ya está cifrado no se vuelve a cifrar. La operación inversa descifra y deja texto plano.
"""
from django.db import migrations


def _filas(con, tabla, columna, pk):
    qn = con.ops.quote_name
    with con.cursor() as c:
        c.execute("SELECT %s, %s FROM %s" % (qn(pk), qn(columna), qn(tabla)))
        return c.fetchall()


def _guardar(con, tabla, columna, pk, id_fila, valor):
    qn = con.ops.quote_name
    with con.cursor() as c:
        c.execute("UPDATE %s SET %s = %%s WHERE %s = %%s" % (qn(tabla), qn(columna), qn(pk)), [valor, id_fila])


def cifrar_columna(tabla, columna, pk):
    contexto = "%s.%s" % (tabla, columna)

    def adelante(apps, schema_editor):
        from apps.core.cifrado import cifrar_texto, descifrar_texto
        con = schema_editor.connection
        for id_fila, valor in _filas(con, tabla, columna, pk):
            if valor is None:
                continue
            if isinstance(valor, (bytes, bytearray, memoryview)):
                valor = bytes(valor)
                try:
                    descifrar_texto(valor, contexto)
                    continue                                  # ya estaba cifrado
                except Exception:
                    valor = valor.decode("utf-8")
            _guardar(con, tabla, columna, pk, id_fila, cifrar_texto(valor, contexto))

    def atras(apps, schema_editor):
        from apps.core.cifrado import descifrar_texto
        con = schema_editor.connection
        for id_fila, valor in _filas(con, tabla, columna, pk):
            if isinstance(valor, (bytes, bytearray, memoryview)) and len(bytes(valor)):
                _guardar(con, tabla, columna, pk, id_fila, descifrar_texto(bytes(valor), contexto))

    return migrations.RunPython(adelante, atras, elidable=False)
