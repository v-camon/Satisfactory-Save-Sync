# Satisfactory Save Sync

Sistema integral de coordinación multijugador para partidas compartidas de *Satisfactory*. Proporciona bloqueo atómico en tiempo real (anti-solapamiento de sesiones), sincronización continua de partidas locales/autosaves y soporte para despliegue contenerizado en nodos de Pterodactyl.

---

## 1. Características Principales

* **Wrapper Transparente para Steam (`FactoryGameSteam.exe`):** Sustituye la llamada nativa de Steam, gestiona los bloqueos antes de iniciar y arranca el binario oficial sin alterar la integración de la plataforma ni los logros.
* **Bloqueo Atómico de Sesión (`Locking System`):** Impide que dos jugadores editen la misma partida compartida en simultáneo, avisando mediante ventanas emergentes nativas quién tiene la partida activa.
* **Hot-Sync Daemon (`SaveWatcherDaemon`):** Hilo en segundo plano que detecta los autoguardados locales durante la partida y los sube de inmediato al servidor para evitar pérdidas si el juego crashea.
* **Modo Dual:**
  * **API (Recomendado):** Servidor centralizado FastAPI con autenticación Bearer token, rotación automática de copias de seguridad (`backups`) y validación de prefijos autorizados.
  * **P2P:** Compatibilidad con sincronización distribuida mediante Syncthing y fichero de bloqueo `session.lock`.
* **Despliegue Listo para Pterodactyl:** Incluye definición de Egg (`PTDL_v2`) y script de entrada validado para contenedores basados en imágenes Debian/Yolks Python.

---

## 2. Guía de Instalación para Jugadores (Cliente)

Sigue estos pasos para conectar tu cliente de Steam con la partida compartida:

### Paso 1: Descargar los archivos
Accede a la pestaña **Releases** de este repositorio y descarga:
1. `FactoryGameSteam.exe`
2. `config.example.json`

### Paso 2: Preparar la carpeta del juego
1. En tu biblioteca de Steam, haz clic derecho en **Satisfactory** -> **Administrar** -> **Ver archivos locales**.
2. Localiza el ejecutable oficial `FactoryGameSteam.exe` y renómbralo a:
   **`FactoryGameSteam_real.exe`**
3. Pega el archivo `FactoryGameSteam.exe` descargado en esa misma carpeta.
4. Pega el archivo `config.example.json`, cámbiale el nombre a **`config.json`** y ábrelo con un editor de texto.

### Paso 3: Configurar `config.json`

#### Opción A: Modo Servidor API (Predeterminado)
Configura tu URL del servidor, tu nombre y el token provisto por el host:

```json
{
  "mode": "api",
  "server_url": "http://IP_O_DOMINIO_DEL_SERVIDOR:PUERTO",
  "user": "TuNombre",
  "token": "TU_TOKEN_SECRETO"
}
```

#### Opción B: Modo P2P (Syncthing)
Si el grupo sincroniza las partidas mediante Syncthing:

```json
{
  "mode": "p2p",
  "user": "TuNombre"
}
```

### Paso 4: Jugar
Inicia el juego desde la interfaz de **Steam** como siempre:
* Se comprobará si la partida está libre. Si alguien está jugando, se te preguntará si deseas esperar o jugar una partida personal fuera de línea.
* El juego descargará la última versión de la partida compartida automáticamente.
* Durante tu sesión, los autosaves se subirán automáticamente. Al cerrar el juego, se realizará una subida final y se liberará la sesión.

---

## 3. Despliegue del Servidor (Pterodactyl / OCI)

El backend corre sobre FastAPI y gestiona el almacenamiento, rotación de backups y locks de sesión.

### Despliegue con Pterodactyl Egg

1. En el panel de Pterodactyl, ve a **Admin** -> **Nests** -> **Import Egg**.
2. Selecciona el archivo `pterodactyl/egg-satisfactory-sync.json`.
3. Crea un nuevo servidor asignando este Egg:
   * **Docker Image:** `ghcr.io/parkervcp/yolks:python_3.12`
   * **Startup Command:** `bash server/start.sh`
   * **Variables:** Define la URL de este repositorio Git.
4. En el **File Manager** del servidor, configura los siguientes archivos en `server/data/`:

**`server/data/users.json`** (asigna tokens a tus jugadores):
```json
{
  "tokens": {
    "token_jugador_1": "Player1",
    "token_jugador_2": "Player2"
  }
}
```

**`server/data/settings.json`** (filtro de partidas gestionadas):
```json
{
  "allowed_prefix": "tacos_mecanicos_",
  "max_backups_per_file": 10
}
```

5. Inicia el servidor. La documentación interactiva Swagger estará disponible en `http://tu-servidor:puerto/docs`.

---

## 4. Desarrollo y Compilación Local

### Requisitos
* Python 3.11 o 3.12
* Windows (para compilar y ejecutar el cliente Win32)

### Instalación de dependencias de desarrollo
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### Ejecución de Tests
```powershell
python -m pytest -v
```

### Compilar el binario del cliente
Para regenerar el ejecutable de Steam empaquetado:
```powershell
.\build\build_exe.bat
```
El binario resultante se generará en `dist\FactoryGameSteam.exe`.

---

## 5. Estructura del Proyecto

```text
├── build/                 # Scripts de empaquetado con PyInstaller
├── client/                # Lógica del cliente wrapper y daemon
│   ├── sync/              # Proveedores API, P2P y SaveWatcherDaemon
│   ├── utils/             # Detección de rutas de guardado de Satisfactory y UI Win32
│   └── launcher.py        # Punto de entrada principal para FactoryGameSteam.exe
├── common/                # Modelos de datos Pydantic compartidos
├── pterodactyl/           # Plantillas de importación de Egg PTDL_v2
├── server/                # Backend FastAPI (endpoints, locking, backups)
│   ├── data/              # Base de datos JSON de usuarios, settings y saves
│   └── start.sh           # Script de arranque para contenedores
└── tests/                 # Suite de pruebas unitarias y de integración
```