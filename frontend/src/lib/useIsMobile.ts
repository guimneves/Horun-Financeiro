import { useEffect, useState } from 'react'

// Abaixo do ponto de quebra `md` do Tailwind (768 px) a interface vira a de
// celular: gaveta no lugar da barra lateral e listas em cartões
// (Prompt_Horun_Modulo.md, seção 13).
const QUERY = '(max-width: 767.98px)'

export function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(() => typeof window !== 'undefined' && window.matchMedia(QUERY).matches)
  useEffect(() => {
    const media = window.matchMedia(QUERY)
    const onChange = () => setMobile(media.matches)
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return mobile
}
