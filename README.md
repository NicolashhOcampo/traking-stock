# Rastreador de Stock Multisitio (Zonakids y Mercado Libre)

Este script en Python monitorea la disponibilidad (stock) de productos en las tiendas de **Zonakids** y **Mercado Libre**, y envía una notificación inmediata a tu cuenta o grupo de Telegram en cuanto detecta stock disponible.

El script está diseñado para correr localmente en tu PC de forma continua. Mantiene un registro del estado del stock y te enviará un único mensaje de alerta en el momento en que el producto pase de "Agotado" a "Disponible" para no saturarte de notificaciones repetidas.

---

## Requisitos Previos

Necesitas tener **Python 3** instalado en tu computadora.

### 1. Instalar Dependencias
Abre tu consola o terminal (PowerShell, CMD, o la terminal de Linux/Mac) en la carpeta del proyecto y ejecuta el siguiente comando para instalar las librerías necesarias:

```bash
pip install -r requirements.txt
```

---

## Configuración de Telegram

Para recibir las alertas, necesitas crear tu propio Bot de Telegram (gratuito) y vincularlo al chat o grupo donde quieres recibir las notificaciones.

### Paso A: Crear el Bot de Telegram
1. En Telegram, busca al usuario **`@BotFather`** (el bot oficial para crear otros bots) e inicia un chat con él.
2. Envía el comando `/newbot`.
3. Sigue las instrucciones: te pedirá un **nombre** para tu bot (ej. `MiRastreadorStockBot`) y luego un **nombre de usuario** (ej. `mi_rastreador_stock_bot` - debe terminar obligatoriamente en `bot`).
4. Una vez creado, **`@BotFather`** te enviará un mensaje con el **Token HTTP API** (una cadena larga de letras y números). Cópialo.
5. Abre el archivo **`.env`** en la carpeta del proyecto y define tu token en la variable `TELEGRAM_TOKEN` (ej. `TELEGRAM_TOKEN=tu_token_aqui`).

### Paso B: Vincular tu Bot al Chat o Grupo (Configuración Automática)
Ya no necesitas buscar tu ID de chat manualmente. El script puede capturarlo automáticamente:
1. Agrega a tu bot a tu grupo de Telegram (o inicia un chat privado con él presionando **Iniciar** / **Start**).
2. En la terminal de tu computadora ejecuta el script en modo de inicialización:
   ```bash
   python stock_checker.py --init
   ```
   *(Nota: Si ejecutas `python stock_checker.py` por primera vez sin configurar el Chat ID, el programa lo detectará y arrancará automáticamente en este modo).*
3. Envía el comando **`/init`** en el grupo o chat privado de Telegram donde está tu bot.
4. El bot responderá confirmando que la vinculación fue exitosa. El script guardará el Chat ID automáticamente en tu archivo `config.json` y se cerrará solo.

---

## Configuración del Script

El archivo **`.env`** almacena de manera segura tus credenciales privadas (el token de Telegram):

```env
TELEGRAM_TOKEN=TU_TOKEN_DE_TELEGRAM
```

El archivo **`config.json`** almacena el resto de la configuración del bot y los productos. Después de la vinculación automática, se verá así:

```json
{
  "telegram_chat_id": "-100123456789",
  "check_interval_seconds": 300,
  "products": [
    {
      "name": "Combo Album + 25 Sobres (Zonakids)",
      "url": "https://zonakids.com/combo-1-album-25-sobres-de-figuritas-fifa-world-cup-2026"
    },
    {
      "name": "Figuritas Panini Copa Mundial Fifa 2026 - 25 Sobres Oficial World Cup 2026 Mundial 2026",
      "url": "https://meli.la/1Ae8gNE",
      "is_list": true
    },
    {
      "name": "Box 50 Sobres Panini Mundial Fifa World Cup 2026 Oficial Copa Mundial Fifa 2026",
      "url": "https://meli.la/1Ae8gNE",
      "is_list": true
    }
  ]
}
```

* **`check_interval_seconds`**: Frecuencia con la que el script comprobará el stock en segundos (300 segundos equivalen a 5 minutos).
* **`products`**: Puedes agregar tantas URLs de Zonakids o Mercado Libre como quieras a esta lista siguiendo el mismo formato de ejemplo. Si configuras `"is_list": true`, el script buscará la tarjeta que coincida con el nombre dentro de esa página listado, descargándola una sola vez por ciclo.

---

## Comandos Interactivos de Telegram

* **`/status`**: El bot responderá indicando que el rastreador está funcionando en segundo plano, mostrando el intervalo de chequeo y la cantidad de productos bajo monitoreo.
* **`/check`**: Fuerza una comprobación manual de stock de todos los productos configurados (tanto individuales como dentro de las listas) en tiempo real. Te responderá de inmediato con un resumen detallado de los resultados tengan o no stock.
* **`/interval <segundos>`**: Muestra el intervalo de verificación actual (si se envía solo) o lo modifica en tiempo real al valor ingresado (ej: `/interval 120`). El cambio se autoguarda en `config.json` para persistir tras reinicios.

---

## Modo de Uso

### 1. Probar las Credenciales de Telegram (Opcional)
Puedes verificar que el bot tiene permisos de escritura enviando un mensaje de prueba con:

```bash
python stock_checker.py --test
```

### 2. Ejecutar el Monitoreo Continuo
Para iniciar el monitoreo de stock en tiempo real, ejecuta:

```bash
python stock_checker.py
```

El script se quedará corriendo e imprimirá en la consola la fecha y el estado del stock de cada producto en cada vuelta. Para cerrarlo, presiona **`Ctrl + C`** en la consola.
