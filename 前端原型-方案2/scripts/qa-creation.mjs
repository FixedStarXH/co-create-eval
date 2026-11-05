// Local integration check: uses the explicitly created, ignored QA participant.
import { spawn } from 'node:child_process'
import { readFile, mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const account = { code: process.env.QA_STUDY_CODE, credential: process.env.QA_CREDENTIAL }
if (!account.code || !account.credential) throw new Error('Set QA_STUDY_CODE and QA_CREDENTIAL for a fresh S1 demo participant.')
const stageWait = Number(process.env.QA_WAIT_SECONDS || 320)
if (!Number.isFinite(stageWait) || stageWait < 1 || stageWait > 600) throw new Error('QA_WAIT_SECONDS must be between 1 and 600.')
const profile = await mkdtemp(join(tmpdir(), 'creation-e2e-'))
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=0', '--user-data-dir=' + profile, 'http://127.0.0.1:4173/'], { windowsHide: true, stdio: 'ignore' })
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, id = 0
const pending = new Map(), checks = [], errors = []
const send = (method, params = {}) => new Promise((resolve, reject) => { const n = ++id; pending.set(n, { resolve, reject }); socket.send(JSON.stringify({ id: n, method, params })) })
const evaluate = async expression => { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value }
const record = (name, result) => { checks.push({ name, passed: Boolean(result) }); if (!result) throw new Error('Check failed: ' + name) }
const until = async (expression, seconds = 8) => { for (let i = 0; i < seconds * 5; i++) { if (await evaluate(expression)) return true; await wait(200) } return false }
const click = async text => { const ok = await evaluate(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.offsetParent!==null && !x.disabled && x.textContent.includes(${JSON.stringify(text)}));if(!b)return false;b.click();return true })()`); if (!ok) throw new Error('Button not found: ' + text); await wait(200) }
try {
  let port
  for (let i = 0; i < 80; i++) { try { port = Number((await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split(/\r?\n/)[0]); break } catch { await wait(100) } }
  if (!port) throw new Error('Chrome did not start')
  const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json())
  socket = new WebSocket(targets.find(x => x.type === 'page').webSocketDebuggerUrl)
  socket.addEventListener('message', e => { const m=JSON.parse(e.data); if(m.id && pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)} if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text) })
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})})
  await send('Page.enable'); await send('Runtime.enable'); await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false})
  record('入口页面加载', await until("Boolean(document.querySelector('#study-code'))"))
  await evaluate(`(() => {const a=document.querySelector('#study-code'),b=document.querySelector('#credential');a.value=${JSON.stringify(account.code)};a.dispatchEvent(new Event('input',{bubbles:true}));b.value=${JSON.stringify(account.credential)};b.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('.consent-line input').click()})()`)
  await click('同意并继续'); record('真实登录', await until("document.querySelector('.portal h1')?.textContent.includes('了解你的创作任务')"))
  await click('我已理解'); record('服务端开始构思', await until("Boolean(document.querySelector('#idea-0'))"))
  await evaluate("(() => {const x=document.querySelector('#idea-0');x.value='需要核验资料来源';x.dispatchEvent(new Event('input',{bubbles:true}))})()")
  await wait(2000); record('构思自动保存', await until("document.querySelector('.save-hint')?.textContent.includes('已保存')"))
  await send('Page.reload',{ignoreCache:true}); record('刷新恢复构思', await until("document.querySelector('#idea-0')?.value === '需要核验资料来源'"))
  await click('保存并提交构思'); record('初稿锁定等待', await until("document.querySelector('#idea-0')?.readOnly && document.querySelector('.notice-strip')?.textContent.includes('已提交')"))
  record('阶段到时进入工作台', await until("[...document.querySelectorAll('.app-shell')].some(x=>x.offsetParent!==null)", stageWait))
  record('真实草稿初始为空', await evaluate("[...document.querySelectorAll('.app-shell')].find(x=>x.offsetParent!==null)?.querySelector('.rich-editor')?.textContent.trim() === ''"))
  await evaluate("(() => {const x=[...document.querySelectorAll('.app-shell')].find(x=>x.offsetParent!==null).querySelector('.rich-editor');x.textContent='已保存的活动步骤';x.dispatchEvent(new Event('input',{bubbles:true}))})()")
  await wait(2000); record('作品自动保存', await until("[...document.querySelectorAll('.app-shell')].find(x=>x.offsetParent!==null)?.querySelector('.save-label')?.textContent.includes('已保存')"))
  await send('Page.reload',{ignoreCache:true}); record('刷新恢复作品草稿', await until("[...document.querySelectorAll('.app-shell')].find(x=>x.offsetParent!==null)?.querySelector('.rich-editor')?.textContent.includes('已保存的活动步骤')"))
  await click('提交与问卷'); record('提交预览', await until("document.querySelector('.final-preview')?.textContent.includes('已保存的活动步骤')"))
  await click('确认提交'); record('服务端锁定终稿', await until("document.querySelector('.success-strip')?.textContent.includes('作品已提交')"))
  record('终稿状态可恢复', await evaluate("fetch('/api/v1/participant/sessions').then(r=>r.json()).then(x=>x.data[0].state === 'SUBMITTED')"))
  record('浏览器无运行异常', errors.length === 0)
  console.log(JSON.stringify({checks,errors},null,2))
} catch(e) { console.error(e); console.error(JSON.stringify({checks,errors},null,2)); process.exitCode=1 } finally { if(socket)socket.close();chrome.kill() }
