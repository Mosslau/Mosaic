import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'

const here = path.dirname(fileURLToPath(import.meta.url))

/**
 * 课程结构由 scripts/sync-docs.mjs 生成。缺失时退化成空站，便于直接跑 vitepress 排查问题。
 */
function loadCurriculum() {
  const file = path.join(here, 'data', 'curriculum.json')
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    console.warn('[tenetlang] 未找到 .vitepress/data/curriculum.json，请先运行 `npm run sync`')
    return { languages: [], analysis: [], tenet: { compilers: [] }, stats: {}, ignoredLinks: [] }
  }
}

const data = loadCurriculum()
const pad = (n) => String(n).padStart(2, '0')

/**
 * 全文搜索的中文分词器。
 *
 * MiniSearch 默认按空白与标点切词，中文长句会变成一个整词，导致「语法」这类查询
 * 搜不到「基础语法阶段」。这里改用 Intl.Segmenter 做词级切分。
 *
 * 注意：这个函数会被 VitePress 序列化进页面（`new Function` 还原），所以它必须
 * **自包含**——不能引用模块作用域的任何变量，缓存也只能挂在 globalThis 上。
 */
function tokenize(text: string): string[] {
  const g = globalThis as any
  let segmenter = g.__tenetLangSegmenter
  if (segmenter === undefined) {
    segmenter =
      typeof Intl !== 'undefined' && 'Segmenter' in Intl
        ? new (Intl as any).Segmenter('zh-Hans', { granularity: 'word' })
        : null
    g.__tenetLangSegmenter = segmenter
  }
  if (!segmenter) return String(text).split(/[\n\r\p{Z}\p{P}]+/u)

  const terms: string[] = []
  for (const part of segmenter.segment(String(text)) as Iterable<{ segment: string }>) {
    const term = part.segment
    // 丢掉纯标点/空白切出来的碎片，保留含字母、数字或汉字的词
    if (term.trim() && /[\p{L}\p{N}]/u.test(term)) terms.push(term)
  }
  return terms
}


const nav = [
  {
    text: '学习',
    items: [
      { text: '六门语言总览', link: '/studies/' },
      ...data.languages.map((lang) => ({
        text: `${lang.name} · ${lang.chapters.length} 阶段`,
        link: lang.board,
      })),
    ],
  },
  {
    text: '分析',
    items: [
      { text: '语言设计分析总览', link: '/analysis/' },
      ...data.analysis.map((item) => ({ text: `${item.name} 的设计取舍`, link: item.link })),
    ],
  },
  { text: 'Tenet', link: '/tenet/' },
  { text: '语言域总览', link: '/about' },
]

/** 每种语言一个侧边栏：章节总览 → roadmap → 各阶段正文（代码层由正文与卡片进入） */
const langSidebars = Object.fromEntries(
  data.languages.map((lang) => [
    `/studies/${lang.id}/`,
    [
      {
        text: lang.name,
        items: [
          { text: '章节总览', link: lang.board },
          { text: '学习路线 Roadmap', link: lang.link },
        ],
      },
      {
        text: '阶段',
        collapsed: false,
        items: lang.chapters
          .filter((chapter) => chapter.link)
          .map((chapter) => ({
            text: `${pad(chapter.n)} ${chapter.title}`,
            link: chapter.link,
          })),
      },
    ],
  ]),
)

const sidebar = {
  '/studies/': [
    {
      text: '六门语言',
      items: data.languages.map((lang) => ({
        text: `${lang.name} · ${lang.chapters.length} 阶段`,
        link: lang.board,
      })),
    },
  ],
  '/analysis/': [
    { text: '语言设计分析', items: [{ text: '总览', link: '/analysis/' }] },
    ...data.analysis.map((item) => ({
      text: item.name,
      collapsed: false,
      items: [
        { text: '分析路线', link: item.link },
        ...item.notes.map((note) => ({ text: `${pad(note.n)} ${note.title}`, link: note.link })),
      ],
    })),
  ],
  '/tenet/': [
    {
      text: 'Tenet',
      items: [
        { text: '语言与编译器入口', link: '/tenet/' },
        ...(data.tenet.design ? [{ text: data.tenet.design.title, link: data.tenet.design.link }] : []),
        ...data.tenet.compilers.map((compiler) => ({
          text: `compiler-${compiler.slug}`,
          link: compiler.link,
        })),
      ],
    },
  ],
  ...langSidebars,
}

