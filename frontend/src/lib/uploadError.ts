/** Mensagem de erro de envio de planilha. Quando o navegador nem consegue
 * ler o arquivo (visto na prática: planilha aberta no Excel, que trava o
 * arquivo no Windows), o fetch falha sem resposta do servidor — dizer isso,
 * em vez de um "Failed to fetch" sem sentido. */
export function uploadErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof TypeError || (err instanceof DOMException && err.name === 'NotReadableError')) {
    return (
      'Não foi possível enviar o arquivo — se a planilha estiver aberta no Excel, feche-a e tente de novo ' +
      '(ou o servidor pode estar fora do ar).'
    )
  }
  return err instanceof Error ? err.message : fallback
}
