import os
import sys
import time
import json
import re
import logging
import argparse
import threading
import requests
from bs4 import BeautifulSoup
import telebot

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

CONFIG_FILE = "config.json"

def load_config():
    """Carga y valida el archivo de configuración config.json."""
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"El archivo de configuración {CONFIG_FILE} no existe.")
        sys.exit(1)
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error al decodificar {CONFIG_FILE}: {e}")
        sys.exit(1)
        
    # Validaciones básicas
    required_keys = ["telegram_chat_id", "check_interval_seconds", "products"]
    for key in required_keys:
        if key not in config:
            logging.error(f"Falta la clave requerida '{key}' en {CONFIG_FILE}.")
            sys.exit(1)
            
    if not isinstance(config["products"], list) or len(config["products"]) == 0:
        logging.error(f"La lista de productos en {CONFIG_FILE} está vacía o no es válida.")
        sys.exit(1)
        
    return config

def save_config(config):
    """Guarda los cambios de configuración en config.json."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Error al guardar la configuración en {CONFIG_FILE}: {e}")
        return False

def load_env_token():
    """Busca y lee el TELEGRAM_TOKEN desde el archivo .env o variables de entorno."""
    # Intentar primero desde variable de entorno
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        return token.strip()
        
    env_file = ".env"
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        if key.strip() == "TELEGRAM_TOKEN":
                            # Limpiar comillas si las hay
                            return val.strip().strip("'\"")
        except Exception as e:
            logging.error(f"Error al leer el archivo .env: {e}")
            
    return None

def check_telegram_connection(token, chat_id):
    """Prueba la conexión enviando un mensaje de prueba a Telegram."""
    try:
        logging.info("Enviando mensaje de prueba a Telegram...")
        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, "🔔 *Prueba de conexión exitosa*\nEl Rastreador de Stock está configurado correctamente y listo para monitorear.", parse_mode="Markdown")
        logging.info("¡Mensaje de prueba enviado con éxito!")
        return True
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {e}")
        return False

def run_init_mode(token):
    """Inicia el bot en modo polling para escuchar el comando /init y guardar el Chat ID."""
    logging.info("==================================================")
    logging.info("MODO DE CONFIGURACIÓN AUTOMÁTICA ACTIVO")
    logging.info("Por favor, envía el comando /init en el chat o grupo de Telegram")
    logging.info("donde deseas recibir las alertas de stock.")
    logging.info("==================================================")
    
    try:
        bot = telebot.TeleBot(token)
        bot_info = bot.get_me()
        logging.info(f"Bot identificado: @{bot_info.username}")
        logging.info("Esperando el comando /init...")
        
        @bot.message_handler(commands=['init'])
        def save_chat_id(message):
            chat_id = str(message.chat.id)
            chat_title = message.chat.title if message.chat.title else f"Chat privado con {message.from_user.first_name}"
            logging.info(f"¡Comando /init recibido desde: '{chat_title}' (ID: {chat_id})!")
            
            # Cargar config, actualizar ID y guardar
            config = load_config()
            config["telegram_chat_id"] = chat_id
            
            if save_config(config):
                logging.info(f"Configuración guardada exitosamente con el Chat ID: {chat_id}")
                bot.reply_to(
                    message,
                    f"🔔 *¡Rastreador Inicializado!*\n\n"
                    f"Este chat ha sido registrado con éxito (ID: `{chat_id}`).\n"
                    f"A partir de ahora, enviaré aquí las alertas de stock.\n\n"
                    f"👉 *Próximo paso:* Ejecuta el script normalmente en tu PC con:\n"
                    f"`python stock_checker.py`",
                    parse_mode="Markdown"
                )
                bot.stop_polling()
            else:
                bot.reply_to(message, "❌ Error interno al guardar la configuración en config.json.")
                bot.stop_polling()
                
        bot.infinity_polling()
        logging.info("Modo de configuración completado con éxito. Saliendo del programa.")
        
    except Exception as e:
        logging.error(f"Error en el modo de configuración automática: {e}")
        sys.exit(1)

def check_stock_single(product, user_agent):
    """
    Verifica el stock de un producto individual usando requests y BeautifulSoup.
    Retorna (in_stock, price_str)
    """
    url = product["url"]
    name = product["name"]
    
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        logging.info(f"Consultando stock para producto individual: '{name}'...")
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logging.warning(f"Error HTTP {response.status_code} al consultar '{name}'.")
            return None, None
            
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Estrategia Principal: Buscar JSON-LD
        json_ld_stock = None
        price_str = "No disponible"
        
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            script_text = script.get_text()
            if not script_text or not script_text.strip():
                continue
            try:
                data = json.loads(script_text.strip())
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if item.get("@type") == "Product" and "offers" in item:
                        offers = item["offers"]
                        offer = offers[0] if isinstance(offers, list) else offers
                        
                        availability = offer.get("availability", "")
                        price = offer.get("price")
                        currency = offer.get("priceCurrency", "ARS")
                        
                        if price and float(price) > 0:
                            price_str = f"${float(price):,.2f} {currency}".replace(",", ".")
                        
                        if "OutOfStock" in availability:
                            json_ld_stock = False
                        elif "InStock" in availability:
                            json_ld_stock = True
            except Exception:
                continue
                
        if json_ld_stock is not None:
            logging.info(f"[{name}] Stock determinado por JSON-LD: {json_ld_stock} (Precio: {price_str})")
            return json_ld_stock, price_str
            
        # 2. Fallbacks
        is_mercadolibre = "mercadolibre.com" in url.lower()
        is_zonakids = "zonakids.com" in url.lower()
        
        body_lower = soup.get_text().lower()
        
        if is_mercadolibre:
            if "no está disponible por el momento" in body_lower or "publicación pausada" in body_lower:
                return False, price_str
            if "comprar ahora" in body_lower or "agregar al carrito" in body_lower:
                return True, price_str
            
            logging.warning(f"[{name}] Fallback de Mercado Libre no pudo determinar el stock con certeza.")
            return None, None
            
        elif is_zonakids:
            stock_msg = soup.find(class_=re.compile("stock unavailable"))
            if stock_msg and "agotado" in stock_msg.get_text().lower():
                return False, price_str
                
            if "producto no disponible" in body_lower or "agotado" in body_lower:
                return False, price_str
                
            add_to_cart_btn = soup.find(id="product-addtocart-button-fixed")
            if add_to_cart_btn:
                if not add_to_cart_btn.has_attr('disabled'):
                    return True, price_str
                else:
                    return False, price_str
            
            if "añadir al carrito" in body_lower:
                return True, price_str
                
            logging.warning(f"[{name}] Fallback de Zonakids no pudo determinar el stock con certeza.")
            return None, None
            
        else:
            logging.warning(f"Sitio no identificado para {url}. Intentando verificación genérica...")
            if "agotado" in body_lower or "sin stock" in body_lower or "no disponible" in body_lower:
                return False, price_str
            if "comprar" in body_lower or "añadir" in body_lower or "agregar" in body_lower:
                return True, price_str
            return None, None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error de red al consultar '{name}': {e}")
        return None, None
    except Exception as e:
        logging.error(f"Error inesperado al procesar '{name}': {e}")
        return None, None

def check_stock_list(list_url, target_products, user_agent):
    """
    Descarga una página de listado (perfil/búsqueda) y evalúa el stock de varios productos dentro de ella.
    Retorna un diccionario mapping de { nombre_producto: (in_stock, precio) }
    """
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    results = {}
    try:
        logging.info(f"Consultando listado de productos en: {list_url}")
        response = requests.get(list_url, headers=headers, timeout=15)
        if response.status_code != 200:
            logging.warning(f"Error HTTP {response.status_code} al consultar el listado.")
            return results
            
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.select(".poly-card__content")
        
        if not cards:
            logging.warning("No se encontraron tarjetas de producto (.poly-card__content) en el listado.")
            return results
            
        logging.info(f"Se encontraron {len(cards)} tarjetas en la página. Evaluando objetivos...")
        
        # Para cada tarjeta en el listado
        for card in cards:
            title_elem = card.select_one(".poly-component__title")
            if not title_elem:
                continue
                
            card_title = title_elem.get_text().strip()
            
            # Verificamos si esta tarjeta coincide con alguno de nuestros productos objetivo
            for target_prod in target_products:
                target_name = target_prod["name"]
                
                # Búsqueda por subcadena
                if target_name.lower() in card_title.lower() or card_title.lower() in target_name.lower():
                    card_text = card.get_text().lower()
                    
                    # Evaluar disponibilidad en base a textos del contenedor
                    if "pausada" in card_text or "sin stock" in card_text or "agotado" in card_text or "no disponible" in card_text:
                        in_stock = False
                    else:
                        in_stock = True
                        
                    # Extraer precio si figura
                    price_str = "No disponible"
                    price_elem = card.select_one(".poly-price__current")
                    if price_elem:
                        price_str = price_elem.get_text().replace("\n", " ").strip()
                        
                    results[target_name] = (in_stock, price_str)
                    logging.info(f"-> Encontrado en lista: '{target_name}' | Stock: {in_stock} | Precio: {price_str}")
                    
    except Exception as e:
        logging.error(f"Error al consultar o procesar el listado {list_url}: {e}")
        
    return results

def send_telegram_alert(token, chat_id, product_name, url, price):
    """Envía la alerta de Telegram al usuario con formato llamativo."""
    bot = telebot.TeleBot(token)
    site_name = "Mercado Libre" if "mercadolibre.com" in url.lower() or "meli.la" in url.lower() else "Zonakids"
    
    message = (
        f"🚨 *¡STOCK DETECTADO!* 🚨\n\n"
        f"📦 *Producto:* {product_name}\n"
        f"🌐 *Sitio:* {site_name}\n"
        f"💵 *Precio:* {price}\n\n"
        f"🛒 [COMPRAR AQUÍ]({url})"
    )
    
    bot.send_message(chat_id, message, parse_mode="Markdown", disable_web_page_preview=False)

def register_bot_handlers(bot, config):
    """Registra los manejadores de comandos /status y /check en el bot."""
    
    @bot.message_handler(commands=['status'])
    def handle_status(message):
        logging.info(f"Comando /status recibido del Chat ID: {message.chat.id}")
        bot.reply_to(
            message,
            "🟢 *Rastreador de Stock Activo*\n\n"
            "El programa está funcionando correctamente en segundo plano.\n"
            f"Frecuencia de chequeo: `{config['check_interval_seconds']}` segundos.\n"
            f"Productos bajo monitoreo: `{len(config['products'])}`.",
            parse_mode="Markdown"
        )

    @bot.message_handler(commands=['check'])
    def handle_check(message):
        logging.info(f"Comando /check recibido del Chat ID: {message.chat.id}")
        bot.reply_to(message, "🔍 *Iniciando comprobación manual en tiempo real...* Por favor, espera.", parse_mode="Markdown")
        
        products = config["products"]
        user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        single_products = []
        list_url_groups = {}
        for p in products:
            if p.get("is_list"):
                url = p["url"]
                if url not in list_url_groups:
                    list_url_groups[url] = []
                list_url_groups[url].append(p)
            else:
                single_products.append(p)
                
        results_summary = []
        
        # 1. Chequear productos individuales
        for product in single_products:
            name = product["name"]
            in_stock, price = check_stock_single(product, user_agent)
            
            if in_stock is None:
                status_str = "❓ Error de lectura"
            elif in_stock:
                status_str = f"🟢 *Con Stock* (Precio: {price})"
            else:
                status_str = "🔴 Sin Stock"
                
            results_summary.append(f"📦 *{name}*\nEstado: {status_str}")
            
        # 2. Chequear productos en listas
        for list_url, prods in list_url_groups.items():
            results = check_stock_list(list_url, prods, user_agent)
            for product in prods:
                name = product["name"]
                
                if name not in results:
                    status_str = "❓ No encontrado en la lista"
                else:
                    in_stock, price = results[name]
                    if in_stock:
                        status_str = f"🟢 *Con Stock* (Precio: {price})"
                    else:
                        status_str = "🔴 Sin Stock"
                        
                results_summary.append(f"📦 *{name}*\nEstado: {status_str}")
                
        # Enviar respuesta con resultados consolidados
        response_msg = "🔍 *Resultados de Comprobación Manual:*\n\n" + "\n\n".join(results_summary)
        bot.send_message(message.chat.id, response_msg, parse_mode="Markdown", disable_web_page_preview=True)

    @bot.message_handler(commands=['interval'])
    def handle_interval(message):
        logging.info(f"Comando /interval recibido del Chat ID: {message.chat.id}")
        text_parts = message.text.split()
        
        if len(text_parts) < 2:
            current_int = config.get("check_interval_seconds", 300)
            bot.reply_to(
                message,
                f"⏱️ *Intervalo Actual*\n\n"
                f"El rastreador verifica el stock cada `{current_int}` segundos (aproximadamente {current_int // 60} minutos).\n\n"
                f"Para cambiarlo, envía:\n"
                f"`/interval <segundos>` (ej: `/interval 120`)",
                parse_mode="Markdown"
            )
            return
            
        try:
            new_val = int(text_parts[1])
            if new_val < 10:
                bot.reply_to(message, "⚠️ El intervalo mínimo permitido es de 10 segundos para evitar bloqueos de red.")
                return
                
            config["check_interval_seconds"] = new_val
            if save_config(config):
                logging.info(f"Intervalo de verificación actualizado a {new_val} segundos por Telegram.")
                bot.reply_to(
                    message,
                    f"✅ *Intervalo Actualizado*\n\n"
                    f"El intervalo de verificación se actualizó con éxito a `{new_val}` segundos.\n"
                    f"El cambio se aplicará a partir de la próxima comprobación.",
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(message, "❌ Error al guardar el nuevo intervalo en config.json.")
        except ValueError:
            bot.reply_to(message, "⚠️ Por favor, introduce un número entero válido para los segundos.\nEjemplo: `/interval 120`.")


def main():
    parser = argparse.ArgumentParser(description="Monitoreo de Stock para Zonakids y Mercado Libre con avisos en Telegram.")
    parser.add_argument("--test", action="store_true", help="Envía un mensaje de prueba a Telegram y finaliza el script.")
    parser.add_argument("--init", action="store_true", help="Inicia el bot en modo escucha para capturar el Chat ID automáticamente con /init.")
    args = parser.parse_args()
    
    config = load_config()
    
    # Obtener token de Telegram desde .env
    token = load_env_token()
    if not token or token == "ESCRIBE_AQUI_TU_TELEGRAM_TOKEN":
        logging.error("No se encontró o no está configurado el TELEGRAM_TOKEN en el archivo .env.")
        logging.error("Por favor, edita el archivo .env e introduce tu token real obtenido de @BotFather.")
        sys.exit(1)
        
    chat_id = config["telegram_chat_id"]
    interval = config["check_interval_seconds"]
    products = config["products"]
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Verificar si el Chat ID está sin configurar
    is_default_chat = chat_id in ["ESCRIBE_AQUI_TU_TELEGRAM_CHAT_ID", "", "TU_CHAT_ID", "0"]
    
    if args.init or is_default_chat:
        if is_default_chat:
            logging.info("Se detectó que el Chat ID no está configurado. Iniciando configuración automática...")
        run_init_mode(token)
        sys.exit(0)
        
    if args.test:
        success = check_telegram_connection(token, chat_id)
        sys.exit(0 if success else 1)
        
    # Inicializar el bot de Telegram
    bot = telebot.TeleBot(token)
    
    # Registrar manejadores de comandos (/status, /check)
    register_bot_handlers(bot, config)
    
    # Iniciar la escucha de comandos en un hilo secundario
    logging.info("Iniciando escucha de comandos (/status, /check) en segundo plano...")
    polling_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    polling_thread.start()
        
    logging.info("Iniciando el Rastreador de Stock...")
    logging.info(f"Productos totales configurados: {len(products)}")
    logging.info(f"Intervalo de comprobación: {interval} segundos")
    
    # Separar productos en individuales y productos que provienen de listas
    single_products = []
    list_url_groups = {}
    
    for p in products:
        if p.get("is_list"):
            url = p["url"]
            if url not in list_url_groups:
                list_url_groups[url] = []
            list_url_groups[url].append(p)
        else:
            single_products.append(p)
            
    # Registro de estados anteriores (inicializamos todo en False/sin stock)
    last_status = {}
    for p in products:
        last_status[p["name"]] = False
        
    logging.info(f"Clasificación de tareas:")
    logging.info(f"- Productos individuales a consultar: {len(single_products)}")
    logging.info(f"- Listas URL a consultar (agrupadas): {len(list_url_groups)}")
    
    logging.info("Iniciando monitoreo continuo. Presiona Ctrl+C para salir.")
    
    while True:
        # 1. Monitorear productos individuales
        for product in single_products:
            name = product["name"]
            url = product["url"]
            
            in_stock, price = check_stock_single(product, user_agent)
            
            if in_stock is None:
                logging.warning(f"No se pudo determinar el stock del producto individual '{name}' en esta vuelta.")
                continue
                
            prev_status = last_status.get(name, False)
            
            if in_stock:
                logging.info(f"🟢 [{name}] - ¡CON STOCK! (Precio: {price})")
                if not prev_status:
                    logging.info(f"Enviando alerta a Telegram para '{name}'...")
                    try:
                        send_telegram_alert(token, chat_id, name, url, price)
                        last_status[name] = True
                    except Exception as e:
                        logging.error(f"Error al enviar la alerta de stock para '{name}': {e}")
            else:
                logging.info(f"🔴 [{name}] - Sin stock")
                if prev_status:
                    logging.info(f"El producto '{name}' volvió a quedarse sin stock.")
                    last_status[name] = False
                    
            time.sleep(2)
            
        # 2. Monitorear listas de productos
        for list_url, prods in list_url_groups.items():
            results = check_stock_list(list_url, prods, user_agent)
            
            for product in prods:
                name = product["name"]
                url = product["url"]
                
                if name not in results:
                    logging.warning(f"El producto objetivo '{name}' no fue encontrado en la lista {list_url} en esta vuelta.")
                    continue
                    
                in_stock, price = results[name]
                prev_status = last_status.get(name, False)
                
                if in_stock:
                    logging.info(f"🟢 [{name}] - ¡CON STOCK! (Precio: {price})")
                    if not prev_status:
                        logging.info(f"Enviando alerta a Telegram para '{name}'...")
                        try:
                            send_telegram_alert(token, chat_id, name, url, price)
                            last_status[name] = True
                        except Exception as e:
                            logging.error(f"Error al enviar la alerta de stock para '{name}': {e}")
                else:
                    logging.info(f"🔴 [{name}] - Sin stock")
                    if prev_status:
                        logging.info(f"El producto '{name}' volvió a quedarse sin stock.")
                        last_status[name] = False
                        
            time.sleep(2)
            
        current_interval = config.get("check_interval_seconds", 300)
        logging.info(f"Esperando {current_interval} segundos para el próximo ciclo...")
        time.sleep(current_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Monitoreo detenido por el usuario. ¡Hasta luego!")
        sys.exit(0)
