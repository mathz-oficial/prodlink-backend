from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import re
import random 

app = Flask(__name__)
CORS(app) 

# --- Configurações Importantes ---
# **SUBSTITUA "SEU_LINK_DE_CONVITE_DO_GRUPO_AQUI" PELO SEU LINK REAL!**
WHATSAPP_GROUP_INVITE_LINK = os.environ.get("WHATSAPP_GROUP_INVITE_LINK", "https://chat.whatsapp.com/ByyFqFS3mkoAw6jFlBxFmG") 

# Dicionário com seletores CSS para extrair informações dos sites.
# EXTREMAMENTE IMPORTANTE: Seletores são sensíveis a mudanças no site.
# Se um site mudar sua estrutura HTML, você precisará atualizar os seletores aqui.
SITE_SELECTORS = {
    "amazon.com": {
        "title": "#productTitle",
        "price": ".a-price-whole", 
        "old_price": ".a-text-price .a-offscreen", 
        "image": "#landingImage",
        "currency": ".a-price-symbol", 
        "description": "#productDescription span", 
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
        "title": ".product-title-text",
        "price": ".product-price-value",
        "old_price": ".product-price-del .product-price-value", 
        "image": ".magnifier-image",
        "currency": ".product-price-currency",
        "description": ".product-description-content", 
        "store_name": "AliExpress" 
    },
    "shopee.com.br": { 
        "title": "div[class^='_2EB2pM'], div[class^='_3O_Lg'], ._3yC_eA", 
        "price": "div[class^='_2fXkC'], ._3gUuT", 
        "old_price": "div[class^='_2o8hA'], ._3gUuT.line-through", 
        "image": "div[class^='_2l-C4'] img, ._2aB7J img", 
        "currency": "", 
        "description": "div[class^='_3gUuT'], ._3gUuT", 
        "store_name": "Shopee"
    },
}

def extract_text(soup, selector):
    if isinstance(selector, list):
        for s in selector:
            element = soup.select_one(s)
            if element:
                return element.get_text(strip=True)
        return ""
    else:
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ""

def extract_attr(soup, selector, attr):
    if isinstance(selector, list):
        for s in selector:
            element = soup.select_one(s)
            if element and attr in element.attrs:
                return element[attr]
        return ""
    else:
        element = soup.select_one(selector)
        return element[attr] if element and attr in element.attrs else ""

def clean_price(price_text):
    price_text = price_text.replace(" ", "").replace("\n", "").replace(",", ".")
    match = re.search(r'(\d[\d\.,]*)', price_text)
    if match:
        cleaned = match.group(1).replace(",", ".") 
        return cleaned
    return ""

def extract_product_info(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
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
        price = clean_price(price_raw) 
        
        old_price_raw = extract_text(soup, selectors.get("old_price", ""))
        old_price = clean_price(old_price_raw) if old_price_raw else "" 
        
        currency = extract_text(soup, selectors.get("currency", ""))
        image = extract_attr(soup, selectors["image"], "src")
        description = extract_text(soup, selectors.get("description", ""))

        if not image:
            image = extract_attr(soup, selectors["image"], "data-a-dynamic-image") 
            if image:
                try:
                    import json
                    img_dict = json.loads(image)
                    image = next(iter(img_dict)) 
                except json.JSONDecodeError:
                    pass 
        
        if image and not image.startswith(('http://', 'https://')):
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            image = base_url + image if image.startswith('/') else base_url + '/' + image


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
        return {"error": f"Erro ao acessar a URL: {e}. Verifique se o link está correto."}
    except Exception as e:
        return {"error": f"Erro inesperado ao processar o link: {e}"}

def generate_whatsapp_link(product_info):
    """
    Gera o link para compartilhar no WhatsApp com base nas informações do produto,
    com a estrutura detalhada solicitada, cupom aleatório e nome da loja.
    O link gerado será para o grupo de WhatsApp especificado.
    """
    title = product_info.get('title', 'Produto').replace('*', '').replace('_', '') 
    price = product_info.get('price', 'Preço não disponível')
    old_price = product_info.get('old_price', '') 
    currency = product_info.get('currency', '')
    url = product_info['url'] 
    store_name = product_info.get('store_name', '') 
    
    # --- Geração de Cupom Aleatório ---
    coupon_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    coupon_length = 8 
    random_coupon = ''.join(random.choice(coupon_chars) for i in range(coupon_length))
    CUPOM_TEXT = f"🔖Utilize o Cupom: {random_coupon}" 
    
    SUA_ASSINATURA = "~ Seu Nome Aqui" # SUBSTITUA PELO SEU NOME REAL AQUI
    
    whatsapp_message_parts = []

    # 1. Título do produto
    whatsapp_message_parts.append(f"*{title}*") 
    whatsapp_message_parts.append("") # Linha em branco para espaçamento

    # 2. Preço "De" (riscado)
    if old_price and old_price != "Preço não disponível" and old_price != price:
        whatsapp_message_parts.append(f"~De {currency}{old_price}~")
    
    # 3. Preço "Por" com destaque e "no Pix"
    whatsapp_message_parts.append(f"*Por {currency}{price} no Pix*")
    
    # 4. Cupom de desconto (sempre gerado)
    whatsapp_message_parts.append("") # Linha em branco antes do cupom
    whatsapp_message_parts.append(f"({CUPOM_TEXT})")

    # 5. Link do Produto
    whatsapp_message_parts.append("") # Linha em branco antes do link
    whatsapp_message_parts.append("🛒 Link do Produto ⤵️")
    whatsapp_message_parts.append(url) # O link em si, em nova linha para pré-visualização
    
    # 6. Texto da Loja (agora dinâmico com o nome da loja)
    if store_name:
        # Aqui, estamos usando o nome da loja extraído.
        whatsapp_message_parts.append(f"\n🛒 Na {store_name}!!!") 

    # 7. Sua assinatura 
    if SUA_ASSINATURA:
        whatsapp_message_parts.append(f"{🚀 Via ProdLink!}") 

    message_for_whatsapp = "\n".join(whatsapp_message_parts)
    
    # --- MUDANÇA PARA ENVIAR PARA O GRUPO ---
    # Usamos o link de convite do grupo e anexamos o texto codificado.
    # O WhatsApp abrirá o grupo e a mensagem pré-preenchida para o usuário encaminhar.
    whatsapp_url = f"{WHATSAPP_GROUP_INVITE_LINK}?text={requests.utils.quote(message_for_whatsapp)}"
    return whatsapp_url

@app.route('/api/process_product_link', methods=['POST'])
def process_product_link():
    """
    Endpoint da API que recebe a URL do frontend, processa e retorna as informações.
    """
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
    """Rota de teste simples para verificar se o backend está online."""
    return "ProdLink Backend está online! Use a rota /api/process_product_link para processar links."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
