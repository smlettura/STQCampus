<div align="center">

# STQCampus

**Plataforma web de gestión psicosocial y convivencia escolar**

Proyecto de título · Ingeniería en Informática · Inacap La Serena

</div>

---

## Descripción

STQCampus es una plataforma web que centraliza la gestión psicosocial y de convivencia escolar de un establecimiento educacional: registro de atenciones, fichas de estudiantes, conflictos, protocolos, anotaciones e indicadores de bienestar.

El sistema está pensado para el equipo de convivencia escolar y psicología, e incluye apoyo de inteligencia artificial para redactar borradores de informes a partir de las atenciones registradas.

> **Estado del proyecto:** rediseño de interfaz terminado (16 pantallas en un prototipo navegable). El modelo de datos y el desarrollo del backend están en preparación.

## Capturas

| Inicio de sesión | Atención psicosocial |
|---|---|
| ![Inicio de sesión](imagenes/1_General/01_Inicio_de_sesion.png) | ![Panel principal](imagenes/1_General/02_Atencion_psicosocial.png) |

| Registro de atención | Generar informe con IA |
|---|---|
| ![Registrar atención](imagenes/1_General/03_Registrar_atencion.png) | ![Generar informe](imagenes/1_General/04_Generar_informe.png) |

| Lista de estudiantes | Anotaciones |
|---|---|
| ![Lista de estudiantes](imagenes/2_Estudiantes/01_Lista_de_estudiantes.png) | ![Anotaciones](imagenes/3_Convivencia/02_Anotaciones.png) |

## Módulos

**Gestión de estudiantes**
- Lista de estudiantes con filtros por estado, curso y programa (PIE, prioritario)
- Registro individual e importación masiva desde Excel
- Cursos agrupados por nivel, promoción de fin de año en tres pasos y egresados

**Atención psicosocial**
- Registro de atenciones con motivo, tipo, nivel de urgencia, descripción y acuerdos
- Generación de informes asistida por IA: se accede desde el menú de acciones de cada
  estudiante, permite elegir qué atenciones incluir y entrega un borrador que el
  profesional revisa, edita y firma antes de guardarlo en la ficha
- Fichas de estudiantes y estadísticas

**Convivencia escolar**
- Conflictos y mediaciones
- Protocolos de actuación
- Anotaciones por curso y situación conductual
- Plan de gestión de convivencia e indicadores de bienestar

## Decisiones de diseño

- Menú lateral único con submenús por módulo, en reemplazo de la navegación por pestañas
- Acciones de cada fila agrupadas en un botón "Ver ficha" y un menú, en lugar de íconos de colores sin texto
- Filtros de año, mes y curso en una barra fija, iguales en todos los módulos
- Indicadores y gráficos al inicio de cada módulo
- Paleta de alto contraste y datos de ejemplo anonimizados

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python · Django |
| Base de datos | MySQL 8 (InnoDB, utf8mb4) |
| Frontend | Plantillas Django · HTML · CSS |
| Prototipo | HTML estático (carpeta `pantallas/`) |

## Estructura del repositorio

```
.
├── index.html        # Índice del prototipo navegable
├── pantallas/        # Las 16 pantallas del prototipo en HTML
│   └── fuentes/      # Tipografías incluidas
└── imagenes/         # Capturas de cada pantalla
    ├── 1_General/      # Login, panel principal, atención, informe y perfil
    ├── 2_Estudiantes/  # Lista, registro, cursos, promoción y egresados
    └── 3_Convivencia/  # Conflictos, anotaciones, conducta, protocolos, plan e indicadores
```

## Cómo ver el prototipo

1. Clona o descarga el repositorio.
2. Abre la carpeta en Visual Studio Code.
3. Clic derecho sobre `index.html` → **Open with Live Server**.

También puedes abrir `index.html` directamente en el navegador con doble clic. El menú lateral está enlazado, así que se puede recorrer el sistema completo como en la aplicación real.

## Instalación del sistema (en preparación)

```bash
# Clonar el repositorio
git clone https://github.com/smlettura/Plataforma-STQ-v1.git
cd Plataforma-STQ-v1

# Entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS y Linux

# Dependencias
pip install -r requirements.txt

# Variables de entorno
copy .env.example .env       # y completar los datos de conexión

# Base de datos y ejecución
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Protección de datos

El sistema maneja datos personales sensibles de estudiantes, por lo que considera:

- Acceso restringido por roles y registro de auditoría de las acciones
- Datos de prueba anonimizados en el repositorio: no se incluyen nombres, RUT ni información real de estudiantes
- Informes de IA entregados siempre como borrador, sujetos a revisión y firma profesional
- Respaldos periódicos de la base de datos
- Tratamiento de datos conforme a la Ley 21.719 sobre protección de datos personales

## Autores

- Simón Andrés Martí Lettura — [@smlettura](https://github.com/smlettura)
- Diego Vicente Martí Lettura
- Eric Mauricio Torres Mardones

## Licencia

Proyecto académico de uso restringido. El escudo y la identidad visual del establecimiento son propiedad del colegio y se utilizan con su autorización.
