import os
import time
import asyncio
import threading
import requests
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

RESAMANIA_USER = os.getenv("RESAMANIA_USER")
RESAMANIA_PASS = os.getenv("RESAMANIA_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_notificacion_telegram(mensaje):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
        try:
            requests.post(url, json=data)
        except Exception as e:
            print(f"Error enviando mensaje a Telegram: {e}")

async def proceso_reserva_playwright(actividad_nombre, modo):
    url_login = "https://member.resamania.com/enjoy-multiusos/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url_login)
            await page.click("text=INICIAR SESIÓN")
            await page.fill("input[type='email']", RESAMANIA_USER)
            await page.fill("input[type='password']", RESAMANIA_PASS)
            await page.click("button[type='submit']")
            await page.wait_for_selector(".v-card, .activity-card", timeout=20000)

            tarjeta = page.locator(f"text={actividad_nombre}").first
            await tarjeta.click()
            await page.wait_for_selector(".v-dialog--active, [role='dialog']", timeout=10000)

            modal = page.locator(".v-dialog--active, [role='dialog']").first

            reserva_completada = False
            while not reserva_completada:
                texto_modal = await modal.inner_text()

                if "Se ha realizado la reserva" in texto_modal or "DESINSCRIBIRSE" in texto_modal:
                    enviar_notificacion_telegram(f"¡PLAZA CONSEGUIDA EN {actividad_nombre}!")
                    reserva_completada = True
                    break

                boton_inscribirse = modal.locator("button:has-text('INSCRIBIRSE'), div:has-text('INSCRIBIRSE')").first
                if await boton_inscribirse.is_visible():
                    await boton_inscribirse.click()

                await asyncio.sleep(1.0)

        except Exception as e:
            print(f"Error en ejecución: {e}")
        finally:
            await browser.close()

def ejecutar_en_hilo(actividad_nombre, modo):
    asyncio.run(proceso_reserva_playwright(actividad_nombre, modo))

@app.route('/ejecutar', methods=['POST'])
def recibir_orden():
    data = request.json or {}
    actividad = data.get('actividad', '')
    modo = data.get('modo', 'bucle')

    hilo = threading.Thread(target=ejecutar_en_hilo, args=(actividad, modo))
    hilo.start()

    return jsonify({"status": "Servicio iniciado en la nube", "modo": modo}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
