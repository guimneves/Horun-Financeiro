/** Rodando sob o Horun Core? O gateway serve o módulo em /m/financeiro/
 * (vite `base`); no desenvolvimento local o BASE_URL é "/". */
export const UNDER_CORE = import.meta.env.BASE_URL.startsWith('/m/')
