import sys
import json
import re
import requests
from bs4 import BeautifulSoup

# URL de prueba de lista por defecto
URL_PRUEBA = "https://meli.la/1Ae8gNE"

def test_fetch(url):
    print("==================================================")
    print(f"INICIANDO FETCH DE PRUEBA (requests + BeautifulSoup)")
    print(f"URL: {url}")
    print("==================================================")
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        print("Enviando petición HTTP...")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Respuesta HTTP recibida. Código de estado: {response.status_code}")
        
        # Verificar si hay error de código HTTP
        if response.status_code != 200:
            print("❌ La petición no devolvió un código 200. Posible bloqueo del servidor.")
            return
            
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Título de la página
        title = soup.title.string if soup.title else "Sin Título"
        print(f"Título de la página: '{title.strip()}'")
        
        # 2. Detección de bloqueos comunes en el HTML
        body_lower = html.lower()
        print("\n--- Análisis de Seguridad / Bloqueos ---")
        indicators = {
            "captcha": "Google CAPTCHA / Desafío de seguridad",
            "recaptcha": "reCAPTCHA",
            "cloudflare": "Protección Cloudflare",
            "robot": "Detección de Robot",
            "access denied": "Acceso Denegado (403)",
            "forbidden": "Prohibido",
            "unusual activity": "Actividad Inusual detectada",
            "ingresa a tu cuenta": "Redirección a Inicio de Sesión / Login"
        }
        
        blocked = False
        for kw, desc in indicators.items():
            if kw in body_lower:
                print(f"⚠️ Alerta: Se detectó el término '{kw}' ({desc}) en el HTML.")
                blocked = True
        
        if not blocked:
            print("✅ No se detectaron indicadores evidentes de bloqueo o CAPTCHA en el HTML.")
            
        # Verificar si es una página de lista de productos
        cards = soup.select(".poly-card__content")
        is_list_page = len(cards) > 0
        
        if is_list_page:
            print(f"\n📋 MODO LISTA DETECTADO ({len(cards)} tarjetas encontradas) 📋")
            print("Analizando cada publicación en la lista sin ingresar en ellas...\n")
            
            parsed_count = 0
            print("================ RESULTADOS DE LA LISTA ================")
            for idx, card in enumerate(cards):
                title_elem = card.select_one(".poly-component__title")
                if not title_elem:
                    continue
                
                prod_title = title_elem.get_text().strip()
                prod_url = title_elem.get('href', '')
                
                if not prod_title:
                    continue
                    
                parsed_count += 1
                card_text = card.get_text().lower()
                
                # Detección de stock
                if "pausada" in card_text or "sin stock" in card_text or "agotado" in card_text or "no disponible" in card_text:
                    in_stock = False
                else:
                    in_stock = True
                    
                # Extraer precio
                price_str = "No disponible"
                price_elem = card.select_one(".poly-price__current")
                if price_elem:
                    price_str = price_elem.get_text().replace("\n", " ").strip()
                    
                status_emoji = "🟢 DISPONIBLE" if in_stock else "🔴 SIN STOCK"
                print(f"{parsed_count}. [{status_emoji}] - {prod_title}")
                print(f"   Precio: {price_str}")
                print(f"   Enlace: {prod_url[:90]}...")
                print("-" * 50)
                
            print(f"Total de productos procesados: {parsed_count}")
            print("========================================================")
            return
            
        # 3. Si no es una lista, intentar extraer JSON-LD de Producto Individual
        print("\n--- Extracción de metadatos JSON-LD ---")
        scripts = soup.find_all('script', type='application/ld+json')
        print(f"Se encontraron {len(scripts)} bloques de tipo <script type=\"application/ld+json\">")
        
        product_schema_found = False
        for idx, script in enumerate(scripts):
            script_text = script.get_text()
            if not script_text or not script_text.strip():
                continue
            try:
                data = json.loads(script_text.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        product_schema_found = True
                        print(f"\n[Bloque {idx}] Tipo: Product")
                        print(f"  - Nombre: {item.get('name')}")
                        if 'offers' in item:
                            offers = item["offers"]
                            offer = offers[0] if isinstance(offers, list) else offers
                            print(f"  - Disponibilidad: {offer.get('availability')}")
                            print(f"  - Precio: {offer.get('price')} {offer.get('priceCurrency')}")
            except Exception as e:
                print(f"❌ Error al decodificar bloque JSON-LD {idx}: {e}")
                
        if not product_schema_found:
            print("❌ No se encontró ningún metadato estructurado de tipo 'Product' en la página.")
            
        # 4. Mostrar una muestra de texto de la página individual
        print("\n--- Muestra del Texto de la Página (Primeros 300 caracteres) ---")
        clean_text = soup.get_text()
        clean_lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        sample_text = " | ".join(clean_lines[:10])
        print(sample_text[:300] + "...")
        print("==================================================")
        
    except Exception as e:
        print(f"❌ Ocurrió un error al realizar la petición: {e}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else URL_PRUEBA
    test_fetch(url)
