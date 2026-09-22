#!/usr/bin/env node
/**
 * 开发服务器：启动 VitePress，并监听仓库里的文档源。
 *
 * 内容真源是域根下的 `studies/`、`analysis/`、`tenet/` 与域根 README，`docs/` 只是产物。
 * 这个脚本让你**只改原文**即可：原文一变就重跑一次同步，VitePress 的 HMR 再把页面刷出来，
 * 不需要手工执行 `npm run sync`，也不需要碰 `docs/` 里的任何文件。
 *
 * 用法：node scripts/dev.mjs
 */
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SITE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const REPO_DIR = path.resolve(SITE_DIR, '..')
const SYNC = path.join(SITE_DIR, 'scripts', 'sync-docs.mjs')
const VITEPRESS = path.join(SITE_DIR, 'node_modules', 'vitepress', 'bin', 'vitepress.js')

/** 需要监听的文档源：三个内容族（域根）+ 手写页面目录（站点内） */
const WATCH_DIRS = [
  path.join(REPO_DIR, 'studies'),
  path.join(REPO_DIR, 'analysis'),
  path.join(REPO_DIR, 'tenet'),
  path.join(SITE_DIR, 'content'),
]
/** 域根 README 会被复制成站点的「总览」页，也要监听 */
const WATCH_FILES = [path.join(REPO_DIR, 'README.md')]

const DEBOUNCE_MS = 180

function runSync({ verbose }) {
  const started = Date.now()
  const result = spawnSync(process.execPath, [SYNC], { cwd: SITE_DIR, encoding: 'utf8' })
  const elapsed = Date.now() - started
  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.trim()

  if (result.status !== 0) {
    console.error('\n✖ 同步失败：')
    console.error(output)
    return false
  }
  if (verbose) {
    console.log(output)
    return true
  }

  // 监听触发的重同步只报一行，避免刷屏；有告警时把告警完整带出来
  const warnings = output
    .split('\n')
    .filter((line) => line.trim().startsWith('- ') || line.includes('⚠️'))
  const stamp = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  console.log(`  ↻ ${stamp} 已重新同步（${elapsed}ms）`)
  if (warnings.length) {
    console.log(warnings.map((w) => `    ${w.trim()}`).join('\n'))
  }
  return true
}

console.log('首次同步…')
if (!runSync({ verbose: true })) process.exit(1)

// ---------------------------------------------------------------- 文件监听

let timer = null
let pending = new Set()

const shouldReact = (filePath) => {
  if (!filePath) return true
  if (filePath.endsWith('.md') || filePath.endsWith('.markdown')) return true
  // content/ 下的静态资源（logo、favicon 等）也要跟着重新复制
  return path.resolve(filePath).startsWith(path.join(SITE_DIR, 'content') + path.sep)
}

const watchers = []
for (const target of [...WATCH_DIRS, ...WATCH_FILES]) {
  if (!fs.existsSync(target)) continue
  try {
    const watcher = fs.watch(target, { recursive: fs.statSync(target).isDirectory() }, (_event, filename) => {
      if (!shouldReact(filename)) return
      pending.add(filename ? path.join(target, filename) : target)
      clearTimeout(timer)
      timer = setTimeout(() => {
        const changed = [...pending]
        pending = new Set()
        const label = changed.length === 1 ? path.relative(REPO_DIR, changed[0]) : `${changed.length} 个文件`
        console.log(`\n  ● ${label} 有变化`)
        runSync({ verbose: false })
      }, DEBOUNCE_MS)
    })
    watchers.push(watcher)
  } catch (error) {
    console.warn(`  ⚠️  无法监听 ${path.relative(REPO_DIR, target)}：${error.message}`)
  }
}

console.log(`\n监听中：${WATCH_DIRS.map((d) => path.relative(REPO_DIR, d) || '.').join('、')}、README.md`)

// ------------------------------------------------------------ VitePress

const server = spawn(process.execPath, [VITEPRESS, 'dev', '.'], {
  cwd: SITE_DIR,
  stdio: 'inherit',
})

const shutdown = (signal) => {
  for (const watcher of watchers) watcher.close()
  clearTimeout(timer)
  if (!server.killed) server.kill(signal)
}
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

server.on('exit', (code) => {
  for (const watcher of watchers) watcher.close()
  clearTimeout(timer)
  process.exit(code ?? 0)
})
