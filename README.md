<div align="center">

# Gestor de Vehículos

**Control de flota, solicitudes de uso y seguimiento vehicular con Odoo 18**

![Odoo](https://img.shields.io/badge/Odoo-18.0-714B67?style=flat)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)
![Licencia](https://img.shields.io/badge/Licencia-LGPL--3-green?style=flat)

Organiza el uso de los vehículos de una empresa, registra su estado y conserva su información en un solo lugar.

[Funciones](#funcionalidades) · [Instalación](#instalación-local) · [Uso](#guía-de-uso) · [Solución de problemas](#solución-de-problemas)

</div>

---

## Acerca del proyecto

Este repositorio distribuye el módulo personalizado **`control_vehiculos`** para **Odoo 18**, que amplía la aplicación de Flota con un flujo de solicitudes, aprobación, entrega, devolución y cierre de uso.

Permite a los administradores gestionar los vehículos y a los empleados solicitar su uso, conservando el historial de decisiones, inspecciones, documentos y costos.

| Dato | Valor |
| --- | --- |
| Módulo técnico | `control_vehiculos` |
| Versión del módulo | `18.0.1.1.0` |
| Plataforma requerida | Odoo Community 18.0 |
| Dependencias de Odoo | `fleet`, `mail`, `web` |
| Base de datos incluida en Compose | PostgreSQL 16 |
| Interfaz | Español |
| Licencia declarada del módulo | LGPL-3 |

## Funcionalidades

| Área | Funciones principales |
| --- | --- |
| Vehículos | Catálogo con fotografía, placa, marca, modelo, tipo, chasis, motor, capacidad y responsables. |
| Solicitudes | Destino, motivo y fechas; aprobación, rechazo y cancelación con seguimiento. |
| Entrega y devolución | Kilometraje, combustible, firmas, fotografías, observaciones e inspecciones. |
| Calendario | Consulta de solicitudes; componentes de disponibilidad semanal con reservas y mantenimientos. |
| Mantenimiento | Registro de trabajos, fechas, costos y estados de ejecución. |
| Documentos | Matrícula, seguro, revisión técnica, permisos y archivos adjuntos con control de vencimiento. |
| Multas | Registro de infracciones, relación con viajes e importación de citaciones ANT. |
| Costos | Modelos y cálculos de costos acumulados, mensuales, anuales y por kilómetro. |
| ANT | Consulta por placa para completar datos e importar matrícula y citaciones. |
| Reportes | Carta de compromiso e informe de uso en PDF. |
| Recordatorios | Tareas programadas para llaves pendientes, multas y documentos por vencer. |

> Los menús principales son **Vehículos**, **Calendario**, **Solicitudes / Mis Solicitudes**, **Mantenimiento**, **Multas** y **Documentos**, según los permisos. Los archivos de costos y del panel semanal forman parte del módulo; no todos tienen un menú independiente en la configuración actual.

## Tecnologías y requisitos

- **Python 3.10 o superior**, según `setup.py`, con un entorno virtual.
- **PostgreSQL**; el archivo Compose utiliza la versión **16**.
- **Docker con Docker Compose**, si utilizas la base de datos incluida.
- **PowerShell**, para seguir esta guía en Windows.
- **JavaScript, XML y SCSS**, con componentes OWL de Odoo.
- **`python-docx`**, dependencia adicional declarada por el módulo.
- **ReportLab y Pillow**, para los documentos PDF y sus imágenes; incluidos en `odoo-source/requirements.txt`.

Docker ejecuta PostgreSQL. El servidor Odoo se ejecuta localmente con Python.

## Estructura del repositorio

```text
odoo-gestor_vehiculos/
├── odoo-source/                    # Código de Odoo descargado localmente (ignorado)
├── custom_addons/
│   └── control_vehiculos/
│       ├── __manifest__.py          # Dependencias, vistas y recursos
│       ├── models/                  # Modelos y reglas de negocio
│       ├── controllers/             # Formularios, consultas y descargas
│       ├── views/                   # Formularios, listas, calendario y menús
│       ├── security/                # Grupos, permisos y reglas por compañía
│       ├── services/                # Cliente ANT y su documentación
│       ├── reports/                 # Generación de documentos
│       ├── data/                    # Secuencias, tareas y plantillas
│       ├── static/src/              # Componentes JS, XML, estilos e imágenes
│       ├── migrations/              # Migraciones del módulo
│       └── wizard/                  # Paquete de asistentes
├── compose.postgres.yml             # Servicio PostgreSQL local
├── requirements.txt                 # Dependencias adicionales del módulo
├── .env.example                     # Variables de conexión de ejemplo
├── odoo.conf.example                # Configuración de ejemplo
├── odoo.conf                        # Configuración local; ignorada por Git
├── LICENSE
└── README.md
```

El asistente de motivos de rechazo y cancelación está definido en `models/vehicle_usage.py`. Los scripts temporales de diagnóstico y corrección no se incluyen en esta distribución.

## Instalación local

Clona el repositorio y descarga Odoo 18 en una carpeta independiente:

```powershell
git clone https://github.com/NoeliaMendoza/Odoo-Gestor-Vehiculos.git
cd Odoo-Gestor-Vehiculos
git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git odoo-source
```

Ejecuta los siguientes comandos desde la raíz de `Odoo-Gestor-Vehiculos`. El núcleo de Odoo se descarga por separado y no se incluye en este repositorio.

### 1. Preparar el entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r odoo-source/requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Se utiliza directamente el Python del entorno virtual, por lo que no necesitas activarlo en PowerShell.

### 2. Iniciar PostgreSQL

Copia las variables de ejemplo y define una contraseña local en `.env` antes de iniciar Docker:

```powershell
Copy-Item .env.example .env
```

Con Docker iniciado:

```powershell
docker compose -f compose.postgres.yml up -d
docker compose -f compose.postgres.yml ps
```

El servicio publica PostgreSQL en **`127.0.0.1:5433`** y conserva los datos en el volumen **`postgres16_data`**. Si ya tienes PostgreSQL instalado, ajusta la conexión del siguiente paso para utilizarlo.

### 3. Crear o ajustar `odoo.conf`

Copia la configuración de ejemplo:

```powershell
Copy-Item odoo.conf.example odoo.conf
```

Sustituye `addons_path` por las rutas de tu instalación. Obtén la raíz con:

```powershell
(Get-Location).Path
```

Ejemplo de configuración; reemplaza `C:\ruta\odoo-gestor_vehiculos` por esa ubicación:

```ini
[options]
addons_path = C:\ruta\odoo-gestor_vehiculos\odoo-source\odoo\addons,C:\ruta\odoo-gestor_vehiculos\odoo-source\addons,C:\ruta\odoo-gestor_vehiculos\custom_addons

db_host = 127.0.0.1
db_port = 5433
db_user = odoo
db_password = <contraseña POSTGRES_PASSWORD definida en .env>

admin_passwd = <tu contraseña maestra para administrar bases de datos>
http_port = 8069
```

Reemplaza los marcadores `<...>` antes de iniciar. La contraseña maestra administra bases de datos y es distinta de la contraseña del usuario que inicia sesión en Odoo.

### 4. Iniciar Odoo y crear la base de datos

```powershell
.\.venv\Scripts\python.exe odoo-source/odoo-bin -c odoo.conf
```

Abre **[http://localhost:8069](http://localhost:8069)** y utiliza el formulario inicial:

- **Contraseña maestra:** la definida en `admin_passwd`.
- **Nombre de la base:** por ejemplo, `gestor_vehiculos`.
- **Correo y contraseña:** las credenciales del administrador de Odoo.
- **Idioma:** español.
- **País:** Ecuador, si corresponde a tu entorno.

### 5. Instalar el módulo

1. Ingresa con el administrador de Odoo.
2. Activa el modo desarrollador desde **Ajustes**.
3. Abre **Aplicaciones** y actualiza la lista de aplicaciones.
4. Busca el módulo de gestión de vehículos; su identificador técnico es **`control_vehiculos`**.
5. Instálalo y asigna los permisos de flota a los usuarios.

Como alternativa, detén el servidor y ejecuta estos comandos sobre una base de datos ya creada:

```powershell
.\.venv\Scripts\python.exe odoo-source/odoo-bin -c odoo.conf -d gestor_vehiculos -i control_vehiculos --stop-after-init
.\.venv\Scripts\python.exe odoo-source/odoo-bin -c odoo.conf -d gestor_vehiculos
```

Reemplaza `gestor_vehiculos` si elegiste otro nombre para la base.

## Roles y permisos

| Perfil | Alcance principal |
| --- | --- |
| Empleado: catálogo y solicitudes propias | Consulta del catálogo y calendario; creación y edición de solicitudes propias según su estado. |
| Administrador de flota | Vehículos, revisión de solicitudes, entrega, devolución, cierre, mantenimientos, documentos, multas y consultas ANT. |

El grupo de empleados es **`control_vehiculos.group_assignment_driver`** y el administrador utiliza **`fleet.fleet_group_manager`**. Asigna los grupos desde la ficha del usuario en **Ajustes**.

Los registros de control incorporan reglas por compañía. Los empleados tienen una regla de lectura amplia para las solicitudes de las compañías permitidas; **Mis Solicitudes** filtra las propias en la interfaz. Las descargas documentales añaden verificaciones de acceso.

## Guía de uso

### 1. Registrar el vehículo

Desde **Gestión de Vehículos → Vehículos**, registra placa, marca, modelo, datos técnicos y responsables. Asigna un administrador de flota que pueda revisar las solicitudes. Completa fotografía, condición operativa y datos no proporcionados por ANT, como kilometraje y combustible.

### 2. Solicitar y aprobar el uso

El empleado selecciona el vehículo y registra destino, motivo y fechas. El administrador revisa la solicitud y la aprueba o rechaza. El rechazo y la cancelación se gestionan con un motivo.

```text
Pendiente → Aprobado → En Ruta → Devuelto → Cerrado
    └──→ Rechazado
```

La cancelación sigue las condiciones de estado y permisos del módulo. La aprobación comprueba la disponibilidad para evitar conflictos con reservas y mantenimientos.

### 3. Entregar el vehículo

Registra kilometraje, combustible e inspección de salida. La ficha permite añadir firmas, fotografías y observaciones.

La entrega exige **al menos 50 % de combustible** y un kilometraje mayor que cero que no sea inferior al último registrado del vehículo.

### 4. Registrar la devolución y cerrar

Completa kilometraje, combustible e inspección de regreso. El kilometraje no puede ser inferior al de salida. Al confirmar la devolución, se actualiza el odómetro.

Revisa diferencias, incidencias y costos antes del cierre. El módulo calcula distancia, duración y alertas por combustible bajo o daños nuevos.

### 5. Consultar documentos y reportes

- Registra matrícula, seguro, revisión técnica y permisos desde **Documentos**.
- La vigencia distingue **Vigente**, **Por vencer** —30 días o menos— y **Vencido**.
- Utiliza las acciones de descarga para obtener la carta de compromiso o el informe de uso.
- El informe de uso requiere que se haya registrado la devolución.

**Formato actual:** las descargas generan **PDF con ReportLab**. Hay plantillas `.docx`, utilidades de Word y métodos con nombres heredados; esos nombres no implican que la descarga actual sea un archivo Word.

## Integración con ANT

El módulo consulta información pública de la Agencia Nacional de Tránsito por placa para completar marca/modelo, año y color, y conservar matrícula, estado de cuenta y citaciones.

- Consulta automática al crear, si la opción está habilitada, o manual por el administrador.
- La matrícula con caducidad se integra en **Documentos**; las citaciones, en **Multas**.
- Las referencias externas evitan duplicados y permiten conservar adjuntos y notas.
- Una consulta fallida mantiene la información anterior. Si falla la consulta automática al crear, se conserva el vehículo y se muestra un aviso.
- Las citaciones no se atribuyen automáticamente al conductor actual.
- La ausencia de una citación en una consulta posterior no implica que esté pagada o anulada.

La integración lee un portal público y sus consultas JSON, y depende de su disponibilidad y formato. Consulta [la documentación del cliente ANT](custom_addons/control_vehiculos/services/README_ANT.md) para conocer los detalles y límites.

## Tareas programadas

| Tarea | Frecuencia configurada |
| --- | --- |
| Llaves pendientes de entrega o devolución | Diaria |
| Resumen de multas pendientes de pago | Semanal |
| Documentos por vencer o vencidos | Diaria |

Se declaran en `data/fine_data.xml` y pueden revisarse en las acciones planificadas de Odoo en modo desarrollador. Los correos externos requieren configurar el servidor de correo de Odoo.

## Desarrollo y actualización

Después de modificar modelos, permisos o vistas, detén el servidor y actualiza el módulo:

```powershell
.\.venv\Scripts\python.exe odoo-source/odoo-bin -c odoo.conf -d gestor_vehiculos -u control_vehiculos --stop-after-init
.\.venv\Scripts\python.exe odoo-source/odoo-bin -c odoo.conf -d gestor_vehiculos
```

Para revisar JavaScript y estilos, abre **[http://localhost:8069/web?debug=assets](http://localhost:8069/web?debug=assets)** y recarga el navegador.

### Comprobación funcional sugerida

1. Crear un vehículo y asignarle un administrador de flota.
2. Registrar una solicitud como empleado.
3. Aprobarla como administrador y comprobar la disponibilidad.
4. Registrar entrega con kilometraje y combustible válidos.
5. Registrar devolución, revisar el odómetro y cerrar el uso.
6. Descargar el PDF y comprobar sus datos.
7. Revisar permisos con ambos perfiles y consultar ANT si hay conexión.

La comprobación anterior es manual. Esta distribución no incluye una suite automatizada ni los scripts de diagnóstico y reparación usados durante el desarrollo.

## Solución de problemas

| Problema | Qué revisar |
| --- | --- |
| No aparece el módulo | Incluir `custom_addons` en `addons_path`, reiniciar y actualizar la lista de aplicaciones. |
| Error de conexión a PostgreSQL | Comprobar Docker, el servicio y los datos de conexión en `odoo.conf`. |
| Puerto incorrecto | El Compose publica **5433** en el equipo; **5432** es el puerto interno del contenedor. |
| `ModuleNotFoundError: docx` | Instalar `python-docx` con el Python del entorno virtual que ejecuta Odoo. |
| Falta `docxtpl` al ejecutar un script | Instalar `docxtpl` si necesitas esa utilidad; no forma parte del flujo actual de descargas PDF. |
| Cambios de vistas no visibles | Actualizar el módulo con `-u` y revisar los errores del servidor. |
| Estilos o JavaScript desactualizados | Abrir con `debug=assets` y realizar una recarga completa. |
| Menús o botones ausentes | Revisar los grupos del usuario y la compañía activa. |
| No se puede entregar | Revisar aprobación, kilometraje y combustible mínimo del 50 %. |
| No se puede descargar el informe | Confirmar la devolución y el permiso de acceso al documento. |
| Error de consulta ANT | Revisar la placa, conexión y aviso del módulo; la disponibilidad o el formato del portal pueden variar. |

Consultar registros de PostgreSQL:

```powershell
docker compose -f compose.postgres.yml logs --tail 100 postgres
```

Detener PostgreSQL conservando el volumen de datos:

```powershell
docker compose -f compose.postgres.yml stop
```

## Licencia y créditos

El módulo declara **LGPL-3** en su manifiesto. Odoo es desarrollado por Odoo S.A. y sus colaboradores y se instala por separado. Consulta [LICENSE](LICENSE) y los avisos de cada componente.

Los datos importados de ANT proceden de su portal público. Este proyecto constituye una integración independiente.
