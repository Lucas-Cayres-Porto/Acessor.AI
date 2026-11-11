# 🚀 Publicação da Apresentação no Google Apps Script

> 🌐 **Link Público Ativo (Acesso Liberado para Todos):**  
> **https://script.google.com/macros/s/AKfycbwnfUfDq7RYxt0-UZ0IkxkiyNRIua8c7ZtpAvmL4sPnSocFsjbYmkPDFKMfSCv3YeclnQ/exec**

---

### Passo 1: Criar o Projeto
1. Acesse **[script.google.com](https://script.google.com/)** com sua conta Google.
2. Clique no botão **+ Novo projeto** (canto superior esquerdo).
3. Renomeie o projeto no topo de *"Projeto sem título"* para **`Apresentação Assessor.AI`**.

---

### Passo 2: Configurar o Código Backend (`Código.gs`)
1. No arquivo `Código.gs` que já vem aberto, apague tudo e cole o código abaixo (disponível em `google_apps_script/Codigo.gs`):

```javascript
function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Assessor.AI · Relatório Geral da Arquitetura & Código')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
```

2. Pressione **Ctrl + S** para salvar.

---

### Passo 3: Criar o Arquivo HTML (`index.html`)
1. No menu lateral esquerdo, ao lado de **Arquivos**, clique no ícone de mais (**+**) e escolha **HTML**.
2. Digite o nome: **`index`** (o Google criará automaticamente como `index.html`).
3. Abra o arquivo local [`google_apps_script/index.html`](file:///c:/Users/lucasporto-ieg/OneDrive%20-%20Instituto%20J&F/Área%20de%20Trabalho/Matérias%20TECH/Inteligência%20Artificial/códigos/juiz_tardio/google_apps_script/index.html), selecione tudo (**Ctrl + A**), copie (**Ctrl + C**) e cole dentro do editor do Google Apps Script substituindo todo o conteúdo.
4. Pressione **Ctrl + S** para salvar.

---

### Passo 4: Publicar e Gerar o Link Público
1. No canto superior direito, clique no botão azul **Implantar** (Deploy) ➔ **Nova implantação**.
2. Na janela que abrir, clique na engrenagem (**⚙️ Selecionar tipo**) e escolha **App da Web**.
3. Configure os seguintes campos:
   * **Descrição:** `Apresentação Assessor.AI`
   * **Executar como:** `Eu (seu_email@...)`
   * **Quem pode acessar:** `Qualquer pessoa` *(ou "Anyone", para que todos possam abrir sem login)*.
4. Clique no botão azul **Implantar**.
5. Se o Google solicitar autorização de acesso, clique em **Revisar permissões**, escolha sua conta e confirme.
6. Pronto! O Google gerará um link público no formato:
   `https://script.google.com/macros/s/AKfycb.../exec`

Copie esse link e envie para quem você quiser!
