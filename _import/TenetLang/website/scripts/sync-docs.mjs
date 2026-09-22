#!/usr/bin/env node
/**
 * 把仓库里的 Markdown 同步进 VitePress 的 srcDir（`docs/`），并把课程结构解析成
 * 主题组件消费的数据模块（`.vitepress/data/curriculum.json`）。
 *
 * `docs/` 是纯产物目录：随时可以删掉重建，任何手工编辑都会在下次 sync 时丢失。
 * 内容唯一真源始终是仓库里的 `languages/`、`analysis/`、`tenet/`。
 * 站点工程的整体说明见 `website/README.md`。
 *
 * 用法：node scripts/sync-docs.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SITE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const REPO_DIR = path.resolve(SITE_DIR, '..')
const DOCS_DIR = path.join(SITE_DIR, 'docs')
const CONTENT_DIR = path.join(SITE_DIR, 'content')
const DATA_FILE = path.join(SITE_DIR, '.vitepress', 'data', 'curriculum.json')

/** 三个内容族，顺序即首页与导航的呈现顺序 */
const FAMILIES = ['languages', 'analysis', 'tenet']

/** 六门语言：顺序、显示名与身份色 token */
const LANGUAGES = [
  { id: 'c', name: 'C', token: 'c' },
  { id: 'cpp', name: 'C++', token: 'cpp' },
  { id: 'go', name: 'Go', token: 'go' },
  { id: 'java', name: 'Java', token: 'java' },
  { id: 'py', name: 'Python', token: 'py' },
  { id: 'rs', name: 'Rust', token: 'rs' },
]

const CODE_LAYERS = [
  { dir: 'examples', label: '示例' },
  { dir: 'exercises', label: '练习' },
  { dir: 'project', label: '项目' },
]

// ---------------------------------------------------------------- 通用工具

const warnings = []
const warn = (msg) => warnings.push(msg)

/**
 * 只在内容真的变了才写盘。
 *
 * 监听模式下这个差别很关键：无脑重写 571 个文件会让 VitePress 对每一页发一次 HMR，
 * 增量写入则让「改一篇文档」只影响那一页。
 */
let written = 0
const expected = new Set()
function writeIfChanged(target, content) {
  expected.add(target)
  const next = Buffer.isBuffer(content) ? content : Buffer.from(content, 'utf8')
  try {
    if (fs.readFileSync(target).equals(next)) return false
  } catch {
    // 目标不存在或不可读，照常写入
  }
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, next)
  written++
  return true
}

/** 删掉 docs/ 里这次同步没有产出的文件（源文档被删除/改名后的残留页） */
function pruneOrphans() {
  let removed = 0
  const dirs = []
  for (const file of walk(DOCS_DIR)) {
    if (!expected.has(file)) {
      fs.rmSync(file, { force: true })
      removed++
    }
  }
  // 自底向上清掉空目录
  const collect = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue
      const full = path.join(dir, entry.name)
      collect(full)
      dirs.push(full)
    }
  }
  collect(DOCS_DIR)
  for (const dir of dirs.sort((a, b) => b.length - a.length)) {
    if (fs.readdirSync(dir).length === 0) fs.rmdirSync(dir)
  }
  return removed
}

function walk(dir, filter) {
  const out = []
  const stack = [dir]
  while (stack.length) {
    const cur = stack.pop()
    let entries
    try {
      entries = fs.readdirSync(cur, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      const full = path.join(cur, entry.name)
      if (entry.isDirectory()) {
        if (entry.name === 'node_modules' || entry.name === 'target' || entry.name === '.git') continue
        stack.push(full)
      } else if (!filter || filter(full)) {
        out.push(full)
      }
    }
  }
  return out.sort()
}

const toPosix = (p) => p.split(path.sep).join('/')

/** 仓库绝对路径 → 站点路由（去掉 .md，README/index 归一为目录路由） */
function routeOf(absPathInDocs) {
  let rel = toPosix(path.relative(DOCS_DIR, absPathInDocs))
    .replace(/\.md$/, '')
    .replace(/(^|\/)index$/, '$1')
  if (rel === 'index') rel = ''
  return '/' + rel
}

/** 仓库绝对路径 → docs 内的绝对路径（README.md 映射为 index.md） */
function docsPathOf(repoAbsPath) {
  const rel = toPosix(path.relative(REPO_DIR, repoAbsPath))
  return path.join(DOCS_DIR, rel.replace(/README\.md$/, 'index.md'))
}

function stripMd(text) {
  return text
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\*\*([^*]*)\*\*/g, '$1')
    .replace(/[*_]/g, '')
    .trim()
}

