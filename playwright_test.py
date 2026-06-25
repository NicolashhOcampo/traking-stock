import sys
import json
import re
import time
from playwright.sync_api import sync_playwright

# Nueva URL de prueba de lista por defecto
URL_PRUEBA = "https://meli.la/1Ae8gNE"

def test_playwright(url):
    print("==================================================")
    print("INICIANDO PRUEBA DE STOCK CON PLAYWRIGHT")
    print(f"URL: {url}")
    print("==================================================")
    
    try:
        with sync_playwright() as p:
            print("Lanzando navegador Chromium en modo VISIBLE (headless=False)...")
            browser = p.chromium.launch(headless=True)
            
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print("Cargando la página...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Esperar 5 segundos para carga de JS dinámico
            print("Esperando 5 segundos para asegurar la carga completa de datos...")
            page.wait_for_timeout(5000)
            
            title = page.title()
            print(f"Título de la página cargada: '{title}'\n")
            
            body_text = page.locator("body").inner_text()
            
            # Detectar si es una lista (tienda/perfil social o resultados de búsqueda)
            # Buscamos si existen elementos con clase .poly-card__content o similares en el DOM
            card_count = page.locator(".poly-card__content").count()
            is_list_page = card_count > 0
            
            if is_list_page:
                print(f"📋 MODO LISTA DETECTADO ({card_count} tarjetas encontradas) 📋")
                print("Analizando cada publicación en la lista sin ingresar en ellas...\n")
                
                cards = page.locator(".poly-card__content").all()
                parsed_count = 0
                
                print("================ RESULTADOS DE LA LISTA ================")
                for idx, card in enumerate(cards):
                    title_elem = card.locator(".poly-component__title")
                    if title_elem.count() == 0:
                        continue
                    
                    prod_title = title_elem.inner_text().strip()
                    prod_url = title_elem.get_attribute("href")
                    
                    if not prod_title:
                        continue
                        
                    parsed_count += 1
                    
                    # Obtener todo el texto de la tarjeta para verificar stock
                    card_text = card.inner_text().lower()
                    
                    # Detección de disponibilidad
                    if "pausada" in card_text or "sin stock" in card_text or "agotado" in card_text or "no disponible" in card_text:
                        in_stock = False
                    else:
                        in_stock = True
                        
                    # Buscar el precio
                    price_str = "No disponible"
                    price_elem = card.locator(".poly-price__current")
                    if price_elem.count() > 0:
                        # Extraer solo el texto numérico y símbolos
                        price_str = price_elem.inner_text().replace("\n", " ").strip()
                    
                    status_emoji = "🟢 DISPONIBLE" if in_stock else "🔴 SIN STOCK"
                    print(f"{parsed_count}. [{status_emoji}] - {prod_title}")
                    print(f"   Precio: {price_str}")
                    print(f"   Enlace: {prod_url[:90]}...")
                    print("-" * 50)
                
                print(f"Total de productos procesados: {parsed_count}")
                print("========================================================")
                
            else:
                print("🔍 MODO PRODUCTO INDIVIDUAL DETECTADO 🔍")
                html = page.content()
                
                # 1. Comprobar si nos redirigió a Login o saltó un desafío
                print("\n--- Análisis de Seguridad / Acceso ---")
                if "ingresa a tu cuenta" in body_text.lower() or "iniciar sesión" in body_text.lower() and "compras" not in body_text.lower():
                    print("⚠️ Mercado Libre redirigió a la página de Inicio de Sesión.")
                elif "captcha" in html.lower() or "robot" in html.lower():
                    print("⚠️ Se detectaron elementos de CAPTCHA de seguridad en la página.")
                else:
                    print("✅ Acceso correcto: No se detectaron pantallas de Login ni CAPTCHAs.")
                    
                # 2. Intentar buscar metadatos JSON-LD
                print("\n--- Análisis de JSON-LD ---")
                scripts = page.locator('script[type="application/ld+json"]').all()
                print(f"Se encontraron {len(scripts)} bloques JSON-LD en el DOM.")
                
                json_ld_stock = None
                price_str = "No disponible"
                
                for idx, script in enumerate(scripts):
                    script_text = script.inner_text()
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
                
                final_stock = None
                if json_ld_stock is not None:
                    print(f"Resultado JSON-LD: Stock disponible = {json_ld_stock} (Precio: {price_str})")
                    final_stock = json_ld_stock
                else:
                    print("❌ No se encontró o no se pudo interpretar el metadato JSON-LD 'Product'.")
                    
                # 3. Fallback de Texto Directo en el DOM renderizado
                print("\n--- Análisis de Fallback de Texto ---")
                body_lower = body_text.lower()
                fallback_stock = None
                if "no está disponible por el momento" in body_lower or "publicación pausada" in body_lower:
                    print("Resultado Fallback: SIN STOCK (Mensaje 'no disponible' o 'pausado' detectado en texto)")
                    fallback_stock = False
                elif "comprar ahora" in body_lower or "agregar al carrito" in body_lower:
                    print(f"Resultado Fallback: CON STOCK (Botones de compra detectados en texto. Precio: {price_str})")
                    fallback_stock = True
                else:
                    print("Resultado Fallback: INDETERMINADO (No se encontraron patrones de compra ni de falta de stock)")
                    
                if final_stock is None:
                    final_stock = fallback_stock
                    
                print("\n================ RESUMEN DE DETECCIÓN ================")
                print(f"URL: {url}")
                if final_stock is True:
                    print("ESTADO: 🟢 ¡DISPONIBLE / CON STOCK! 🟢")
                    print(f"PRECIO: {price_str}")
                elif final_stock is False:
                    print("ESTADO: 🔴 AGOTADO / SIN STOCK 🔴")
                else:
                    print("ESTADO: ❓ INDETERMINADO (No se pudo verificar) ❓")
                print("======================================================")
            
            print("\nEsperando 10 segundos adicionales con el navegador abierto para que puedas inspeccionarlo visualmente...")
            time.sleep(10)
            
            browser.close()
            print("Navegador cerrado. Proceso finalizado.")
            
    except Exception as e:
        print(f"❌ Error al ejecutar Playwright: {e}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else URL_PRUEBA
    test_playwright(url)
