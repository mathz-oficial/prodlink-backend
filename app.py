from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote 
import os
import re
import random 
import json 

app = Flask(__name__)
CORS(app) 

# --- Configurações Importantes ---
# **NÚMERO DE TELEFONE PARA O WHATSAPP - JÁ INSERIDO**
WHATSAPP_PHONE_NUMBER = "5581973085768"

# Dicionário com seletores CSS para extrair informações dos sites.
# EXTREMAMENTE IMPORTANTE: Seletores são sensíveis a mudanças no site.
# Se um site mudar sua estrutura HTML, você precisará atualizar os seletores aqui.
SITE_SELECTORS = {
    "amazon.com": {
        "title": "#productTitle",
        "price": "span.a-price span.a-offscreen", 
        "old_price": "span.a-text-price span.a-offscreen", 
        "image": "#landingImage, img#imgBliss, #imgTagWrapperId img", 
        "currency": "span.a-price-symbol", 
        "description": "#productDescription span, #feature-bullets .a-list-item", 
        "store_name": "Amazon" 
    },
    "mercadolivre.com.br": {
        "title": ".ui-pdp-title",
        "price": ".andes-money-amount__fraction",
        "old_price": ".ui-pdp-price__second-line .andes-money-amount__fraction", 
        "image": ".ui-pdp-gallery__figure img",
        "currency": ".andes-money-amount__currency-symbol",
        "description": ".ui-pdp-description__content",
        "store_name": "Mercado Livre" 
    },
    "aliexpress.com": {
        "title": "h1.product-title-text, .product-title-text",
        "price": "div.product-price-current span.currency-value, .product-price-value",
        "old_price": "div.product-price-original span.currency-value, .product-price-del .product-price-value",
        "image": ".magnifier-image, .image-view-magnifier-wrap img",
        "currency": "div.product-price-current span.currency-symbol, .product-price-currency",
        "description": ".product-description-content, div.product-description",
        "store_name": "AliExpress" 
    },
    "shopee.com.br": { 
        "title": "div.qa_sQ, ._3yC_eA, ._2EB2pM", 
        "price": "div.qa_sW span, ._3gUuT, ._2fXkC", 
        "old_price": "div.qa_sX span, ._3gUuT.line-through, ._2o8hA", 
        "image": "div.flex.items-center.justify-center.relative.shopee-image-container img, ._2l-C4 img, ._2aB7J img", 
        "currency": "div.qa_sW span", 
        "description": "div.Wk005g, ._3gUuT", 
        "store_name": "Shopee"
    },
}

def extract_text(soup, selector):
    selectors = selector.split(',') if isinstance(selector, str) and ',' in selector else [selector]
    for s in selectors:
        element = soup.select_one(s.strip())
        if element:
            return element.get_text(strip=True)
    return ""

def extract_attr(soup, selector, attr):
    selectors = selector.split(',') if isinstance(selector, str) and ',' in selector else [selector]
    for s in selectors:
        element = soup.select_one(s.strip())
        if element and attr in element.attrs:
            return element[attr]
    return ""

def clean_price(price_text):
    if not price_text:
        return ""
    
    price_text = price_text.replace(" ", "").replace("\n", "")
    price_text = re.sub(r'^[^\d\.,]*', '', price_text) 

    if re.search(r',\d{2}$', price_text):
        price_text = price_text.replace('.', '').replace(',', '.')
    elif re.search(r'\.\d{2}$', price_text):
        price_text = price_text.replace(',', '') 
    else: 
        price_text = price_text.replace('.', '').replace(',', '')
    
    match = re.search(r'(\d+\.?\d*)', price_text)
    if match:
        return match.group(1)
    return ""

