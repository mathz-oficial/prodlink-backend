# ProdLink Backend

API RESTful para processamento de links de produtos (Amazon, Mercado Livre, AliExpress) e geração de links de compartilhamento para o WhatsApp.

## Funcionalidades

* Extração de título, preço, imagem, moeda e descrição do produto a partir de uma URL.
* Geração de links diretos para compartilhamento no WhatsApp com informações formatadas.
* Suporte a CORS para integração com frontends em domínios diferentes.

## Pré-requisitos

* Python 3.7+ (gerenciado pelo Render)
* `pip` (gerenciado pelo Render)

## Deploy no Render (Recomendado)

O Render é uma plataforma de nuvem que facilita muito o deploy de aplicações Python.

1.  **Crie uma conta gratuita** no [Render](https://render.com/).
2.  No seu dashboard, clique em `New` -> `Web Service`.
3.  **Conecte sua conta GitHub** e selecione o repositório `prodlink-backend`.
4.  Configure as seguintes opções:
    * **Name**: `prodlink-backend` (ou o nome que preferir)
    * **Region**: Escolha a mais próxima do Brasil (ex: `São Paulo` se disponível, ou `Oregon`/`Frankfurt` como alternativa).
    * **Branch**: `main` (ou a branch principal do seu projeto)
    * **Root Directory**: Deixe em branco (ou `/`)
    * **Runtime**: `Python 3`
    * **Build Command**: `pip install -r requirements.txt`
    * **Start Command**: `gunicorn app:app` (o `gunicorn` é um servidor web otimizado para produção)
5.  **Adicione uma Variável de Ambiente**:
    * Clique em `Advanced` -> `Add Environment Variable`.
    * **Key**: `WHATSAPP_PHONE_NUMBER`
    * **Value**: `SEU_NUMERO_AQUI` (ex: `5511987654321` - com código do país e DDD)
6.  Clique em `Create Web Service`. O Render irá clonar seu código, instalar as dependências e iniciar sua aplicação.

## Rotas da API

| Método | Rota                     | Descrição                                         | Body de Exemplo               | Retorno de Exemplo                                                                                                        |
| :----- | :----------------------- | :------------------------------------------------ | :---------------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| `GET`  | `/`                      | Verifica se a API está online.                    | N/A                           | `ProdLink Backend está online! Use a rota /api/process_product_link para processar links.`                                |
| `POST` | `/api/process_product_link` | Processa a URL de um produto e retorna suas informações. | `{"url": "https://..."}`      | `{"title": "...", "price": "...", "currency": "...", "image": "...", "whatsapp_link": "...", "description": "..."}` |