export default defineConfig({
  lang: 'zh-CN',
  title: 'Mosaic · 语言域',
  description: '万语归宗——六门语言的学习笔记、设计分析与 Tenet 语言实现',
  srcDir: 'docs',
  cleanUrls: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    ['meta', { name: 'theme-color', content: '#f2f5f8' }],
    // 首次绘制前恢复侧边栏的折叠状态与宽度，避免「先展开再收起」的闪动。
    // 与 SidebarResizer.vue 共用同一组 localStorage 键，键名改动需同步。
    [
      'script',
      {},
      `(function(){try{var d=document.documentElement;` +
        `if(localStorage.getItem('tenetlang:sidebar-collapsed')==='1'){d.classList.add('sidebar-collapsed');}` +
        `var w=parseInt(localStorage.getItem('tenetlang:sidebar-width')||'',10);` +
        `if(w>=200&&w<=440){d.style.setProperty('--vp-sidebar-width',w+'px');}` +
        `}catch(e){}})();`,
    ],
  ],
  markdown: {
    theme: { light: 'github-light', dark: 'github-dark' },
    config(md) {
      // 行内代码里的 C 初始化列表 {{1,2,3}}、Go 模板 {{ .Values.x }} 会被 Vue 当成插值。
      // 给所有行内 <code> 加上 v-pre，让它们原样输出。
      const fallback = (tokens, idx) =>
        `<code>${md.utils.escapeHtml(tokens[idx].content)}</code>`
      const original = md.renderer.rules.code_inline
      md.renderer.rules.code_inline = (tokens, idx, options, env, self) =>
        (original ?? fallback)(tokens, idx, options, env, self).replace('<code', '<code v-pre')

      // C++/Rust 的泛型写法（Stack<T>、Arc<Mutex<T>>、Box<dyn Trait>…）会被 markdown-it
      // 当成原始 HTML 标签，交给 Vue 后会因为「标签未闭合」直接构建失败，在浏览器里也会
      // 被当成未知标签吞掉。这里把它们降级成普通文本，由渲染器转义成 &lt;T&gt; 正常显示。
      // 只保留文档里真正刻意使用的行内 HTML（<br>）。
      const KEEP_HTML = new Set(['br'])
      md.core.ruler.push('tenet-escape-stray-html', (state) => {
        for (const token of state.tokens) {
          if (token.type !== 'inline' || !token.children) continue
          for (const child of token.children) {
            if (child.type !== 'html_inline') continue
            const name = (child.content.match(/^<\/?([A-Za-z][A-Za-z0-9-]*)/) ?? [])[1]
            if (name && KEEP_HTML.has(name.toLowerCase())) continue
            child.type = 'text'
          }
        }
      })
    },
  },
  themeConfig: {
    logo: { light: '/logo.svg', dark: '/logo-dark.svg' },
    nav,
    sidebar,
    // 仓库入口。默认会排在亮暗切换之后，样式里用 order 把它提到「语言域总览」正后方。
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Mosslau/Mosaic', ariaLabel: 'GitHub 仓库' },
    ],
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一节', next: '下一节' },
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色',
    darkModeSwitchTitle: '切换到深色',
    sidebarMenuLabel: '目录',
    returnToTopLabel: '回到顶部',
    externalLinkIcon: true,
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: {
            tokenize,
          },
        },
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            displayDetails: '显示详情',
            resetButtonTitle: '清除查询',
            backButtonTitle: '返回',
            noResultsText: '没有找到相关内容',
            footer: {
              selectText: '选择',
              selectKeyAriaLabel: '回车',
              navigateText: '切换',
              navigateUpKeyAriaLabel: '上箭头',
              navigateDownKeyAriaLabel: '下箭头',
              closeText: '关闭',
              closeKeyAriaLabel: 'Esc',
            },
          },
        },
      },
    },
  },
  // 指向未收录源码文件（.py/.rs/.yml/Cargo.toml…）的链接由 sync 脚本精确收集。
  // VitePress 会把链接交给 markdown-it 的 normalizeLink 归一化（例如给 `../x` 补成 `./../x`）
  // 之后才匹配，所以这里对每条记录做「可选 ./ 前缀」的宽容匹配，而不是依赖其内部细节。
  ignoreDeadLinks: (data.ignoredLinks ?? []).map(
    (link: string) =>
      new RegExp(`^(\\./)?${link.replace(/^\.\//, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`),
  ),
})