def extract_product_info(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        response = requests.get(url, headers=headers, timeout=20) 
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        domain = urlparse(url).netloc.replace("www.", "")
        
        selectors = None
        store_name = ""
        for site_key, site_data in SITE_SELECTORS.items():
            if site_key in domain:
                selectors = site_data
                store_name = site_data.get("store_name", "") 
                break
        
        if not selectors:
            return {"error": "Site não suportado. Tente Amazon, Mercado Livre, AliExpress ou Shopee."}
        
        title = extract_text(soup, selectors["title"])
        price_raw = extract_text(soup, selectors["price"])
        currency = extract_text(soup, selectors.get("currency", "")) 
        
        if not currency:
            if "R$" in price_raw:
                currency = "R$"
            elif "$" in price_raw:
                currency = "$"
            elif "€" in price_raw:
                currency = "€"
            else:
                currency = "R$" 

        price = clean_price(price_raw) 
        
        old_price_raw = extract_text(soup, selectors.get("old_price", ""))
        old_price = clean_price(old_price_raw)
        
        try:
            current_price_float = float(price) if price else 0.0
            old_price_float = float(old_price) if old_price else 0.0

            if old_price_float > 0.0 and current_price_float > 0.0 and old_price_float < current_price_float:
                price, old_price = old_price, price 
                current_price_float, old_price_float = old_price_float, current_price_float 
            
            if old_price_float == current_price_float or old_price_float == 0.0:
                old_price = ""

        except ValueError:
            old_price = "" 
            pass
            
        image = extract_attr(soup, selectors["image"], "src")
        
        if not image: 
            data_image_str = extract_attr(soup, selectors["image"], "data-a-dynamic-image")
            if data_image_str:
                try:
                    img_dict = json.loads(data_image_str)
                    image = next(iter(img_dict.keys())) 
                except (json.JSONDecodeError, StopIteration):
                    pass 
            
            if not image: 
                image = extract_attr(soup, selectors["image"], "data-src")

        if image and not image.startswith(('http://', 'https://')):
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            image = base_url.rstrip('/') + '/' + image.lstrip('/')

        # Esta é a linha CRÍTICA para a variável 'description'
        description = extract_text(soup, selectors.get("description", ""))

        product = {
            "url": url,
            "title": title if title else "Título não disponível",
            "price": price if price else "Preço não disponível",
            "old_price": old_price, 
            "currency": currency, 
            "image": image if image else "https://via.placeholder.com/150?text=Sem+Imagem", 
            "domain": domain,
            "description": description if description else "Descrição não disponível", 
            "store_name": store_name 
        }
        
        return product
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro ao acessar a URL: {e}. Verifique se o link está correto ou se o site está bloqueando requisições."}
    except Exception as e:
        import traceback
        print(f"Erro inesperado ao processar o link {url}: {e}")
        traceback.print_exc() 
        return {"error": f"Erro inesperado ao processar o link. Tente novamente mais tarde. Detalhes: {e}"}

def generate_whatsapp_link(product_info):
    title = product_info.get('title', 'Produto').replace('*', '').replace('_', '') 
    price = product_info.get('price', 'Preço não disponível')
    old_price = product_info.get('old_price', '') 
    currency = product_info.get('currency', '')
    url = product_info['url'] 
    store_name = product_info.get('store_name', '') 
    
    coupon_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    coupon_length = 8 
    random_coupon = ''.join(random.choice(coupon_chars) for i in range(coupon_length))
    CUPOM_TEXT = f"🔖Utilize o Cupom: {random_coupon}" 
    
    whatsapp_message_parts = []

    whatsapp_message_parts.append(f"*{title}*") 
    whatsapp_message_parts.append("") 

    if old_price and old_price != "Preço não disponível":
        try:
            if float(old_price) > float(price):
                whatsapp_message_parts.append(f"~De {currency}{old_price}~")
        except ValueError:
            pass 
        
    whatsapp_message_parts.append(f"*Por {currency}{price} no Pix*")
    
    whatsapp_message_parts.append("") 
    whatsapp_message_parts.append(f"({CUPOM_TEXT})")

    whatsapp_message_parts.append("") 
    whatsapp_message_parts.append("🛒 Link do Produto ⤵️")
    whatsapp_message_parts.append(url) 
    
    if store_name:
        whatsapp_message_parts.append(f"\n🛒 Na {store_name}!!!") 

    whatsapp_message_parts.append("Via ProdLink!") 

    message_for_whatsapp = "\n".join(whatsapp_message_parts)
    
    whatsapp_url = f"https://api.whatsapp.com/send?phone={WHATSAPP_PHONE_NUMBER}&text={quote(message_for_whatsapp)}"
    return whatsapp_url

@app.route('/api/process_product_link', methods=['POST'])
def process_product_link():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"error": "A URL do produto é obrigatória."}), 400
    
    if not url.startswith(('http://', 'https://')):
        return jsonify({"error": "Formato de URL inválido. Use 'http://' ou 'https://'."}), 400

    product_info = extract_product_info(url)
    
    if "error" in product_info:
        return jsonify(product_info), 400 
    
    whatsapp_link = generate_whatsapp_link(product_info)
    product_info["whatsapp_link"] = whatsapp_link
    
    return jsonify(product_info)

@app.route('/')
def home():
    return "ProdLink Backend está online! Use a rota /api/process_product_link para processar links."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
