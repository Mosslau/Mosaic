import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme'

// 自托管字型：拉丁字面用 IBM Plex（正文 + 等宽），中文回落到系统 UI 字族
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'

import './styles/tokens.css'
import './styles/base.css'
import './styles/card.css'
import './styles/landing.css'

import AnalysisGrid from './components/AnalysisGrid.vue'
import CompilerGrid from './components/CompilerGrid.vue'
import ConvergenceHero from './components/ConvergenceHero.vue'
import LanguageBoard from './components/LanguageBoard.vue'
import LanguageGrid from './components/LanguageGrid.vue'
import StatStrip from './components/StatStrip.vue'
import ThreePaths from './components/ThreePaths.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('ConvergenceHero', ConvergenceHero)
    app.component('StatStrip', StatStrip)
    app.component('ThreePaths', ThreePaths)
    app.component('LanguageGrid', LanguageGrid)
    app.component('AnalysisGrid', AnalysisGrid)
    app.component('CompilerGrid', CompilerGrid)
    app.component('LanguageBoard', LanguageBoard)
  },
} satisfies Theme