/** 估算阅读时长（分钟）：中文按 400 字/分，西文按 180 词/分 */
function readingMinutes(text) {
  const cjk = (text.match(/[\u3400-\u9fff\u3040-\u30ff]/g) || []).length
  const latin = (text.match(/[A-Za-z0-9_]+/g) || []).length
  return Math.max(1, Math.round(cjk / 400 + latin / 180))
}

/** 取 H1 之后的第一段连续 blockquote，作为该文档的一句话定位 */
function firstLede(text) {
  const lines = text.split('\n')
  const h1 = lines.findIndex((l) => /^#\s+/.test(l))
  const out = []
  let started = false
  for (const line of lines.slice(h1 + 1)) {
    const t = line.trim()
    if (t.startsWith('>')) {
      started = true
      out.push(t.replace(/^>\s?/, ''))
    } else if (started) {
      break
    } else if (t && !t.startsWith('>')) {
      break
    }
  }
  return stripMd(out.join(' '))
}

// -------------------------------------------------------- Markdown 同步

const copiedMd = new Set() // 仓库中的 md 绝对路径（已复制）
const ignoredLinks = new Set() // 指向"未收录内容"的链接，交给 ignoreDeadLinks

/**
 * 把代码区（围栏代码块 + 行内代码）替换成同长度的空字符。
 *
 * 代码里大量出现 `ops[0](7)`、`[捕获列表](参数)` 这类调用写法，直接对原文跑链接正则
 * 会把它们当成 Markdown 链接。掩码后长度不变，因此匹配到的下标可以直接映射回原文。
 */
function maskCode(md) {
  // 必须按 UTF-16 码元切分（split('') 而非 [...md]）：偏移量是用 line.length 累加的，
  // 文档里的 emoji 是非 BMP 字符，按码点切会让掩码位置与原文错位。
  const chars = md.split('')
  const blank = (from, to) => {
    for (let i = from; i < to && i < chars.length; i++) chars[i] = '\u0000'
  }

  let offset = 0
  let fence = null
  for (const line of md.split('\n')) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)
    if (marker) {
      const char = marker[1][0]
      if (!fence) fence = char
      else if (char === fence) fence = null
      blank(offset, offset + line.length)
    } else if (fence) {
      blank(offset, offset + line.length)
    } else {
      const inline = /`[^`\n]*`/g
      let hit
      while ((hit = inline.exec(line))) blank(offset + hit.index, offset + hit.index + hit[0].length)
    }
    offset += line.length + 1
  }
  return chars.join('')
}

/** 判断一个链接目标在站点里是什么：页面 / 未收录的源码资产 / 失效 */
function classifyLink(targetAbs, target) {
  if (fs.existsSync(targetAbs)) {
    if (fs.statSync(targetAbs).isDirectory()) {
      const hasIndex =
        copiedMd.has(path.join(targetAbs, 'README.md')) || copiedMd.has(path.join(targetAbs, 'index.md'))
      return hasIndex ? 'page' : 'asset'
    }
    if (/\.md$/i.test(target)) return copiedMd.has(targetAbs) ? 'page' : 'missing'
    // 其余（.html/.py/.yml/Cargo.toml…）都不作为站点页面收录，交给 ignoreDeadLinks
    return 'asset'
  }
  // 目标不存在：相对路径视为失效，绝对/外链不归这里管
  return /^\.\.?\//.test(target) ? 'missing' : 'asset'
}

/**
 * 复制单个 md：README.md → index.md、改写指向 README 的链接、记录死链白名单。
 * `targetOverride` 用于根 README 这类不能按目录索引落位的文件。
 */
function copyMarkdown(repoAbsPath, targetOverride) {
  const target = targetOverride ?? docsPathOf(repoAbsPath)
  const original = fs.readFileSync(repoAbsPath, 'utf8')
  const masked = maskCode(original)
  const srcDir = path.dirname(repoAbsPath)
  const relSource = toPosix(path.relative(REPO_DIR, repoAbsPath))

  const edits = []
  const linkRe = /\]\(\s*<([^>\s]+)>|\]\(\s*([^)\s]+)/g
  let hit
  while ((hit = linkRe.exec(masked))) {
    const url = hit[1] ?? hit[2]
    if (!url || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(url) || url.startsWith('#') || url.startsWith('/')) continue

    const [target0, hash = ''] = url.split('#')
    if (!target0) continue

    // 兼容 `](tenet/README)` 这种省略扩展名的写法，按 README.md 探测目标
    const isReadme = /(^|\/)README(\.md)?$/.test(target0)
    const probe = /(^|\/)README$/.test(target0) ? target0 + '.md' : target0
    const targetAbs = path.resolve(srcDir, probe)
    const kind = classifyLink(targetAbs, probe)

    // 站点里实际发出的链接：README 引用会被改写成目录索引
    const emitted = isReadme
      ? target0.replace(/README(\.md)?$/, 'index.md') + (hash ? '#' + hash : '')
      : url

    if (kind !== 'page') {
      // 与 VitePress 的归一化保持一致（去 query/hash、去扩展名、目录补 index），
      // 否则 ignoreDeadLinks 匹配不上
      const normalized = emitted.replace(/[?#].*$/, '').replace(/\.(md|html)$/, '')
      ignoredLinks.add(normalized)
      if (normalized.endsWith('/')) ignoredLinks.add(normalized + 'index')
    }
    if (kind === 'missing') warn(`失效链接 ${relSource} → ${url}`)

    if (isReadme) {
      const start = hit.index + hit[0].indexOf(url)
      edits.push({ start, end: start + url.length, text: emitted })
    }
  }

  // 从后往前替换，前面的下标才不会失效
  let md = original
  for (const edit of edits.sort((a, b) => b.start - a.start)) {
    md = md.slice(0, edit.start) + edit.text + md.slice(edit.end)
  }

  writeIfChanged(target, md)
  copiedMd.add(repoAbsPath)
  return target
}

/** 递归复制 content/ 里的手写页面与静态资源 */
function copyContent() {
  if (!fs.existsSync(CONTENT_DIR)) return 0
  const files = walk(CONTENT_DIR)
  for (const file of files) {
    const rel = path.relative(CONTENT_DIR, file)
    writeIfChanged(path.join(DOCS_DIR, rel), fs.readFileSync(file))
  }
  return files.length
}

// ------------------------------------------------------------ 结构解析

/** 从 roadmap 解析出「阶段」列表 */
function parseRoadmap(text, displayName, langId) {
  const chapters = []
  let cur = null
  let inGoal = false

  for (const raw of text.split('\n')) {
    const h2 = raw.match(/^##\s+(\d+)[.、]\s*(.+?)\s*$/)
    if (h2) {
      let title = h2[2].trim()
      if (title.startsWith(displayName + ' ')) title = title.slice(displayName.length + 1)
      cur = { n: Number(h2[1]), title, detail: null, goal: '' }
      chapters.push(cur)
      inGoal = false
      continue
    }
    if (/^##\s+/.test(raw)) {
      cur = null
      inGoal = false
      continue
    }
    if (!cur) continue

    const detail = raw.match(/详细展开版见\s*\[[^\]]*\]\(([^)]+)\)/)
    if (detail) {
      cur.detail = detail[1]
      continue
    }
    const h3 = raw.match(/^###\s+(.+?)\s*$/)
    if (h3) {
      inGoal = h3[1].trim() === '目标'
      continue
    }
    if (inGoal) {
      const t = raw.trim()
      if (t && !t.startsWith('>') && !t.startsWith('|') && !t.startsWith('-')) {
        cur.goal = stripMd(t)
        inGoal = false
      }
    }
  }

  for (const ch of chapters) {
    if (!ch.detail) {
      warn(`${langId} roadmap 阶段 ${ch.n} 缺少「详细展开版」链接`)
      ch.link = null
      ch.dir = null
      continue
    }
    const detailAbs = path.resolve(REPO_DIR, 'languages', langId, ch.detail)
    ch.dir = path.dirname(toPosix(ch.detail))
    ch.link = routeOf(docsPathOf(detailAbs))
    const detailText = fs.existsSync(detailAbs) ? fs.readFileSync(detailAbs, 'utf8') : ''
    ch.minutes = readingMinutes(detailText)
    ch.chars = detailText.length

    // 代码层：examples / exercises / project 里是否有配套内容，入口在哪
    const code = []
    for (const layer of CODE_LAYERS) {
      const layerDir = path.resolve(REPO_DIR, 'languages', langId, ch.dir, layer.dir)
      if (!fs.existsSync(layerDir)) continue
      const mds = walk(layerDir, (f) => f.endsWith('.md'))
      if (!mds.length) continue
      const entry = mds.find((f) => path.basename(f) === 'README.md') ?? mds[0]
      code.push({ label: layer.label, link: routeOf(docsPathOf(entry)) })
    }
    ch.code = code
  }

  return chapters
}

/** 解析 analysis/<id>/README.md 的主题表 */
function parseAnalysis(id) {
  const readme = path.join(REPO_DIR, 'analysis', id, 'README.md')
  if (!fs.existsSync(readme)) return null
  const text = fs.readFileSync(readme, 'utf8')
  const lines = text.split('\n')

  const notes = []
  for (const line of lines) {
    const m = line.match(/^\|\s*(\d+)\s*\|(.+)\|\s*$/)
    if (!m) continue
    const cells = line.split('|').map((c) => c.trim())
    const linkCell = cells[2] ?? ''
    const link = linkCell.match(/\]\(([^)]+)\)/)
    if (!link) continue
    const abs = path.resolve(path.dirname(readme), link[1])
    notes.push({
      n: Number(m[1]),
      title: stripMd(linkCell),
      question: stripMd(cells[3] ?? ''),
      demo: (cells[4] ?? '').replace(/`/g, ''),
      link: routeOf(docsPathOf(abs)),
      minutes: fs.existsSync(abs) ? readingMinutes(fs.readFileSync(abs, 'utf8')) : 1,
    })
  }

  const thesis =
    lines
      .map((l) => l.trim())
      .find((l) => l && !l.startsWith('#') && !l.startsWith('>') && !l.startsWith('|') && !l.startsWith('```')) ?? ''

  const name = { c: 'C', cpp: 'C++', go: 'Go', java: 'Java', py: 'Python', rs: 'Rust' }[id] ?? id.toUpperCase()

  return {
    id,
    name,
    token: id,
    title: stripMd((text.match(/^#\s+(.+)$/m) || [])[1] ?? name),
    lede: firstLede(text),
    thesis: stripMd(thesis),
    link: routeOf(docsPathOf(readme)),
    notes,
  }
}

/** 解析 tenet/README.md 里的编译器对照表 */
function parseTenet() {
  const readme = path.join(REPO_DIR, 'tenet', 'README.md')
  const text = fs.readFileSync(readme, 'utf8')
  const compilers = []
  for (const line of text.split('\n')) {
    const m = line.match(/^\|\s*\[`([^`]+)\/`\]\(([^)]+)\)\s*\|(.+)\|\s*$/)
    if (!m) continue
    const cells = line.split('|').map((c) => c.trim())
    compilers.push({
      // slug 是短名（rs/cpp/arm64），dir 是磁盘目录名（compiler-rs），
      // 消费方统一用 `compiler-${slug}` 拼显示名
      slug: m[1].replace(/^compiler-/, ''),
      dir: m[1],
      link: routeOf(docsPathOf(path.resolve(path.dirname(readme), m[2], 'README.md'))),
      frontend: stripMd(cells[2] ?? ''),
      backend: stripMd(cells[3] ?? ''),
      tests: stripMd(cells[4] ?? ''),
    })
  }
  const design = path.join(REPO_DIR, 'tenet', 'Tenet架构设计.md')
  return {
    lede: firstLede(text),
    design: fs.existsSync(design)
      ? { title: 'Tenet 架构设计', link: routeOf(docsPathOf(design)), minutes: readingMinutes(fs.readFileSync(design, 'utf8')) }
      : null,
    compilers,
  }
}

// ------------------------------------------------------------------ 主流程

// 不清空 docs/：配合 writeIfChanged 做增量写入，只有内容变化才落盘，
// 避免监听模式下每次保存都触发整站 HMR。残留文件由 pruneOrphans 收尾。
fs.mkdirSync(DOCS_DIR, { recursive: true })

const contentCount = copyContent()

// 1) 先把三个族的 md 全部登记并复制（先登记后校验链接，避免顺序依赖）
const familyFiles = {}
for (const family of FAMILIES) {
  const root = path.join(REPO_DIR, family)
  if (!fs.existsSync(root)) {
    warn(`缺少内容族目录 ${family}/`)
    familyFiles[family] = []
    continue
  }
  familyFiles[family] = walk(root, (f) => f.endsWith('.md'))
}
for (const family of FAMILIES) {
  for (const file of familyFiles[family]) copiedMd.add(file)
}
let copiedCount = 0
for (const family of FAMILIES) {
  for (const file of familyFiles[family]) {
    copyMarkdown(file)
    copiedCount++
  }
}

// 2) 仓库根 README → 站点「总览」页（不能走 README→index 的默认映射，那会覆盖首页）
const rootReadme = path.join(REPO_DIR, 'README.md')
if (fs.existsSync(rootReadme)) copyMarkdown(rootReadme, path.join(DOCS_DIR, 'about.md'))

// 3) 解析课程结构
const languages = LANGUAGES.map((meta) => {
  const langDir = path.join(REPO_DIR, 'languages', meta.id)
  const roadmaps = fs
    .readdirSync(langDir, { withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith('.md'))
    .map((e) => e.name)
  if (roadmaps.length !== 1) warn(`languages/${meta.id}/ 顶层应有且仅有 1 篇 roadmap，实际 ${roadmaps.length} 篇`)
  const roadmapPath = path.join(langDir, roadmaps[0])
  const text = fs.readFileSync(roadmapPath, 'utf8')

  return {
    ...meta,
    tagline: firstLede(text),
    link: routeOf(docsPathOf(roadmapPath)),
    board: `/languages/${meta.id}/`,
    docs: familyFiles.languages.filter((f) => f.startsWith(langDir + path.sep)).length,
    chapters: parseRoadmap(text, meta.name, meta.id),
  }
})

const analysis = ['rs', 'cpp', 'java', 'py'].map(parseAnalysis).filter(Boolean)
const tenet = parseTenet()

// 4) 生成每种语言的卡片总览页
for (const lang of languages) {
  const target = path.join(DOCS_DIR, 'languages', lang.id, 'index.md')
  writeIfChanged(
    target,
    [
      '---',
      `title: ${lang.name}`,
      `description: ${lang.tagline.replace(/\n/g, ' ')}`,
      'aside: false',
      'outline: false',
      '---',
      '',
      `<LanguageBoard lang="${lang.id}" />`,
      '',
    ].join('\n'),
  )
}

// 5) 写出主题消费的数据模块
const data = {
  languages,
  analysis,
  tenet,
  stats: {
    languages: languages.length,
    chapters: languages.reduce((sum, l) => sum + l.chapters.length, 0),
    languageDocs: familyFiles.languages.length,
    analysisDocs: familyFiles.analysis.length,
    tenetDocs: familyFiles.tenet.length,
  },
  ignoredLinks: [...ignoredLinks].sort(),
}

writeIfChanged(DATA_FILE, JSON.stringify(data, null, 2) + '\n')

// 6) 清掉源文档已删除/改名留下的残留页，并汇总输出
const pruned = pruneOrphans()

console.log('')
console.log(`  手写页面      ${contentCount}`)
console.log(`  复制 Markdown ${copiedCount + (fs.existsSync(rootReadme) ? 1 : 0)}`)
console.log(
  `  解析结构      ${languages.length} 门语言 / ${data.stats.chapters} 个阶段 / ` +
    `${analysis.length} 个分析台 / ${tenet.compilers.length} 个编译器`,
)
console.log(`  写入变更      ${written} 个文件${pruned ? `，清理残留 ${pruned} 个` : ''}`)
console.log(`  忽略的资产链接 ${data.ignoredLinks.length}`)
if (warnings.length) {
  console.log('')
  console.log(`  ⚠️  ${warnings.length} 条提示：`)
  for (const w of warnings.slice(0, 40)) console.log(`     - ${w}`)
  if (warnings.length > 40) console.log(`     …… 其余 ${warnings.length - 40} 条已省略`)
}
console.log('')
