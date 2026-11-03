import { spawn } from 'node:child_process'
import { readFile, writeFile, mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const profile = await mkdtemp(join(tmpdir(), 'creative-pages-'))
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=0', '--user-data-dir=' + profile, 'http://127.0.0.1:4173/'], { windowsHide: true, stdio: 'ignore' })
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, id = 0
const pending = new Map(), errors = [], checks = []
const send = (method, params = {}) => new Promise((resolve, reject) => { const n = ++id; pending.set(n, { resolve, reject }); socket.send(JSON.stringify({ id: n, method, params })) })
const evaluate = async expression => { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value }
const record = (name, ok) => checks.push({ name, passed: Boolean(ok) })
const click = async text => { const ok = await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.offsetParent !== null && x.textContent.trim().includes(${JSON.stringify(text)})); if (!b) return false; b.click(); return true })()`); if (!ok) throw new Error('Button not found: ' + text); await wait(100) }
const screenshot = async name => { const r = await send('Page.captureScreenshot', { format: 'png' }); await writeFile(join(root, name), Buffer.from(r.data, 'base64')) }
try {
  let port
  for (let i = 0; i < 80; i++) { try { port = Number((await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split(/\r?\n/)[0]); break } catch { await wait(100) } }
  if (!port) throw new Error('Chrome did not start')
  const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json())
  socket = new WebSocket(targets.find(x => x.type === 'page').webSocketDebuggerUrl)
  socket.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(m.error) : p.resolve(m.result) } if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text); if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('console error') })
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  await send('Page.enable'); await send('Runtime.enable'); await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false }); await send('Page.reload', { ignoreCache: true })
  for (let i = 0; i < 40; i++) { if (await evaluate("Boolean(document.querySelector('.portal'))")) break; await wait(200) }
  await screenshot('qa-pages-entry.png')
  await click('同意并继续'); record('参与编号必填', await evaluate("document.querySelector('.form-error')?.textContent.includes('编号')"))
  await evaluate("document.querySelector('#study-code').value='P001';document.querySelector('#study-code').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('.consent-line input').click()")
  await click('同意并继续'); record('进入任务说明', await evaluate("document.querySelector('.portal h1')?.textContent.includes('了解你的创作任务')"))
  await click('我已理解'); record('进入独立构思', await evaluate("document.querySelector('.portal h1')?.textContent.includes('先写下你的想法')"))
  await click('保存想法'); record('进入创作工作台', await evaluate("document.querySelector('.app-shell').offsetParent !== null")); await screenshot('qa-pages-workbench.png')
  await click('提出问题'); await evaluate("(() => { const x=document.querySelector('#chat-input-A');x.value='如何组织学生讨论？';x.dispatchEvent(new Event('input',{bubbles:true})) })()"); await click('发送'); record('AI 对话示例', await evaluate("document.querySelector('.chat-history')?.textContent.includes('示例回复')")); await click('收起对话')
  await click('改写后采纳'); await evaluate("(() => { const t=document.querySelector('#adopt-target-A');t.value='resource';t.dispatchEvent(new Event('change',{bubbles:true}));const x=document.querySelector('#adopt-text-A');x.value='补充学习资料卡';x.dispatchEvent(new Event('input',{bubbles:true})) })()"); await click('确认加入作品'); await click('资源'); record('建议可加入指定章节', await evaluate("document.querySelector('.app-shell .rich-editor')?.textContent.includes('补充学习资料卡')")); await click('活动流程')
  await evaluate("const ed=document.querySelector('.rich-editor');ed.innerHTML += '<p>界面测试标记</p>';ed.dispatchEvent(new Event('input',{bubbles:true}))")
  await click('提交与问卷'); record('提交页保留编辑内容', await evaluate("document.querySelector('.final-preview')?.textContent.includes('界面测试标记')"))
  await click('确认提交'); await click('提交反馈'); record('问卷缺答提示', await evaluate("document.querySelector('.form-error')?.textContent.includes('回答')"))
  await evaluate("document.querySelectorAll('.survey-question').forEach(q=>q.querySelector('input[value=\"4\"]').click())")
  await click('提交反馈'); record('场次完成页', await evaluate("document.querySelector('.portal h1')?.textContent.includes('第一场任务已完成')"))
  await click('查看本场报告'); record('报告待评分状态', await evaluate("document.querySelector('.pending-panel')?.textContent.includes('尚未完成')")); await screenshot('qa-pages-report.png')
  await click('返回场次'); await click('准备开始第二场'); record('第二场任务说明', await evaluate("document.querySelector('.task-main h2')?.textContent.includes('学习建议')"))
  await click('我已理解'); await click('保存想法'); record('独立场不显示 AI 建议', await evaluate("(() => { const active = [...document.querySelectorAll('.app-shell')].find(x => x.offsetParent !== null); return active?.textContent.includes('任务 B') && !active.querySelector('.adopt-button') })()"))
  await click('提交与问卷'); await click('确认提交'); record('独立场仅显示共同问卷题', await evaluate("document.querySelectorAll('.survey-question').length === 5"))
  await evaluate("document.querySelectorAll('.survey-question').forEach(q=>q.querySelector('input[value=\"4\"]').click())"); await click('提交反馈'); record('第二场报告', await evaluate("document.querySelector('.page-title-row .outlined-tag')?.textContent.includes('任务 B')")); await click('第 1 场'); record('两场报告可切换', await evaluate("document.querySelector('.report-sections')?.textContent.includes('界面测试标记')")); await click('第 2 场')
  await click('页面导航'); await click('工作人员登录'); await evaluate("document.querySelector('#staff-name').value='teacher';document.querySelector('#staff-name').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#staff-password').value='demo';document.querySelector('#staff-password').dispatchEvent(new Event('input',{bubbles:true}))")
  await click('进入工作区'); record('教师待评列表', await evaluate("document.querySelector('.portal h1')?.textContent.includes('待评作品')"))
  await click('开始评分'); record('匿名评分页面', await evaluate("document.querySelector('.portal h1')?.textContent.includes('匿名作品评分')")); await screenshot('qa-pages-rating.png')
  await click('提交评分'); record('教师评分必填', await evaluate("document.querySelector('.form-error')?.textContent.includes('三个维度')"))
  await evaluate("document.querySelectorAll('.rating-dimension').forEach(q=>q.querySelector('input[value=\"4\"]').click());for(const [id,v] of [['strength','目标清晰'],['improve','补充时间']]){const x=document.getElementById(id);x.value=v;x.dispatchEvent(new Event('input',{bubbles:true}))}")
  await click('提交评分'); record('评分提交状态', await evaluate("document.querySelector('.rating-actions button:last-child')?.textContent.includes('已提交')"))
  await click('页面导航'); await click('研究管理'); record('管理员概览', await evaluate("document.querySelector('.portal h1')?.textContent.includes('研究管理')")); await screenshot('qa-pages-admin.png')
  for (const name of ['任务配置','参与进度','数据导出']) { await click(name); record('管理页面：' + name, await evaluate(`document.querySelector('.portal main')?.textContent.includes(${JSON.stringify(name === '数据导出' ? '匿名数据导出' : name)})`)) }
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true }); await click('页面导航'); await click('进入与说明'); await wait(100); await screenshot('qa-pages-mobile.png')
  record('手机入口无横向溢出', await evaluate("document.documentElement.scrollWidth <= innerWidth"))
  for (const name of ['任务说明','初始构思','作品提交','体验问卷','场次间休息','个人报告','工作人员登录','待评作品','匿名评分','研究管理']) {
    await click('页面导航'); await click(name)
    record('手机页面：' + name, await evaluate("document.documentElement.scrollWidth <= innerWidth && document.querySelector('.portal').scrollWidth <= innerWidth"))
  }
  await click('页面导航'); await click('创作工作台'); record('手机工作台布局', await evaluate("document.documentElement.scrollWidth <= innerWidth")); await click('返回构思')
  record('浏览器运行错误', errors.length === 0)
  console.log(JSON.stringify({ checks, errors }, null, 2)); if (checks.some(x => !x.passed)) process.exitCode = 1
} catch (e) { console.error(e); process.exitCode = 1 } finally { if (socket) socket.close(); chrome.kill() }
