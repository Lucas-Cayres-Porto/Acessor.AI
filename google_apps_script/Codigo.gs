function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Assessor.AI · Relatório Geral da Arquitetura & Código')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
