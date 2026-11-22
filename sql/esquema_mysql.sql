-- =====================================================================================================================
-- Plataforma de Bienestar Psicológico Estudiantil — esquema MySQL 8 (solo estructura, sin datos)
-- Generado desde las migraciones de Django con mysqldump --no-data. Es de REFERENCIA: la forma recomendada de crear
-- la base es `python manage.py migrate` (ver README). Si lo usa directamente:
--   mysql -u root -p < sql/00_crear_bd_y_usuarios.sql
--   mysql -u bienestar_migra -p bienestar < sql/esquema_mysql.sql
-- Las columnas LONGBLOB (salvo fragmento_normativo.embedding) guardan texto cifrado con AES-256-GCM por la aplicación:
-- notas y acuerdos de atenciones, motivos de derivación, hitos, nombres de archivos adjuntos, tipo de NEE, diagnósticos,
-- aportes, adecuaciones y detalle de planes, informes, anotaciones, situación conductual, conflictos, protocolos,
-- relatos y gestiones de alertas, contenido de IA y el secreto del segundo factor. La base nunca ve ese texto en claro.
-- La bitácora `evento_auditoria` es de solo inserción: al final se otorgan permisos mínimos al usuario de aplicación.
-- =====================================================================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE `actividad_plan` (
  `id_actividad` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(12) NOT NULL,
  `titulo` varchar(160) NOT NULL,
  `fecha` date NOT NULL,
  `medio_verificacion` varchar(160) NOT NULL,
  `descripcion` longtext NOT NULL,
  `estado` varchar(10) NOT NULL,
  `id_responsable` bigint NOT NULL,
  PRIMARY KEY (`id_actividad`),
  KEY `actividad_plan_id_responsable_259c835b_fk_usuario_id_usuario` (`id_responsable`),
  CONSTRAINT `actividad_plan_id_responsable_259c835b_fk_usuario_id_usuario` FOREIGN KEY (`id_responsable`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `alerta_riesgo` (
  `id_alerta` bigint NOT NULL AUTO_INCREMENT,
  `tipo_situacion` varchar(24) NOT NULL,
  `subtipo_violencia` varchar(24) NOT NULL,
  `descripcion` longblob NOT NULL,
  `fecha_hora_conocimiento` datetime(6) NOT NULL,
  `fecha_hora_registro` datetime(6) NOT NULL,
  `posible_delito` tinyint(1) NOT NULL,
  `estado` varchar(12) NOT NULL,
  `id_caso` bigint DEFAULT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_informante` bigint NOT NULL,
  `id_sede` bigint NOT NULL,
  PRIMARY KEY (`id_alerta`),
  KEY `alerta_riesgo_id_caso_13e9558b_fk_caso_id_caso` (`id_caso`),
  KEY `alerta_riesgo_id_estudiante_fa16574a_fk_estudiante_id_estudiante` (`id_estudiante`),
  KEY `alerta_riesgo_id_informante_c5eb601c_fk_usuario_id_usuario` (`id_informante`),
  KEY `alerta_riesgo_id_sede_5f3c07bf_fk_sede_id_sede` (`id_sede`),
  CONSTRAINT `alerta_riesgo_id_caso_13e9558b_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `alerta_riesgo_id_estudiante_fa16574a_fk_estudiante_id_estudiante` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `alerta_riesgo_id_informante_c5eb601c_fk_usuario_id_usuario` FOREIGN KEY (`id_informante`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `alerta_riesgo_id_sede_5f3c07bf_fk_sede_id_sede` FOREIGN KEY (`id_sede`) REFERENCES `sede` (`id_sede`),
  CONSTRAINT `ck_alerta_conocimiento` CHECK ((`fecha_hora_conocimiento` <= `fecha_hora_registro`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `anotacion` (
  `id_anotacion` bigint NOT NULL AUTO_INCREMENT,
  `fecha` date NOT NULL,
  `tipo` varchar(10) NOT NULL,
  `descripcion` longblob NOT NULL,
  `registrada_en` datetime(6) NOT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_registrada_por` bigint NOT NULL,
  PRIMARY KEY (`id_anotacion`),
  KEY `anotacion_id_estudiante_2a79ec48_fk_estudiante_id_estudiante` (`id_estudiante`),
  KEY `anotacion_id_registrada_por_85bc1d90_fk_usuario_id_usuario` (`id_registrada_por`),
  CONSTRAINT `anotacion_id_estudiante_2a79ec48_fk_estudiante_id_estudiante` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `anotacion_id_registrada_por_85bc1d90_fk_usuario_id_usuario` FOREIGN KEY (`id_registrada_por`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `apoderado` (
  `id_apoderado` bigint NOT NULL AUTO_INCREMENT,
  `rut` varchar(12) DEFAULT NULL,
  `nombre_completo` varchar(120) NOT NULL,
  `telefono` varchar(20) NOT NULL,
  `correo` varchar(120) NOT NULL,
  PRIMARY KEY (`id_apoderado`),
  UNIQUE KEY `rut` (`rut`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `aviso_reevaluacion` (
  `id_aviso` bigint NOT NULL AUTO_INCREMENT,
  `fecha_programada` date NOT NULL,
  `fecha_envio` datetime(6) DEFAULT NULL,
  `estado` varchar(10) NOT NULL,
  `id_destinatario` bigint NOT NULL,
  `id_evaluacion` bigint NOT NULL,
  PRIMARY KEY (`id_aviso`),
  UNIQUE KEY `uq_aviso_destinatario` (`id_evaluacion`,`id_destinatario`),
  KEY `aviso_reevaluacion_id_destinatario_776c3fe5_fk_usuario_i` (`id_destinatario`),
  CONSTRAINT `aviso_reevaluacion_id_destinatario_776c3fe5_fk_usuario_i` FOREIGN KEY (`id_destinatario`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `aviso_reevaluacion_id_evaluacion_be956d5d_fk_evaluacio` FOREIGN KEY (`id_evaluacion`) REFERENCES `evaluacion_diagnostica` (`id_evaluacion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `caso` (
  `id_caso` bigint NOT NULL AUTO_INCREMENT,
  `tipo_proceso` varchar(12) NOT NULL,
  `tipo_atencion` varchar(40) NOT NULL,
  `estado` varchar(12) NOT NULL,
  `fecha_apertura` date NOT NULL,
  `fecha_cierre` date DEFAULT NULL,
  `fecha_fin_retencion` date DEFAULT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_responsable` bigint NOT NULL,
  PRIMARY KEY (`id_caso`),
  KEY `caso_id_estudiante_519cba84_fk_estudiante_id_estudiante` (`id_estudiante`),
  KEY `caso_id_responsable_0c8083ce_fk_usuario_id_usuario` (`id_responsable`),
  CONSTRAINT `caso_id_estudiante_519cba84_fk_estudiante_id_estudiante` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `caso_id_responsable_0c8083ce_fk_usuario_id_usuario` FOREIGN KEY (`id_responsable`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_caso_fechas` CHECK (((`fecha_cierre` is null) or (`fecha_cierre` >= `fecha_apertura`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `conflicto` (
  `id_conflicto` bigint NOT NULL AUTO_INCREMENT,
  `fecha` date NOT NULL,
  `tipo_gestion` varchar(12) NOT NULL,
  `descripcion` longblob NOT NULL,
  `acuerdos` longblob NOT NULL,
  `resultado` varchar(12) NOT NULL,
  `registrado_en` datetime(6) NOT NULL,
  `id_curso` bigint NOT NULL,
  `id_encargada` bigint NOT NULL,
  PRIMARY KEY (`id_conflicto`),
  KEY `conflicto_id_curso_5d54fc80_fk_curso_id_curso` (`id_curso`),
  KEY `conflicto_id_encargada_cf992ad7_fk_usuario_id_usuario` (`id_encargada`),
  CONSTRAINT `conflicto_id_curso_5d54fc80_fk_curso_id_curso` FOREIGN KEY (`id_curso`) REFERENCES `curso` (`id_curso`),
  CONSTRAINT `conflicto_id_encargada_cf992ad7_fk_usuario_id_usuario` FOREIGN KEY (`id_encargada`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `conflicto_participante` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `conflicto_id` bigint NOT NULL,
  `estudiante_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `conflicto_participante_conflicto_id_estudiante_id_6b7a7632_uniq` (`conflicto_id`,`estudiante_id`),
  KEY `conflicto_participan_estudiante_id_9b7f4eef_fk_estudiant` (`estudiante_id`),
  CONSTRAINT `conflicto_participan_conflicto_id_2a7cdd7a_fk_conflicto` FOREIGN KEY (`conflicto_id`) REFERENCES `conflicto` (`id_conflicto`),
  CONSTRAINT `conflicto_participan_estudiante_id_9b7f4eef_fk_estudiant` FOREIGN KEY (`estudiante_id`) REFERENCES `estudiante` (`id_estudiante`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `consentimiento` (
  `id_consentimiento` bigint NOT NULL AUTO_INCREMENT,
  `alcance` varchar(160) NOT NULL,
  `fecha_otorgamiento` date NOT NULL,
  `fecha_revocacion` date DEFAULT NULL,
  `id_apoderado` bigint NOT NULL,
  `id_documento` bigint DEFAULT NULL,
  `id_estudiante` bigint NOT NULL,
  PRIMARY KEY (`id_consentimiento`),
  KEY `consentimiento_id_apoderado_c1654df5_fk_apoderado_id_apoderado` (`id_apoderado`),
  KEY `consentimiento_id_documento_1759e130_fk_documento_id_documento` (`id_documento`),
  KEY `consentimiento_id_estudiante_2fa80fd3_fk_estudiant` (`id_estudiante`),
  CONSTRAINT `consentimiento_id_apoderado_c1654df5_fk_apoderado_id_apoderado` FOREIGN KEY (`id_apoderado`) REFERENCES `apoderado` (`id_apoderado`),
  CONSTRAINT `consentimiento_id_documento_1759e130_fk_documento_id_documento` FOREIGN KEY (`id_documento`) REFERENCES `documento` (`id_documento`),
  CONSTRAINT `consentimiento_id_estudiante_2fa80fd3_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `ck_consentimiento_fechas` CHECK (((`fecha_revocacion` is null) or (`fecha_revocacion` >= `fecha_otorgamiento`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `contenido_ia` (
  `id_contenido` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(20) NOT NULL,
  `modelo` varchar(60) NOT NULL,
  `texto_generado` longblob NOT NULL,
  `etiqueta_ia` tinyint(1) NOT NULL,
  `estado` varchar(12) NOT NULL,
  `fecha_generacion` datetime(6) NOT NULL,
  `fecha_validacion` datetime(6) DEFAULT NULL,
  `id_caso` bigint NOT NULL,
  `id_solicitante` bigint NOT NULL,
  `id_validador` bigint DEFAULT NULL,
  PRIMARY KEY (`id_contenido`),
  KEY `contenido_ia_id_caso_a390bc35_fk_caso_id_caso` (`id_caso`),
  KEY `contenido_ia_id_solicitante_3f7b6769_fk_usuario_id_usuario` (`id_solicitante`),
  KEY `contenido_ia_id_validador_1bcc6358_fk_usuario_id_usuario` (`id_validador`),
  CONSTRAINT `contenido_ia_id_caso_a390bc35_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `contenido_ia_id_solicitante_3f7b6769_fk_usuario_id_usuario` FOREIGN KEY (`id_solicitante`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `contenido_ia_id_validador_1bcc6358_fk_usuario_id_usuario` FOREIGN KEY (`id_validador`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_contenido_ia_validacion` CHECK (((`estado` <> _utf8mb4'validado') or ((`id_validador` is not null) and (`fecha_validacion` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `contenido_ia_fuente` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `relevancia` decimal(4,3) NOT NULL,
  `id_contenido` bigint NOT NULL,
  `id_fragmento` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_contenido_fuente` (`id_contenido`,`id_fragmento`),
  KEY `contenido_ia_fuente_id_fragmento_a1622bcb_fk_fragmento` (`id_fragmento`),
  CONSTRAINT `contenido_ia_fuente_id_contenido_805802e9_fk_contenido` FOREIGN KEY (`id_contenido`) REFERENCES `contenido_ia` (`id_contenido`),
  CONSTRAINT `contenido_ia_fuente_id_fragmento_a1622bcb_fk_fragmento` FOREIGN KEY (`id_fragmento`) REFERENCES `fragmento_normativo` (`id_fragmento`),
  CONSTRAINT `ck_fuente_relevancia` CHECK (((`relevancia` >= 0) and (`relevancia` <= 1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `curso` (
  `id_curso` bigint NOT NULL AUTO_INCREMENT,
  `nivel` varchar(20) NOT NULL,
  `letra` varchar(1) NOT NULL,
  `anio_escolar` smallint unsigned NOT NULL,
  `id_profesor_jefe` bigint DEFAULT NULL,
  `id_sede` bigint NOT NULL,
  PRIMARY KEY (`id_curso`),
  UNIQUE KEY `uq_curso` (`id_sede`,`nivel`,`letra`,`anio_escolar`),
  KEY `curso_id_profesor_jefe_7e2d1ef0_fk_usuario_id_usuario` (`id_profesor_jefe`),
  CONSTRAINT `curso_id_profesor_jefe_7e2d1ef0_fk_usuario_id_usuario` FOREIGN KEY (`id_profesor_jefe`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `curso_id_sede_87f01c56_fk_sede_id_sede` FOREIGN KEY (`id_sede`) REFERENCES `sede` (`id_sede`),
  CONSTRAINT `ck_curso_anio` CHECK (((`anio_escolar` >= 2000) and (`anio_escolar` <= 2100))),
  CONSTRAINT `curso_chk_1` CHECK ((`anio_escolar` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `denuncia` (
  `id_denuncia` bigint NOT NULL AUTO_INCREMENT,
  `institucion` varchar(20) NOT NULL,
  `fecha_hora_presentacion` datetime(6) NOT NULL,
  `numero_parte` varchar(40) NOT NULL,
  `directora_informada_en` datetime(6) NOT NULL,
  `hash_constancia` varchar(64) NOT NULL,
  `id_alerta` bigint NOT NULL,
  `id_psicologa` bigint NOT NULL,
  PRIMARY KEY (`id_denuncia`),
  UNIQUE KEY `hash_constancia` (`hash_constancia`),
  UNIQUE KEY `id_alerta` (`id_alerta`),
  KEY `denuncia_id_psicologa_0dec97f3_fk_usuario_id_usuario` (`id_psicologa`),
  CONSTRAINT `denuncia_id_alerta_877c9d6c_fk_alerta_riesgo_id_alerta` FOREIGN KEY (`id_alerta`) REFERENCES `alerta_riesgo` (`id_alerta`),
  CONSTRAINT `denuncia_id_psicologa_0dec97f3_fk_usuario_id_usuario` FOREIGN KEY (`id_psicologa`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `derivacion` (
  `id_derivacion` bigint NOT NULL AUTO_INCREMENT,
  `fecha_hora` datetime(6) NOT NULL,
  `motivo` longblob NOT NULL,
  `id_caso` bigint DEFAULT NULL,
  `id_derivante` bigint NOT NULL,
  `id_estudiante` bigint NOT NULL,
  PRIMARY KEY (`id_derivacion`),
  KEY `derivacion_id_caso_b90cff88_fk_caso_id_caso` (`id_caso`),
  KEY `derivacion_id_derivante_def5edc0_fk_usuario_id_usuario` (`id_derivante`),
  KEY `derivacion_id_estudiante_bf95d0e3_fk_estudiante_id_estudiante` (`id_estudiante`),
  CONSTRAINT `derivacion_id_caso_b90cff88_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `derivacion_id_derivante_def5edc0_fk_usuario_id_usuario` FOREIGN KEY (`id_derivante`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `derivacion_id_estudiante_bf95d0e3_fk_estudiante_id_estudiante` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `documento` (
  `id_documento` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(20) NOT NULL,
  `nombre_archivo` longblob NOT NULL,
  `ruta_objeto` varchar(255) NOT NULL,
  `hash_sha256` varchar(64) NOT NULL,
  `fecha_carga` datetime(6) NOT NULL,
  `id_caso` bigint NOT NULL,
  PRIMARY KEY (`id_documento`),
  UNIQUE KEY `ruta_objeto` (`ruta_objeto`),
  KEY `documento_id_caso_f80f0fb0_fk_caso_id_caso` (`id_caso`),
  CONSTRAINT `documento_id_caso_f80f0fb0_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `documento_normativo` (
  `id_documento_norm` bigint NOT NULL AUTO_INCREMENT,
  `titulo` varchar(200) NOT NULL,
  `tipo` varchar(30) NOT NULL,
  `fuente` varchar(255) NOT NULL,
  `version` varchar(20) NOT NULL,
  `fecha_vigencia` date NOT NULL,
  `vigente` tinyint(1) NOT NULL,
  PRIMARY KEY (`id_documento_norm`),
  UNIQUE KEY `uq_documento_normativo_version` (`titulo`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `estudiante` (
  `id_estudiante` bigint NOT NULL AUTO_INCREMENT,
  `rut` varchar(12) NOT NULL,
  `primer_nombre` varchar(40) NOT NULL,
  `segundo_nombre` varchar(40) NOT NULL,
  `apellido_paterno` varchar(40) NOT NULL,
  `apellido_materno` varchar(40) NOT NULL,
  `nombre_social` varchar(80) NOT NULL,
  `fecha_nacimiento` date NOT NULL,
  `fecha_ingreso` date DEFAULT NULL,
  `necesidad_educativa` varchar(12) NOT NULL,
  `en_pie` tinyint(1) NOT NULL,
  `prioritario` tinyint(1) NOT NULL,
  `matricula_condicional` tinyint(1) NOT NULL,
  `fecha_egreso` date DEFAULT NULL,
  `tipo_salida` varchar(8) NOT NULL,
  `id_curso` bigint NOT NULL,
  PRIMARY KEY (`id_estudiante`),
  UNIQUE KEY `rut` (`rut`),
  KEY `estudiante_id_curso_dff46e55_fk_curso_id_curso` (`id_curso`),
  CONSTRAINT `estudiante_id_curso_dff46e55_fk_curso_id_curso` FOREIGN KEY (`id_curso`) REFERENCES `curso` (`id_curso`),
  CONSTRAINT `ck_estudiante_egreso` CHECK (((`fecha_egreso` is null) or (`fecha_egreso` > `fecha_nacimiento`))),
  CONSTRAINT `ck_estudiante_salida` CHECK ((((`fecha_egreso` is null) and (`tipo_salida` = _utf8mb4'')) or ((`fecha_egreso` is not null) and (`tipo_salida` <> _utf8mb4''))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `estudiante_apoderado` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `parentesco` varchar(30) NOT NULL,
  `es_titular` tinyint(1) NOT NULL,
  `id_apoderado` bigint NOT NULL,
  `id_estudiante` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_estudiante_apoderado` (`id_estudiante`,`id_apoderado`),
  KEY `estudiante_apoderado_id_apoderado_ff20bda4_fk_apoderado` (`id_apoderado`),
  CONSTRAINT `estudiante_apoderado_id_apoderado_ff20bda4_fk_apoderado` FOREIGN KEY (`id_apoderado`) REFERENCES `apoderado` (`id_apoderado`),
  CONSTRAINT `estudiante_apoderado_id_estudiante_25e1106a_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `evaluacion_diagnostica` (
  `id_evaluacion` bigint NOT NULL AUTO_INCREMENT,
  `tipo_evaluacion` varchar(12) NOT NULL,
  `tipo_nee` longblob NOT NULL,
  `diagnostico` longblob NOT NULL,
  `fecha_evaluacion` date NOT NULL,
  `fecha_reevaluacion` date DEFAULT NULL,
  `estado` varchar(12) NOT NULL,
  `id_caso` bigint NOT NULL,
  PRIMARY KEY (`id_evaluacion`),
  KEY `evaluacion_diagnostica_id_caso_4a25910f_fk_caso_id_caso` (`id_caso`),
  CONSTRAINT `evaluacion_diagnostica_id_caso_4a25910f_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `ck_evaluacion_reevaluacion` CHECK (((`fecha_reevaluacion` is null) or (`fecha_reevaluacion` > `fecha_evaluacion`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `evento_auditoria` (
  `id_evento` bigint NOT NULL AUTO_INCREMENT,
  `fecha_hora` datetime(6) NOT NULL,
  `accion` varchar(20) NOT NULL,
  `entidad` varchar(40) NOT NULL,
  `id_entidad` bigint DEFAULT NULL,
  `detalle` varchar(255) NOT NULL,
  `ip_origen` varchar(45) NOT NULL,
  `hash_previo` varchar(64) NOT NULL,
  `hash_evento` varchar(64) NOT NULL,
  `id_usuario` bigint DEFAULT NULL,
  PRIMARY KEY (`id_evento`),
  UNIQUE KEY `hash_evento` (`hash_evento`),
  KEY `evento_auditoria_id_usuario_200e4480_fk_usuario_id_usuario` (`id_usuario`),
  KEY `evento_auditoria_fecha_hora_4d291949` (`fecha_hora`),
  CONSTRAINT `evento_auditoria_id_usuario_200e4480_fk_usuario_id_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `evidencia_actividad` (
  `id_evidencia` bigint NOT NULL AUTO_INCREMENT,
  `nombre_archivo` longblob NOT NULL,
  `ruta_objeto` varchar(255) NOT NULL,
  `hash_sha256` varchar(64) NOT NULL,
  `fecha_carga` datetime(6) NOT NULL,
  `id_actividad` bigint NOT NULL,
  `id_subida_por` bigint NOT NULL,
  PRIMARY KEY (`id_evidencia`),
  UNIQUE KEY `ruta_objeto` (`ruta_objeto`),
  KEY `evidencia_actividad_id_actividad_2b0fc70f_fk_actividad` (`id_actividad`),
  KEY `evidencia_actividad_id_subida_por_ddd4d808_fk_usuario_id_usuario` (`id_subida_por`),
  CONSTRAINT `evidencia_actividad_id_actividad_2b0fc70f_fk_actividad` FOREIGN KEY (`id_actividad`) REFERENCES `actividad_plan` (`id_actividad`),
  CONSTRAINT `evidencia_actividad_id_subida_por_ddd4d808_fk_usuario_id_usuario` FOREIGN KEY (`id_subida_por`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `fragmento_normativo` (
  `id_fragmento` bigint NOT NULL AUTO_INCREMENT,
  `seccion` varchar(120) NOT NULL,
  `texto` longtext NOT NULL,
  `embedding` longblob NOT NULL,
  `id_documento_norm` bigint NOT NULL,
  PRIMARY KEY (`id_fragmento`),
  KEY `fragmento_normativo_id_documento_norm_f5e48848_fk_documento` (`id_documento_norm`),
  CONSTRAINT `fragmento_normativo_id_documento_norm_f5e48848_fk_documento` FOREIGN KEY (`id_documento_norm`) REFERENCES `documento_normativo` (`id_documento_norm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `gestion_alerta` (
  `id_gestion` bigint NOT NULL AUTO_INCREMENT,
  `accion` varchar(20) NOT NULL,
  `detalle` longblob NOT NULL,
  `fecha_hora` datetime(6) NOT NULL,
  `id_alerta` bigint NOT NULL,
  `id_responsable` bigint NOT NULL,
  PRIMARY KEY (`id_gestion`),
  KEY `gestion_alerta_id_alerta_56552cfb_fk_alerta_riesgo_id_alerta` (`id_alerta`),
  KEY `gestion_alerta_id_responsable_0f6d8dba_fk_usuario_id_usuario` (`id_responsable`),
  CONSTRAINT `gestion_alerta_id_alerta_56552cfb_fk_alerta_riesgo_id_alerta` FOREIGN KEY (`id_alerta`) REFERENCES `alerta_riesgo` (`id_alerta`),
  CONSTRAINT `gestion_alerta_id_responsable_0f6d8dba_fk_usuario_id_usuario` FOREIGN KEY (`id_responsable`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `hito` (
  `id_hito` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(20) NOT NULL,
  `descripcion` longblob NOT NULL,
  `fecha` date NOT NULL,
  `visible_profesor_jefe` tinyint(1) NOT NULL,
  `id_caso` bigint NOT NULL,
  PRIMARY KEY (`id_hito`),
  KEY `hito_id_caso_83608595_fk_caso_id_caso` (`id_caso`),
  CONSTRAINT `hito_id_caso_83608595_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `informe` (
  `id_informe` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(20) NOT NULL,
  `contenido` longblob NOT NULL,
  `estado` varchar(10) NOT NULL,
  `fecha_entrega` date DEFAULT NULL,
  `id_caso` bigint NOT NULL,
  `id_contenido_ia` bigint DEFAULT NULL,
  PRIMARY KEY (`id_informe`),
  UNIQUE KEY `id_contenido_ia` (`id_contenido_ia`),
  KEY `informe_id_caso_06c6b365_fk_caso_id_caso` (`id_caso`),
  CONSTRAINT `informe_id_caso_06c6b365_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `informe_id_contenido_ia_d70a9b69_fk_contenido_ia_id_contenido` FOREIGN KEY (`id_contenido_ia`) REFERENCES `contenido_ia` (`id_contenido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `llamada_modelo` (
  `id_llamada` bigint NOT NULL AUTO_INCREMENT,
  `proveedor` varchar(40) NOT NULL,
  `modelo` varchar(60) NOT NULL,
  `tokens_entrada` int unsigned NOT NULL,
  `tokens_salida` int unsigned NOT NULL,
  `hash_carga` varchar(64) NOT NULL,
  `fecha_hora` datetime(6) NOT NULL,
  `id_contenido` bigint NOT NULL,
  PRIMARY KEY (`id_llamada`),
  KEY `llamada_modelo_id_contenido_47d5fbfd_fk_contenido` (`id_contenido`),
  CONSTRAINT `llamada_modelo_id_contenido_47d5fbfd_fk_contenido` FOREIGN KEY (`id_contenido`) REFERENCES `contenido_ia` (`id_contenido`),
  CONSTRAINT `llamada_modelo_chk_1` CHECK ((`tokens_entrada` >= 0)),
  CONSTRAINT `llamada_modelo_chk_2` CHECK ((`tokens_salida` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `notificacion` (
  `id_notificacion` bigint NOT NULL AUTO_INCREMENT,
  `canal` varchar(10) NOT NULL,
  `fecha_hora_envio` datetime(6) NOT NULL,
  `fecha_hora_lectura` datetime(6) DEFAULT NULL,
  `hash_constancia` varchar(64) NOT NULL,
  `id_alerta` bigint NOT NULL,
  `id_destinatario` bigint NOT NULL,
  PRIMARY KEY (`id_notificacion`),
  UNIQUE KEY `hash_constancia` (`hash_constancia`),
  KEY `notificacion_id_alerta_3da89d76_fk_alerta_riesgo_id_alerta` (`id_alerta`),
  KEY `notificacion_id_destinatario_e04fb966_fk_usuario_id_usuario` (`id_destinatario`),
  CONSTRAINT `notificacion_id_alerta_3da89d76_fk_alerta_riesgo_id_alerta` FOREIGN KEY (`id_alerta`) REFERENCES `alerta_riesgo` (`id_alerta`),
  CONSTRAINT `notificacion_id_destinatario_e04fb966_fk_usuario_id_usuario` FOREIGN KEY (`id_destinatario`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `participacion_evaluacion` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `rol_profesional` varchar(40) NOT NULL,
  `aporte` longblob NOT NULL,
  `fecha` date NOT NULL,
  `id_evaluacion` bigint NOT NULL,
  `id_usuario` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_participacion` (`id_evaluacion`,`id_usuario`),
  KEY `participacion_evalua_id_usuario_713a4977_fk_usuario_i` (`id_usuario`),
  CONSTRAINT `participacion_evalua_id_evaluacion_4a158a19_fk_evaluacio` FOREIGN KEY (`id_evaluacion`) REFERENCES `evaluacion_diagnostica` (`id_evaluacion`),
  CONSTRAINT `participacion_evalua_id_usuario_713a4977_fk_usuario_i` FOREIGN KEY (`id_usuario`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `permiso` (
  `id_permiso` bigint NOT NULL AUTO_INCREMENT,
  `codigo` varchar(60) NOT NULL,
  `descripcion` varchar(160) NOT NULL,
  PRIMARY KEY (`id_permiso`),
  UNIQUE KEY `codigo` (`codigo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `plan_apoyo` (
  `id_plan` bigint NOT NULL AUTO_INCREMENT,
  `tipo` varchar(4) NOT NULL,
  `adecuaciones` longblob NOT NULL,
  `detalle` longblob NOT NULL,
  `fecha_inicio` date NOT NULL,
  `fecha_termino` date DEFAULT NULL,
  `estado` varchar(8) NOT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_evaluacion` bigint DEFAULT NULL,
  PRIMARY KEY (`id_plan`),
  KEY `plan_apoyo_id_estudiante_2947a1b1_fk_estudiante_id_estudiante` (`id_estudiante`),
  KEY `plan_apoyo_id_evaluacion_bea1d661_fk_evaluacio` (`id_evaluacion`),
  CONSTRAINT `plan_apoyo_id_estudiante_2947a1b1_fk_estudiante_id_estudiante` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `plan_apoyo_id_evaluacion_bea1d661_fk_evaluacio` FOREIGN KEY (`id_evaluacion`) REFERENCES `evaluacion_diagnostica` (`id_evaluacion`),
  CONSTRAINT `ck_plan_fechas` CHECK (((`fecha_termino` is null) or (`fecha_termino` >= `fecha_inicio`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `proceso_curso_terminal` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `procesopromocion_id` bigint NOT NULL,
  `curso_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `proceso_curso_terminal_procesopromocion_id_curs_0958a582_uniq` (`procesopromocion_id`,`curso_id`),
  KEY `proceso_curso_terminal_curso_id_95aad0fe_fk_curso_id_curso` (`curso_id`),
  CONSTRAINT `proceso_curso_termin_procesopromocion_id_8dd2c893_fk_proceso_p` FOREIGN KEY (`procesopromocion_id`) REFERENCES `proceso_promocion` (`id_proceso`),
  CONSTRAINT `proceso_curso_terminal_curso_id_95aad0fe_fk_curso_id_curso` FOREIGN KEY (`curso_id`) REFERENCES `curso` (`id_curso`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `proceso_promocion` (
  `id_proceso` bigint NOT NULL AUTO_INCREMENT,
  `anio` smallint unsigned NOT NULL,
  `estado` varchar(10) NOT NULL,
  `fecha_proceso` datetime(6) DEFAULT NULL,
  `id_procesado_por` bigint DEFAULT NULL,
  PRIMARY KEY (`id_proceso`),
  UNIQUE KEY `anio` (`anio`),
  KEY `proceso_promocion_id_procesado_por_74eb6604_fk_usuario_i` (`id_procesado_por`),
  CONSTRAINT `proceso_promocion_id_procesado_por_74eb6604_fk_usuario_i` FOREIGN KEY (`id_procesado_por`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `proceso_promocion_chk_1` CHECK ((`anio` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `promocion_estudiante` (
  `id_promocion` bigint NOT NULL AUTO_INCREMENT,
  `resultado` varchar(10) NOT NULL,
  `id_curso_destino` bigint DEFAULT NULL,
  `id_curso_origen` bigint NOT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_proceso` bigint NOT NULL,
  PRIMARY KEY (`id_promocion`),
  UNIQUE KEY `uq_promocion_estudiante` (`id_proceso`,`id_estudiante`),
  KEY `promocion_estudiante_id_curso_destino_78f76aa9_fk_curso_id_curso` (`id_curso_destino`),
  KEY `promocion_estudiante_id_curso_origen_68d43bad_fk_curso_id_curso` (`id_curso_origen`),
  KEY `promocion_estudiante_id_estudiante_9b26039c_fk_estudiant` (`id_estudiante`),
  CONSTRAINT `promocion_estudiante_id_curso_destino_78f76aa9_fk_curso_id_curso` FOREIGN KEY (`id_curso_destino`) REFERENCES `curso` (`id_curso`),
  CONSTRAINT `promocion_estudiante_id_curso_origen_68d43bad_fk_curso_id_curso` FOREIGN KEY (`id_curso_origen`) REFERENCES `curso` (`id_curso`),
  CONSTRAINT `promocion_estudiante_id_estudiante_9b26039c_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `promocion_estudiante_id_proceso_56d25c2c_fk_proceso_p` FOREIGN KEY (`id_proceso`) REFERENCES `proceso_promocion` (`id_proceso`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `protocolo_activado` (
  `id_protocolo` bigint NOT NULL AUTO_INCREMENT,
  `protocolo` varchar(20) NOT NULL,
  `fecha_activacion` date NOT NULL,
  `estado` varchar(8) NOT NULL,
  `fecha_cierre` date DEFAULT NULL,
  `observaciones` longblob NOT NULL,
  `id_alerta` bigint DEFAULT NULL,
  `id_curso` bigint NOT NULL,
  `id_estudiante` bigint DEFAULT NULL,
  `id_responsable` bigint NOT NULL,
  PRIMARY KEY (`id_protocolo`),
  KEY `protocolo_activado_id_alerta_5e5ef95c_fk_alerta_riesgo_id_alerta` (`id_alerta`),
  KEY `protocolo_activado_id_curso_3e2101c7_fk_curso_id_curso` (`id_curso`),
  KEY `protocolo_activado_id_estudiante_bfc977e7_fk_estudiant` (`id_estudiante`),
  KEY `protocolo_activado_id_responsable_f36fa0cc_fk_usuario_id_usuario` (`id_responsable`),
  CONSTRAINT `protocolo_activado_id_alerta_5e5ef95c_fk_alerta_riesgo_id_alerta` FOREIGN KEY (`id_alerta`) REFERENCES `alerta_riesgo` (`id_alerta`),
  CONSTRAINT `protocolo_activado_id_curso_3e2101c7_fk_curso_id_curso` FOREIGN KEY (`id_curso`) REFERENCES `curso` (`id_curso`),
  CONSTRAINT `protocolo_activado_id_estudiante_bfc977e7_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `protocolo_activado_id_responsable_f36fa0cc_fk_usuario_id_usuario` FOREIGN KEY (`id_responsable`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_protocolo_fechas` CHECK (((`fecha_cierre` is null) or (`fecha_cierre` >= `fecha_activacion`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `registro_conductual` (
  `id_registro` bigint NOT NULL AUTO_INCREMENT,
  `fecha` date NOT NULL,
  `categoria` varchar(10) NOT NULL,
  `descripcion` longblob NOT NULL,
  `porcentaje_asistencia` decimal(5,1) DEFAULT NULL,
  `registrado_en` datetime(6) NOT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_registrado_por` bigint NOT NULL,
  PRIMARY KEY (`id_registro`),
  KEY `registro_conductual_id_estudiante_3e1807ba_fk_estudiant` (`id_estudiante`),
  KEY `registro_conductual_id_registrado_por_1b54fccd_fk_usuario_i` (`id_registrado_por`),
  CONSTRAINT `registro_conductual_id_estudiante_3e1807ba_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `registro_conductual_id_registrado_por_1b54fccd_fk_usuario_i` FOREIGN KEY (`id_registrado_por`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_registro_asistencia` CHECK (((`porcentaje_asistencia` is null) or ((`porcentaje_asistencia` >= 0) and (`porcentaje_asistencia` <= 100))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `regla_enrutamiento` (
  `id_regla` bigint NOT NULL AUTO_INCREMENT,
  `tipo_situacion` varchar(24) NOT NULL,
  `subtipo_violencia` varchar(24) NOT NULL,
  `vigente` tinyint(1) NOT NULL,
  `id_rol_responsable` bigint NOT NULL,
  `id_sede` bigint DEFAULT NULL,
  PRIMARY KEY (`id_regla`),
  UNIQUE KEY `uq_regla_enrutamiento` (`tipo_situacion`,`subtipo_violencia`,`id_sede`,`id_rol_responsable`),
  KEY `regla_enrutamiento_id_rol_responsable_a7539985_fk_rol_id_rol` (`id_rol_responsable`),
  KEY `regla_enrutamiento_id_sede_9a76ef9e_fk_sede_id_sede` (`id_sede`),
  CONSTRAINT `regla_enrutamiento_id_rol_responsable_a7539985_fk_rol_id_rol` FOREIGN KEY (`id_rol_responsable`) REFERENCES `rol` (`id_rol`),
  CONSTRAINT `regla_enrutamiento_id_sede_9a76ef9e_fk_sede_id_sede` FOREIGN KEY (`id_sede`) REFERENCES `sede` (`id_sede`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `retencion_eliminacion` (
  `id_retencion` bigint NOT NULL AUTO_INCREMENT,
  `fecha_vencimiento` date NOT NULL,
  `accion` varchar(10) NOT NULL,
  `estado` varchar(10) NOT NULL,
  `fecha_autorizacion` datetime(6) DEFAULT NULL,
  `fecha_ejecucion` datetime(6) DEFAULT NULL,
  `id_autorizada_por` bigint DEFAULT NULL,
  `id_estudiante` bigint DEFAULT NULL,
  PRIMARY KEY (`id_retencion`),
  KEY `retencion_eliminacio_id_autorizada_por_76d2d906_fk_usuario_i` (`id_autorizada_por`),
  KEY `retencion_eliminacio_id_estudiante_69aa817a_fk_estudiant` (`id_estudiante`),
  CONSTRAINT `retencion_eliminacio_id_autorizada_por_76d2d906_fk_usuario_i` FOREIGN KEY (`id_autorizada_por`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `retencion_eliminacio_id_estudiante_69aa817a_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `ck_retencion_autorizacion` CHECK (((`estado` not in (_utf8mb4'autorizada',_utf8mb4'ejecutada')) or ((`id_autorizada_por` is not null) and (`fecha_autorizacion` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `retroalimentacion_ia` (
  `id_retro` bigint NOT NULL AUTO_INCREMENT,
  `motivo` varchar(12) NOT NULL,
  `comentario` longblob NOT NULL,
  `fecha_hora` datetime(6) NOT NULL,
  `id_contenido` bigint NOT NULL,
  `id_profesional` bigint NOT NULL,
  PRIMARY KEY (`id_retro`),
  KEY `retroalimentacion_ia_id_contenido_a9b87650_fk_contenido` (`id_contenido`),
  KEY `retroalimentacion_ia_id_profesional_0c6c3456_fk_usuario_i` (`id_profesional`),
  CONSTRAINT `retroalimentacion_ia_id_contenido_a9b87650_fk_contenido` FOREIGN KEY (`id_contenido`) REFERENCES `contenido_ia` (`id_contenido`),
  CONSTRAINT `retroalimentacion_ia_id_profesional_0c6c3456_fk_usuario_i` FOREIGN KEY (`id_profesional`) REFERENCES `usuario` (`id_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `rol` (
  `id_rol` bigint NOT NULL AUTO_INCREMENT,
  `codigo` varchar(40) NOT NULL,
  `nombre` varchar(40) NOT NULL,
  `descripcion` varchar(160) NOT NULL,
  PRIMARY KEY (`id_rol`),
  UNIQUE KEY `codigo` (`codigo`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `rol_permiso` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `id_permiso` bigint NOT NULL,
  `id_rol` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rol_permiso` (`id_rol`,`id_permiso`),
  KEY `rol_permiso_id_permiso_3b981607_fk_permiso_id_permiso` (`id_permiso`),
  CONSTRAINT `rol_permiso_id_permiso_3b981607_fk_permiso_id_permiso` FOREIGN KEY (`id_permiso`) REFERENCES `permiso` (`id_permiso`),
  CONSTRAINT `rol_permiso_id_rol_b01f6b5b_fk_rol_id_rol` FOREIGN KEY (`id_rol`) REFERENCES `rol` (`id_rol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `sede` (
  `id_sede` bigint NOT NULL AUTO_INCREMENT,
  `nombre` varchar(60) NOT NULL,
  `direccion` varchar(160) NOT NULL,
  PRIMARY KEY (`id_sede`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `sesion_seguimiento` (
  `id_sesion` bigint NOT NULL AUTO_INCREMENT,
  `fecha_hora` datetime(6) NOT NULL,
  `duracion_minutos` smallint unsigned NOT NULL,
  `tipo_atencion` varchar(10) NOT NULL,
  `urgencia` varchar(5) NOT NULL,
  `motivo` varchar(24) NOT NULL,
  `derivado_por` varchar(16) NOT NULL,
  `nota` longblob NOT NULL,
  `acuerdos` longblob NOT NULL,
  `nivel_acceso` varchar(10) NOT NULL,
  `estado` varchar(10) NOT NULL,
  `id_caso` bigint NOT NULL,
  `id_profesional` bigint NOT NULL,
  PRIMARY KEY (`id_sesion`),
  KEY `sesion_seguimiento_id_caso_d78e25ee_fk_caso_id_caso` (`id_caso`),
  KEY `sesion_seguimiento_id_profesional_ada8e131_fk_usuario_id_usuario` (`id_profesional`),
  CONSTRAINT `sesion_seguimiento_id_caso_d78e25ee_fk_caso_id_caso` FOREIGN KEY (`id_caso`) REFERENCES `caso` (`id_caso`),
  CONSTRAINT `sesion_seguimiento_id_profesional_ada8e131_fk_usuario_id_usuario` FOREIGN KEY (`id_profesional`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `sesion_seguimiento_chk_1` CHECK ((`duracion_minutos` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `solicitud_arco` (
  `id_solicitud` bigint NOT NULL AUTO_INCREMENT,
  `tipo_derecho` varchar(14) NOT NULL,
  `fecha_recepcion` date NOT NULL,
  `fecha_limite` date NOT NULL,
  `estado` varchar(12) NOT NULL,
  `fecha_respuesta` date DEFAULT NULL,
  `id_apoderado` bigint NOT NULL,
  `id_estudiante` bigint NOT NULL,
  `id_responsable` bigint NOT NULL,
  PRIMARY KEY (`id_solicitud`),
  KEY `solicitud_arco_id_apoderado_f989d5c9_fk_apoderado_id_apoderado` (`id_apoderado`),
  KEY `solicitud_arco_id_estudiante_84746d4a_fk_estudiant` (`id_estudiante`),
  KEY `solicitud_arco_id_responsable_f0db1ab2_fk_usuario_id_usuario` (`id_responsable`),
  CONSTRAINT `solicitud_arco_id_apoderado_f989d5c9_fk_apoderado_id_apoderado` FOREIGN KEY (`id_apoderado`) REFERENCES `apoderado` (`id_apoderado`),
  CONSTRAINT `solicitud_arco_id_estudiante_84746d4a_fk_estudiant` FOREIGN KEY (`id_estudiante`) REFERENCES `estudiante` (`id_estudiante`),
  CONSTRAINT `solicitud_arco_id_responsable_f0db1ab2_fk_usuario_id_usuario` FOREIGN KEY (`id_responsable`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_arco_limite` CHECK ((`fecha_limite` >= `fecha_recepcion`)),
  CONSTRAINT `ck_arco_respuesta` CHECK (((`fecha_respuesta` is null) or (`fecha_respuesta` >= `fecha_recepcion`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `usuario` (
  `id_usuario` bigint NOT NULL AUTO_INCREMENT,
  `correo` varchar(120) NOT NULL,
  `nombre_completo` varchar(120) NOT NULL,
  `hash_contrasena` varchar(255) NOT NULL,
  `secreto_totp` longblob,
  `mfa_activo` tinyint(1) NOT NULL,
  `activo` tinyint(1) NOT NULL,
  `ultimo_acceso` datetime(6) DEFAULT NULL,
  `telefono` varchar(20) NOT NULL,
  `especialidad` varchar(80) NOT NULL,
  `fecha_alta` datetime(6) NOT NULL,
  `contrasena_actualizada` datetime(6) DEFAULT NULL,
  `cambio_contrasena_pendiente` tinyint(1) NOT NULL,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `correo` (`correo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `usuario_rol` (
  `id_usuario_rol` bigint NOT NULL AUTO_INCREMENT,
  `vigente_desde` date NOT NULL,
  `vigente_hasta` date DEFAULT NULL,
  `id_rol` bigint NOT NULL,
  `id_sede` bigint DEFAULT NULL,
  `id_usuario` bigint NOT NULL,
  PRIMARY KEY (`id_usuario_rol`),
  KEY `usuario_rol_id_rol_5fb37218_fk_rol_id_rol` (`id_rol`),
  KEY `usuario_rol_id_sede_8751f702_fk_sede_id_sede` (`id_sede`),
  KEY `usuario_rol_id_usuario_72047234_fk_usuario_id_usuario` (`id_usuario`),
  CONSTRAINT `usuario_rol_id_rol_5fb37218_fk_rol_id_rol` FOREIGN KEY (`id_rol`) REFERENCES `rol` (`id_rol`),
  CONSTRAINT `usuario_rol_id_sede_8751f702_fk_sede_id_sede` FOREIGN KEY (`id_sede`) REFERENCES `sede` (`id_sede`),
  CONSTRAINT `usuario_rol_id_usuario_72047234_fk_usuario_id_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `usuario` (`id_usuario`),
  CONSTRAINT `ck_usuario_rol_vigencia` CHECK (((`vigente_hasta` is null) or (`vigente_hasta` >= `vigente_desde`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------------------------------------------------------
-- Permisos mínimos del usuario de la aplicación (equivale a `python manage.py permisos_bd --aplicar`).
-- Ejecutar como bienestar_migra, que tiene GRANT OPTION sobre la base `bienestar`.
-- ---------------------------------------------------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`actividad_plan` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`alerta_riesgo` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`anotacion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`apoderado` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`auth_group` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`auth_group_permissions` TO 'bienestar_app'@'%';
GRANT SELECT ON `bienestar`.`auth_permission` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`aviso_reevaluacion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`caso` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`conflicto` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`conflicto_participante` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`consentimiento` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`contenido_ia` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`contenido_ia_fuente` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`curso` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`denuncia` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`derivacion` TO 'bienestar_app'@'%';
GRANT SELECT ON `bienestar`.`django_content_type` TO 'bienestar_app'@'%';
GRANT SELECT ON `bienestar`.`django_migrations` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`django_session` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`documento` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`documento_normativo` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`estudiante` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`estudiante_apoderado` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`evaluacion_diagnostica` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT ON `bienestar`.`evento_auditoria` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`evidencia_actividad` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`fragmento_normativo` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`gestion_alerta` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`hito` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`informe` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`llamada_modelo` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`notificacion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`participacion_evaluacion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`permiso` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`plan_apoyo` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`proceso_curso_terminal` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`proceso_promocion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`promocion_estudiante` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`protocolo_activado` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`registro_conductual` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`regla_enrutamiento` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`retencion_eliminacion` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`retroalimentacion_ia` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`rol` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`rol_permiso` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`sede` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`sesion_seguimiento` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`solicitud_arco` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`usuario` TO 'bienestar_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON `bienestar`.`usuario_rol` TO 'bienestar_app'@'%';

-- Caché compartida entre los trabajadores de Gunicorn (antirrepetición del segundo factor y bloqueos por intentos).
-- La crea la migración core.0002_cache_compartida (createcachetable); no es una tabla del modelo de datos.
CREATE TABLE `cache_compartida` (
  `cache_key` varchar(255) NOT NULL,
  `value` longtext NOT NULL,
  `expires` datetime(6) NOT NULL,
  PRIMARY KEY (`cache_key`),
  KEY `cache_compartida_expires` (`expires`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
