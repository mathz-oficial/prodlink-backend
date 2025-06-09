from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote 
import os
import re
import random 

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
        "image": "#landingImage",
        "currency": "span.a-price-symbol", 
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
        "title": "h1.product-title-text, .product-title-text", # ATUALIZADO
        "price": "div.product-price-current span.currency-value, .product-price-value", # ATUALIZADO
        "old_price": "div.product-price-original span.currency-value, .product-price-del .product-price-value", # ATUALIZADO
        "image": ".magnifier-image, .image-view-magnifier-wrap img", # ATUALIZADO
        "currency": "div.product-price-current span.currency-symbol, .product-price-currency", # ATUALIZADO
        "description": ".product-description-content, div.product-description", # ATUALIZADO
        "store_name": "AliExpress" 
    },
    "shopee.com.br": { 
        "title": "div.qa_sQ, ._3yC_eA, ._2EB2pM", # ATUALIZADO
        "price": "div.qa_sW span, ._3gUuT, ._2fXkC", # ATUALIZADO
        "old_price": "div.qa_sX span, ._3gUuT.line-through, ._2o8hA", # ATUALIZADO
        "image": "div.flex.items-center.justify-center.relative.shopee-image-container img, ._2l-C4 img, ._2aB7J img", # ATUALIZADO
        "currency": "div.qa_sW span", # Às vezes incluído no preço, mas adicionado seletor específico
        "description": "div.Wk005g, ._3gUuT", # ATUALIZADO
        "store_name": "Shopee"
    },
}

def extract_text(soup, selector):
    if isinstance(selector, list) or isinstance(selector, str) and ',' in selector: # Se for lista ou string com múltiplos seletores
        selectors = selector.split(',') if isinstance(selector, str) else selector
        for s in selectors:
            element = soup.select_one(s.strip())
            if element:
                return element.get_text(strip=True)
        return ""
    else: # Se for um único seletor
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ""

def extract_attr(soup, selector, attr):
    if isinstance(selector, list) or isinstance(selector, str) and ',' in selector: # Se for lista ou string com múltiplos seletores
        selectors = selector.split(',') if isinstance(selector, str) else selector
        for s in selectors:
            element = soup.select_one(s.strip())
            if element and attr in element.attrs:
                return element[attr]
        return ""
    else: # Se for um único seletor
        element = soup.select_one(selector)
        return element[attr] if element and attr in element.attrs else ""

def clean_price(price_text):
    if not price_text:
        return ""
    # Remove espaços, quebras de linha e substitui vírgula por ponto
    price_text = price_text.replace(" ", "").replace("\n", "").replace(",", ".")
    # Remove qualquer texto que não seja dígito, ponto ou vírgula no início (para moedas)
    price_text = re.sub(r'^[^\d\.]*', '', price_text)
    
    # Busca o primeiro número que pode ter vírgulas ou pontos como separador decimal
    match = re.search(r'(\d[\d\.]*(?:,\d{2})?|\d[\d,]*(?:\.\d{2})?)', price_text)
    if match:
        cleaned = match.group(1).replace(",", ".") # Garante que o separador decimal é ponto
        # Se tiver mais de um ponto (ex: 1.000.00), remove os pontos de milhar
        if cleaned.count('.') > 1 and re.search(r'\.\d{3}', cleaned): # Ex: 1.234.56 -> 1234.56 (se tiver ponto antes de 3 digitos)
            parts = cleaned.split('.')
            if len(parts[-1]) == 2: # Se a última parte tem 2 dígitos, é decimal
                cleaned = "".join(parts[:-1]) + "." + parts[-1]
            else: # Caso contrário, remove todos os pontos
                cleaned = "".join(parts)
        return cleaned
    return ""

def extract_product_info(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Connection": "keep-alive"
        }
        response = requests.get(url, headers=headers, timeout=15) # Aumentado timeout para 15s
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
        currency = extract_text(soup, selectors.get("currency", "")) # Tenta pegar da moeda
        
        # Se a moeda não foi encontrada via seletor, tenta inferir do preço
        if not currency and "R$" in price_raw:
            currency = "R$"
        elif not currency and "$" in price_raw:
            currency = "$"
        elif not currency and "€" in price_raw:
            currency = "€"
        
        price = clean_price(price_raw) 
        
        old_price_raw = extract_text(soup, selectors.get("old_price", ""))
        old_price = clean_price(old_price_raw) if old_price_raw else "" 

        # **LÓGICA PARA CORRIGIR VALORES INVERTIDOS**
        # Se 'old_price' existir e for menor que 'price', inverte os valores
        if old_price and price and float(old_price) < float(price):
            temp_price = price
            price = old_price
            old_price = temp_price
            
        image = extract_attr(soup, selectors["image"], "src")
        
        if not image: # Tenta outros atributos se 'src' falhar
            image = extract_attr(soup, selectors["image"], "data-a-dynamic-image")
            if image:
                try:
                    import json
                    img_dict = json.loads(image)
                    # Pega a primeira URL válida no dicionário, que geralmente é a de maior resolução
                    image = next(iter(img_dict.keys()))
                except (json.JSONDecodeError, StopIteration):
                    pass # Ignora se não for JSON ou estiver vazio
            
            if not image: # Tenta data-src se ainda não tiver imagem
                image = extract_attr(soup, selectors["image"], "data-src")

        if image and not image.startswith(('http://', 'https://')):
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            image = base_url + image if image.startswith('/') else base_url + '/' + image


        product = {
            "url": url,
            "title": title if title else "Título não disponível",
            "price": price if price else "Preço não disponível",
            "old_price": old_price, 
            "currency": currency if currency else "R$", 
            "image": image if image else "https://via.placeholder.com/150?text=Sem+Imagem", 
            "domain": domain,
            "description": description if description else "Descrição não disponível", 
            "store_name": store_name 
        }
        
        return product
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro ao acessar a URL: {e}. Verifique se o link está correto ou se o site está bloqueando requisições."}
    except Exception as e:
        return {"error": f"Erro inesperado ao processar o link: {e}"}

def generate_whatsapp_link(product_info):
    """
    Gera o link para compartilhar no WhatsApp com base nas informações do produto,
    com a estrutura detalhada solicitada, cupom aleatório e nome da loja.
    O link gerado será para o número de telefone especificado.
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
    
    whatsapp_message_parts = []

    # 1. Título do produto
    whatsapp_message_parts.append(f"*{title}*") 
    whatsapp_message_parts.append("") # Linha em branco para espaçamento

    # 2. Preço "De" (riscado)
    # Mostra "De" apenas se existir e for maior que o preço final.
    try:
        if old_price and price and float(old_price) > float(price):
            whatsapp_message_parts.append(f"~De {currency}{old_price}~")
    except ValueError:
        pass # Ignora se a conversão para float falhar
        
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
        whatsapp_message_parts.append(f"\n🛒 Na {store_name}!!!") 

    # 7. Assinatura
    whatsapp_message_parts.append("Via ProdLink!") 

    message_for_whatsapp = "\n".join(whatsapp_message_parts)
    
    # --- ENVIAR PARA O NÚMERO INDIVIDUAL ---
    whatsapp_url = f"https://api.whatsapp.com/send?phone={WHATSAPP_PHONE_NUMBER}&text={quote(message_for_whatsapp)}"
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
