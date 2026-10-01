-- Base de datos local MySQL 8 para la Plataforma de Bienestar Psicológico Estudiantil.
-- Ejecutar una vez como administrador de MySQL:  mysql -u root -p < sql/00_crear_bd_y_usuarios.sql
-- Cambie las contraseñas antes de usarlo fuera de su equipo.

CREATE DATABASE IF NOT EXISTS bienestar CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Usuario propietario del esquema: ejecuta las migraciones y otorga los permisos del usuario de aplicación.
CREATE USER IF NOT EXISTS 'bienestar_migra'@'%' IDENTIFIED BY 'Cambiar_Migra_2026';
GRANT ALL PRIVILEGES ON bienestar.* TO 'bienestar_migra'@'%' WITH GRANT OPTION;
-- Solo para ejecutar las pruebas automáticas (Django crea y borra test_bienestar).
GRANT ALL PRIVILEGES ON test_bienestar.* TO 'bienestar_migra'@'%';

-- Usuario con el que corre la aplicación. Sus permisos se otorgan tabla por tabla después de migrar:
--   python manage.py permisos_bd --aplicar   (ejecutado con el usuario bienestar_migra)
-- Sobre evento_auditoria solo recibe SELECT e INSERT: la bitácora no se puede alterar desde la aplicación (RNF-03).
CREATE USER IF NOT EXISTS 'bienestar_app'@'%' IDENTIFIED BY 'Cambiar_App_2026';

FLUSH PRIVILEGES;
