# @horun/design-system

Identidade visual compartilhada de todos os módulos do Horun (ver `../Prompt_Horun_Core.md`, seção 2). Não é publicado no npm. O frontend do Core usa por caminho relativo (`file:../design-system`, mesmo repositório); **cada módulo leva uma cópia** em `frontend/vendor/horun-design-system/`, gerada por `../scripts/vendor_design_system.py` (o `create_horun_module.py` já faz isso). Motivo: o build Docker de um módulo só enxerga o próprio repositório — um caminho até a pasta do Core funciona na máquina de quem desenvolve e quebra no servidor. **Ao mudar algo aqui, aumente `version` no `package.json`** e rode o script em cada módulo (`--check` mostra quem ficou desatualizado).

## Conteúdo

- `src/tokens.css` — paleta de cores (3 temas: claro/dim/escuro) e reset básico. Módulo importa este arquivo **antes** de definir seus próprios tokens específicos (se precisar de algum).
- `src/ThemeProvider.tsx` / `useTheme` — contexto React do tema, com persistência **compartilhada entre módulos** (mesma chave de `localStorage`).
- `src/ThemeToggle.tsx` — botão pronto de troca de tema.
- `src/HorunFooter.tsx` — rodapé padrão (logo NQTR + créditos), mesmo em todo módulo.
- `src/assets/nqtr-logo.png` — logo oficial do laboratório, fonte única (não duplicar em cada módulo).

## Uso num módulo

```tsx
import '@horun/design-system/src/tokens.css'
import { ThemeProvider, ThemeToggle, HorunFooter } from '@horun/design-system'

function App() {
  return (
    <ThemeProvider>
      {/* ... */}
      <ThemeToggle />
      <HorunFooter moduleName="Horun · Meu Módulo" />
    </ThemeProvider>
  )
}
```

## Por que não é um pacote npm publicado

Nesta fase (poucos módulos, um só desenvolvedor principal), referenciar por `file:` evita a complexidade/custo de manter um registro npm privado. Se o número de módulos/colaboradores crescer, publicar como pacote versionado (registro privado ou GitHub Packages) é o passo natural seguinte — sem mudar a API dos componentes.
