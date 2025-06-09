from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import re

app = Flask(__name__)
# CORS é fundamental para permitir que seu frontend (em outro domínio)
# se comunique com este backend.
CORS(app) 

# --- Configurações Importantes ---
# Este número será o destino das mensagens do WhatsApp.
# Em produção (no Render), o valor virá de uma variável de ambiente.
# Em desenvolvimento, usará o valor padrão (5511999999999).
WHATSAPP_PHONE_NUMBER = os.environ.get("WHATSAPP_PHONE_NUMBER", "5581973085768") 
WHATSAPP_API_URL = "https://api.whatsapp.com/send"

# Dicionário com seletores CSS para extrair informações dos sites.
# EXTREMAMENTE IMPORTANTE: Seletores são sensíveis a mudanças no site.
# Se um site mudar sua estrutura HTML, você precisará atualizar os seletores aqui.
SITE_SELECTORS = {
    "amazon.com": {
        "title": "#productTitle",
        "price": ".a-price-whole", # Preço principal
        "image": "#landingImage",
        "currency": ".a-price-symbol", # Símbolo da moeda
        "description": "#productDescription span" # Descrição
    },
    "mercadolivre.com.br": {
        "title": ".ui-pdp-title",
        "price": ".andes-money-amount__fraction",
        "image": ".ui-pdp-gallery__figure img",
        "currency": ".andes-money-amount__currency-symbol",
        "description": ".ui-pdp-description__content"
    },
    "aliexpress.com": {
        "title": ".product-title-text",
        "price": ".product-price-value",
        "image": ".magnifier-image",
        "currency": ".product-price-currency",
        "description": ".product-description-content" # Pode variar bastante no Ali
    },
}

def extract_text(soup, selector):
    """Extrai o texto de um elemento usando um seletor CSS."""
    element = soup.select_one(selector)
    return element.get_text(strip=True) if element else ""

def extract_attr(soup, selector, attr):
    """Extrai um atributo (ex: 'src' de uma imagem) de um elemento."""
    element = soup.select_one(selector)
    return element[attr] if element and attr in element.attrs else ""

def clean_price(price_text):
    """Limpa o texto do preço, removendo caracteres indesejados e formatando."""
    price_text = price_text.replace(" ", "").replace("\n", "").replace(",", ".")
    # Usa expressão regular para pegar apenas números e pontos/vírgulas
    match = re.search(r'(\d[\d\.,]*)', price_text)
    if match:
        cleaned = match.group(1).replace(",", ".") # Garante ponto como decimal
        return cleaned
    return ""

def extract_product_info(url):
    """
    Faz o scraping das informações do produto de uma URL.
    Tenta ser mais robusto na extração de preço e imagem.
    """
    try:
        # User-Agent é importante para simular um navegador real e evitar bloqueios.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10) # Timeout para evitar travamentos
        response.raise_for_status() # Lança um erro para status HTTP ruins (4xx ou 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extrai o domínio da URL (ex: amazon.com, mercadolivre.com.br)
        domain = urlparse(url).netloc.replace("www.", "")

        selectors = None
        # Procura qual site na nossa lista o domínio corresponde
        for site_key, site_data in SITE_SELECTORS.items():
            if site_key in domain:
                selectors = site_data
                break

        if not selectors:
            return {"error": "Site não suportado. Tente Amazon, Mercado Livre ou AliExpress."}

        # --- Extração de dados ---
        title = extract_text(soup, selectors["title"])
        price_raw = extract_text(soup, selectors["price"])
        price = clean_price(price_raw) # Limpa o preço
        currency = extract_text(soup, selectors.get("currency", ""))
        image = extract_attr(soup, selectors["image"], "src")
        description = extract_text(soup, selectors.get("description", ""))

        # Tentativa de pegar imagem alternativa se a principal não for encontrada
        if not image:
            # Ex: Amazon pode ter "data-a-dynamic-image" ou "data-old-hires"
            image = extract_attr(soup, selectors["image"], "data-a-dynamic-image") 
            if image:
                # Se for um JSON string, tenta pegar a primeira URL
                try:
                    import json
                    img_dict = json.loads(image)
                    image = next(iter(img_dict)) # Pega a primeira chave (URL da imagem)
                except json.JSONDecodeError:
                    pass # Se não for JSON, mantém o que for.

        # Adiciona verificação para URL de imagem que pode estar faltando o esquema (http/https)
        if image and not image.startswith(('http://', 'https://')):
            # Tenta construir uma URL absoluta. Pode precisar de mais lógica para domínios complexos.
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            image = base_url + image if image.startswith('/') else base_url + '/' + image


        product = {
            "url": url,
            "title": title if title else "Título não disponível",
            "price": price if price else "Preço não disponível",
            "currency": currency,
            "image": image if image else "https://via.placeholder.com/150?text=Sem+Imagem", # Imagem padrão
            "domain": domain,
            "description": description if description else "Descrição não disponível" # Nova feature
        }

        return product

    except requests.exceptions.RequestException as e:
        return {"error": f"Erro ao acessar a URL: {e}. Verifique se o link está correto."}
    except Exception as e:
        return {"error": f"Erro inesperado ao processar o link: {e}"}

def generate_whatsapp_link(product_info):
    """Gera o link para compartilhar no WhatsApp com base nas informações do produto."""
    title = product_info.get('title', 'Produto').replace('*', '').replace('_', '') # Remove markdown para não conflitar
    price = product_info.get('price', 'Preço não disponível')
    currency = product_info.get('currency', '')
    url = product_info['url']

    # Monta a mensagem que aparecerá no WhatsApp
    message = f"Confira este produto!\n\n"
    message += f"📦 *{title}*\n"
    message += f"💰 *Preço:* {currency}{price}\n"
    message += f"🔗 *Link:* {url}\n\n"
    message += f"🚀 Via ProdLink!" # Um pequeno "branding"

    # Codifica a mensagem para URL (necessário para caracteres especiais e espaços)
    whatsapp_url = f"{WHATSAPP_API_URL}?phone={WHATSAPP_PHONE_NUMBER}&text={requests.utils.quote(message)}"
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

    # Verifica se a URL é válida (melhoria: validação básica)
    if not url.startswith(('http://', 'https://')):
        return jsonify({"error": "Formato de URL inválido. Use 'http://' ou 'https://'."}), 400

    product_info = extract_product_info(url)

    if "error" in product_info:
        return jsonify(product_info), 400 # Retorna o erro específico do scraping

    whatsapp_link = generate_whatsapp_link(product_info)
    product_info["whatsapp_link"] = whatsapp_link

    return jsonify(product_info)

@app.route('/')
def home():
    """Rota de teste simples para verificar se o backend está online."""
    return "ProdLink Backend está online! Use a rota /api/process_product_link para processar links."

if __name__ == '__main__':
    # A porta 5000 é a padrão para Flask. Em ambientes de deploy, o Render pode usar outra.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True é bom para desenvolvimento
