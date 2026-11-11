<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { PhArrowLeft, PhArrowRight, PhCheck, PhCheckCircle, PhClock, PhDownloadSimple, PhFileText, PhInfo, PhListChecks, PhLockKey, PhSignOut, PhSparkle, PhUsers } from '@phosphor-icons/vue'
import Workbench from './Workbench.vue'
import { participantApi, type Assignment, type Progress } from './participant-api'
import { useDraftSaver } from './draft-saver'
import './portal.css'

type Page = 'join' | 'task' | 'idea' | 'work' | 'submit' | 'survey' | 'break' | 'report' | 'staff' | 'teacher' | 'rating' | 'admin'
type Section = { label: string; title: string; html: string }
const page = ref<Page>('join')
const round = ref<1 | 2>(1)
const previewNav = ref(false)
const studyCode = ref('')
const credential = ref('')
const entryLoading = ref(false)
const phaseBusy = ref(false)
const assignment = ref<Assignment | null>(null)
const assignments = ref<Assignment[]>([])
const progress = ref<Progress | null>(null)
const currentSession = computed(() => assignments.value.find(item => item.round_no === round.value))
const liveWork = computed(() => Boolean(currentSession.value && progress.value?.id === currentSession.value.id && ['DEVELOPMENT', 'SUBMITTED'].includes(progress.value.state)))
const workRevision = ref(0)
const clockTick = ref(Date.now())
const clockOffset = ref(0)
const ideaRemaining = computed(() => progress.value?.ideation_deadline_at ? Math.max(0, Math.ceil((Date.parse(progress.value.ideation_deadline_at) - clockTick.value - clockOffset.value) / 1000)) : 300)
const ideaTimeLabel = computed(() => `${String(Math.floor(ideaRemaining.value / 60)).padStart(2, '0')}:${String(ideaRemaining.value % 60).padStart(2, '0')}`)
const ideaLocked = computed(() => Boolean(progress.value?.idea_submitted_at || (progress.value && progress.value.state !== 'IDEATION') || ideaRemaining.value <= 0))
let hydratingIdea = false
let pollTimer: number | undefined
let clockTimer: number | undefined
let polling = false
const csrfToken = ref('')
const previewEpoch = ref(0)
const consent = ref(false)
const staffRole = ref<'teacher' | 'admin'>('teacher')
const staffName = ref('')
const staffPassword = ref('')
const error = ref('')
const ideas = ref(['', '', ''])
const ideaSaver = useDraftSaver<string[]>(() => ideas.value, (revision, values) => participantApi.saveIdea(currentSession.value!.id, csrfToken.value, revision, values))
watch(ideas, () => { if (!hydratingIdea && progress.value?.state === 'IDEATION' && !ideaLocked.value && currentSession.value?.id === progress.value.id) ideaSaver.changed() }, { deep: true, flush: 'sync' })
const sections = ref<Section[]>([])
const reports = ref<Record<1 | 2, Section[]>>({ 1: [], 2: [] })
const reportRound = ref<1 | 2>(1)
const reportSections = computed(() => reports.value[reportRound.value])
const submitted = ref(false)
const survey = ref<number[]>([0, 0, 0, 0, 0, 0])
const scores = ref<number[]>([0, 0, 0])
const strengths = ref('')
const improvements = ref('')
const ratingSubmitted = ref(false)
const reviewFlag = ref(false)
const adminTab = ref<'overview' | 'tasks' | 'participants' | 'export'>('overview')
const selectedTask = ref<'A' | 'B'>('A')
const taskNames = ref({ A: '核验 AI 生成的学习资料', B: '评价 AI 生成的学习建议' })
const taskDescriptions = ref({ A: '学生经常使用生成式 AI 搜集学科知识，需要学会核验资料中的关键说法并根据证据修订。', B: '学生使用 AI 制作复习计划，需要结合个人学习条件判断并调整建议。' })
const taskName = computed({ get: () => taskNames.value[selectedTask.value], set: value => { taskNames.value[selectedTask.value] = value } })
const taskDescription = computed({ get: () => taskDescriptions.value[selectedTask.value], set: value => { taskDescriptions.value[selectedTask.value] = value } })
const notice = ref('')
const role = computed(() => page.value === 'staff' ? 'staff' : page.value === 'teacher' || page.value === 'rating' ? 'teacher' : page.value === 'admin' ? 'admin' : 'participant')
const flowSteps = ['说明', '任务', '构思', '完善', '报告']
const flowIndex = computed(() => ({ join: 0, task: 1, idea: 2, work: 3, submit: 3, survey: 3, break: 3, report: 4, staff: -1, teacher: -1, rating: -1, admin: -1 }[page.value]))
const pageOptions: { id: Page; group: string; label: string }[] = [
  { id: 'join', group: '参与者', label: '01 进入与说明' }, { id: 'task', group: '参与者', label: '02 任务说明' },
  { id: 'idea', group: '参与者', label: '03 初始构思' }, { id: 'work', group: '参与者', label: '04 创作工作台' },
  { id: 'submit', group: '参与者', label: '05 作品提交' }, { id: 'survey', group: '参与者', label: '06 体验问卷' },
  { id: 'break', group: '参与者', label: '07 场次间休息' }, { id: 'report', group: '参与者', label: '08 个人报告' },
  { id: 'staff', group: '评分教师', label: '09 工作人员登录' }, { id: 'teacher', group: '评分教师', label: '10 待评作品' }, { id: 'rating', group: '评分教师', label: '11 匿名评分' },
  { id: 'admin', group: '管理员', label: '11 研究管理' },
]
const questions = ['我能够清楚表达自己的设计想法。', '我感觉自己能够控制最终作品。', '这个创作界面容易使用。', '我能够判断活动方案是否可实施。', '我认为这个任务值得投入时间。', 'AI 的建议帮助我探索了新的设计方向。']
const taskForRound = (n: number): 'A' | 'B' => n === 1 ? (assignment.value?.task_code ?? 'A') : (assignment.value?.task_code === 'B' ? 'A' : 'B')
const activeTask = computed(() => taskForRound(round.value))
const aiEnabled = computed(() => round.value === 1 ? assignment.value?.condition !== 'INDEPENDENT' : assignment.value?.condition === 'INDEPENDENT')
const activeQuestions = computed(() => aiEnabled.value ? questions : questions.slice(0, 5))
const dimensions = [
  { name: '新颖性', hint: '学生任务或活动组织是否具有有意义的新组合。' },
  { name: '教育适切性', hint: '目标、学生参与、学习产出与评价是否相互对应。' },
  { name: '可实施性', hint: '步骤、时间与资源是否清晰，能否在普通学校条件下实施。' },
]
function go(next: Page) {
  const navigate = () => { page.value = next; error.value = ''; previewNav.value = false; nextTick(() => document.querySelector('.portal')?.scrollTo(0, 0)) }
  if (page.value === 'idea' && assignment.value && ideaSaver.status.value !== 'saved') { void ideaSaver.flush().then(ok => { if (ok) navigate(); else error.value = ideaSaver.error.value }); return }
  navigate()
}
async function loadAssignment(restoreRound = false) { const sessions = await participantApi.sessions(); const first = sessions.find(item => item.round_no === 1); if (!first?.task_code || !first.condition) throw new Error('未找到已分配的任务，请联系管理员。'); assignments.value = sessions; assignment.value = first; if (restoreRound) { const second = sessions.find(item => item.round_no === 2); round.value = second && second.state !== 'CREATED' ? 2 : 1 } }
function clearPreviewState() { previewEpoch.value += 1; assignment.value = null; assignments.value = []; progress.value = null; round.value = 1; hydratingIdea = true; ideas.value = ['', '', '']; hydratingIdea = false; ideaSaver.reset(0); sections.value = []; reports.value = { 1: [], 2: [] }; reportRound.value = 1; survey.value = [0, 0, 0, 0, 0, 0]; submitted.value = false }
function applyProgress(value: Progress, restore = false) {
  progress.value = value; clockOffset.value = Date.parse(value.server_time) - Date.now(); clockTick.value = Date.now()
  if (restore && value.idea) { hydratingIdea = true; ideas.value = value.idea.values; hydratingIdea = false; ideaSaver.reset(value.idea.revision) }
}
function sectionsFromDraft(value: Progress): Section[] { const labels = [['goal','目标','1. 活动目标'], ['student','学生任务','2. 学生任务'], ['flow','活动流程','3. 活动流程与时间分配'], ['resource','资源','4. 材料与工具'], ['assessment','评价','5. 评价方式']] as const; return labels.map(([id, label, title]) => ({ label, title, html: value.draft?.sections[id] ?? '' })) }
async function restoreSession() {
  if (!currentSession.value) return
  const value = await participantApi.progress(currentSession.value.id); applyProgress(value, true)
  if (value.state === 'IDEATION') go('idea')
  else if (value.state === 'DEVELOPMENT') go('work')
  else if (value.state === 'SUBMITTED') { sections.value = sectionsFromDraft(value); reports.value[round.value] = sections.value.map(section => ({ ...section })); submitted.value = true; go('survey') }
  else if (value.state === 'EXPIRED') { go('task'); error.value = '本场任务已结束且没有已保存的作品。' }
  else go('task')
}
async function beginIdeation() {
  if (!assignment.value || !currentSession.value) { go('idea'); return }
  if (phaseBusy.value) return
  phaseBusy.value = true
  try { const value = await participantApi.start(currentSession.value.id, csrfToken.value); applyProgress(value, true); if (value.state === 'IDEATION') go('idea'); else if (value.state === 'DEVELOPMENT') go('work'); else if (value.state === 'SUBMITTED') { sections.value = sectionsFromDraft(value); submitted.value = true; go('survey') } else error.value = '本场任务已结束。' }
  catch (e) { error.value = e instanceof Error ? e.message : '无法开始任务' }
  finally { phaseBusy.value = false }
}
async function finishIdea() {
  if (!assignment.value || !currentSession.value || !progress.value) { go('work'); return }
  if (progress.value.state === 'DEVELOPMENT') { go('work'); return }
  if (progress.value.idea_submitted_at) return
  if (phaseBusy.value) return
  phaseBusy.value = true
  try {
  if (!(await ideaSaver.flush())) { error.value = ideaSaver.error.value; return }
  const value = await participantApi.submitIdea(currentSession.value.id, csrfToken.value, ideaSaver.revision.value); applyProgress(value); if (value.state === 'DEVELOPMENT') go('work')
  }
  catch (e) { error.value = e instanceof Error ? e.message : '提交失败' }
  finally { phaseBusy.value = false }
}
function continueAfterUnsavedIdea() { if (window.confirm('未保存的构思不会写入初稿。请先复制需要保留的内容，确定继续吗？')) { ideaSaver.reset(ideaSaver.revision.value); go('work') } }
async function pollProgress() {
  if (!currentSession.value || !assignment.value || !['idea', 'work', 'submit'].includes(page.value) || polling) return
  polling = true
  try { const value = await participantApi.progress(currentSession.value.id); applyProgress(value); if (page.value === 'idea' && value.state === 'DEVELOPMENT' && ideaSaver.status.value === 'saved') go('work') }
  catch { /* Keep locally edited content and retry on the next poll. */ }
  finally { polling = false }
}
async function enter() {
  if (!studyCode.value.trim()) { error.value = '请输入参与编号'; return }
  if (!credential.value) { error.value = '请输入访问凭证'; return }
  if (!consent.value) { error.value = '请阅读并确认同意后继续'; return }
  entryLoading.value = true; error.value = ''
  try { const identity = await participantApi.login(studyCode.value, credential.value); clearPreviewState(); csrfToken.value = identity.csrf_token; await participantApi.consent(identity.csrf_token); await loadAssignment(true); studyCode.value = identity.study_code; credential.value = ''; await restoreSession() }
  catch (e) { error.value = e instanceof Error ? e.message : '登录失败，请稍后再试。' }
  finally { entryLoading.value = false }
}
function warnUnsaved(event: BeforeUnloadEvent) { if (page.value === 'idea' && assignment.value && ideaSaver.status.value !== 'saved') { event.preventDefault(); event.returnValue = '' } }
onMounted(async () => { window.addEventListener('beforeunload', warnUnsaved); clockTimer = window.setInterval(() => { clockTick.value = Date.now() }, 1000); pollTimer = window.setInterval(() => { void pollProgress() }, 3000); try { const identity = await participantApi.me(); if (identity.consented) { studyCode.value = identity.study_code; csrfToken.value = identity.csrf_token; await loadAssignment(true); await restoreSession() } } catch { /* No valid saved session; show entry. */ } })
onBeforeUnmount(() => { window.removeEventListener('beforeunload', warnUnsaved); if (clockTimer) clearInterval(clockTimer); if (pollTimer) clearInterval(pollTimer) })
async function participantLogout() { if (page.value === 'idea' && !(await ideaSaver.flush())) { error.value = ideaSaver.error.value; return }; try { await participantApi.logout(csrfToken.value); clearPreviewState(); csrfToken.value = ''; studyCode.value = ''; credential.value = ''; consent.value = false; go('join') } catch (e) { flash(e instanceof Error ? e.message : '退出失败，请稍后再试。') } }
function staffLogin() { if (!staffName.value.trim() || !staffPassword.value) { error.value = '请输入账号和密码'; return }; go(staffRole.value) }
function continueFromWorkbench(value: Section[], revision: number) { sections.value = value; workRevision.value = revision; go('submit') }
function submitSurvey() { if (survey.value.slice(0, activeQuestions.value.length).some(v => !v)) { error.value = '请先回答所有题目'; return }; reportRound.value = round.value; go(round.value === 1 ? 'break' : 'report') }
async function startSecond() { if (assignment.value) { try { await loadAssignment(); if (!assignments.value.find(item => item.round_no === 2)?.task_code) throw new Error('请先完成第一场作品提交。') } catch (e) { flash(e instanceof Error ? e.message : '无法进入第二场'); return } }; round.value = 2; progress.value = null; hydratingIdea = true; ideas.value = ['', '', '']; hydratingIdea = false; ideaSaver.reset(0); survey.value = [0, 0, 0, 0, 0, 0]; sections.value = []; submitted.value = false; if (assignment.value) await restoreSession(); else go('task') }
async function submitWork() { if (phaseBusy.value) return; phaseBusy.value = true; try { if (liveWork.value && currentSession.value) { await participantApi.submit(currentSession.value.id, csrfToken.value, workRevision.value); const saved = await participantApi.progress(currentSession.value.id); applyProgress(saved); sections.value = sectionsFromDraft(saved); await loadAssignment() }; reports.value[round.value] = sections.value.map(section => ({ ...section })); submitted.value = true; go('survey') } catch (e) { error.value = e instanceof Error ? e.message : '提交失败' } finally { phaseBusy.value = false } }
function submitRating() { if (scores.value.some(v => !v) || !strengths.value.trim() || !improvements.value.trim()) { error.value = '请完成三个维度的评分，并填写优点和改进建议。'; return }; ratingSubmitted.value = true; error.value = ''; notice.value = '评分已在本次预览中提交'; }
function flash(message: string) { notice.value = message; window.setTimeout(() => { notice.value = '' }, 3000) }
function printReport() { window.print() }
</script>

<template>
  <Workbench :key="'A-' + previewEpoch" v-show="page === 'work' && activeTask === 'A'" :active="page === 'work' && activeTask === 'A'" :ai-enabled="aiEnabled" :session-id="liveWork ? currentSession?.id : undefined" :csrf="csrfToken" :initial-draft="progress?.draft" :deadline="progress?.development_deadline_at" :server-time="progress?.server_time" task="A" @back="go('idea')" @continue="continueFromWorkbench" />
  <Workbench :key="'B-' + previewEpoch" v-show="page === 'work' && activeTask === 'B'" :active="page === 'work' && activeTask === 'B'" :ai-enabled="aiEnabled" :session-id="liveWork ? currentSession?.id : undefined" :csrf="csrfToken" :initial-draft="progress?.draft" :deadline="progress?.development_deadline_at" :server-time="progress?.server_time" task="B" @back="go('idea')" @continue="continueFromWorkbench" />
  <div v-if="page !== 'work'" class="portal">
    <header class="portal-header">
      <button class="portal-brand" type="button" @click="go('join')"><span class="portal-logo"><PhFileText :size="21" weight="fill" /></span><span>人机协同创造力评测系统</span></button>
      <span class="portal-divider"></span><span class="portal-context">{{ role === 'participant' ? '参与者工作区' : role === 'staff' ? '工作人员入口' : role === 'teacher' ? '教师评分工作区' : '研究管理工作区' }}</span>
      <div class="portal-header-right">
        <span class="demo-label">后续流程预览</span>
        <div class="preview-menu-wrap"><button class="quiet-button" type="button" :aria-expanded="previewNav" @click="previewNav = !previewNav">页面导航 <span>⌄</span></button>
          <div v-if="previewNav" class="preview-menu"><template v-for="group in ['参与者', '评分教师', '管理员']" :key="group"><div class="menu-caption">{{ group }}</div><button v-for="item in pageOptions.filter(p => p.group === group)" :key="item.id" type="button" @click="go(item.id)">{{ item.label }}</button></template></div>
        </div>
        <button v-if="role === 'participant' && assignment" class="quiet-button" type="button" @click="participantLogout"><PhSignOut :size="17" /> 退出登录</button>
        <button v-else-if="role === 'teacher' || role === 'admin'" class="quiet-button" type="button" @click="go('staff')"><PhSignOut :size="17" /> 退出</button>
      </div>
    </header>

    <nav v-if="role === 'participant'" class="flow-nav" aria-label="任务进度"><div class="flow-nav-inner"><div v-for="(step, index) in flowSteps" :key="step" class="flow-step" :class="{ current: flowIndex === index, complete: flowIndex > index }"><span class="step-number"><PhCheck v-if="flowIndex > index" :size="13" weight="bold" /><template v-else>{{ String(index + 1).padStart(2, '0') }}</template></span><span>{{ step }}</span><span v-if="index < 4" class="step-line"></span></div></div></nav>
    <div v-else-if="role !== 'staff'" class="role-nav"><div class="role-nav-inner"><span class="role-active">{{ role === 'teacher' ? '作品评分' : '研究管理' }}</span><span>{{ role === 'teacher' ? '依据统一量规独立评价匿名作品' : '管理任务、参与进度与数据' }}</span></div></div>

    <main v-if="page === 'join'" class="page-container narrow-page">
      <div class="eyebrow"><span class="eyebrow-line"></span> 开始一项创作任务 <span class="eyebrow-index">01 / 05</span></div>
      <div class="page-title-block"><h1>欢迎参与创作</h1><p>在开始之前，请先了解任务安排和数据使用方式。</p></div>
      <section class="surface intro-surface"><div class="surface-heading"><div><span class="section-kicker">PARTICIPATION</span><h2>参与说明</h2></div><span class="small-tag"><PhClock :size="15" /> 约 65–75 分钟</span></div><p>你将完成两项教育创意任务。每项任务先独立构思，再完善作品。系统会记录作品版本与操作过程，用于生成本次任务的反馈。</p><div class="info-grid"><div><strong>你需要完成</strong><span>阅读任务、设计课堂活动，并填写简短体验问卷。</span></div><div><strong>你的数据</strong><span>使用参与编号记录作品；评分教师只查看匿名终稿。</span></div><div><strong>参与方式</strong><span>参与是自愿的，你可以在过程中选择退出。</span></div></div><details class="inline-details"><summary>查看数据使用与退出说明</summary><p>作品、版本与协作记录将用于本次评测。实际使用前应提供完整的知情说明及联系渠道。</p></details></section>
      <section class="surface form-surface"><div class="form-title"><span class="section-number">01</span><div><h2>输入参与编号</h2><p>请输入组织者提供的编号，用于识别你的任务进度。</p></div></div><label class="field-label" for="study-code">参与编号</label><input id="study-code" v-model="studyCode" class="field-input" placeholder="例如：DEMO001" /><label class="field-label" for="credential">访问凭证</label><input id="credential" v-model="credential" class="field-input" type="password" autocomplete="current-password" placeholder="输入组织者提供的访问凭证" /><label class="consent-line"><input v-model="consent" type="checkbox" /> <span>我已阅读参与说明，并同意继续参加。</span></label><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="form-footer"><span><PhLockKey :size="16" /> 你的编号仅用于本次任务</span><button class="action-primary" type="button" :disabled="entryLoading" @click="enter">{{ entryLoading ? "正在验证…" : "同意并继续" }} <PhArrowRight :size="16" /></button></div></section>
      <p class="bottom-note">评分教师或管理员？<button class="inline-link" type="button" @click="go('staff')">进入工作人员入口 →</button></p>
    </main>

    <main v-else-if="page === 'staff'" class="page-container narrow-page staff-page"><div class="eyebrow"><span class="eyebrow-line"></span> 工作人员入口 <span class="eyebrow-index">WORKSPACE</span></div><div class="page-title-block"><h1>登录工作区</h1><p>选择你的角色，进入对应的评分或管理工作区。</p></div><section class="surface form-surface"><div class="staff-roles"><button type="button" :class="{ active: staffRole === 'teacher' }" @click="staffRole = 'teacher'"><strong>评分教师</strong><span>查看匿名作品并独立评分</span></button><button type="button" :class="{ active: staffRole === 'admin' }" @click="staffRole = 'admin'"><strong>研究管理员</strong><span>配置任务并查看数据进度</span></button></div><label class="field-label" for="staff-name">账号</label><input id="staff-name" v-model="staffName" class="field-input" autocomplete="username" placeholder="输入工作人员账号" /><label class="field-label" for="staff-password">密码</label><input id="staff-password" v-model="staffPassword" class="field-input" type="password" autocomplete="current-password" placeholder="输入密码" @keyup.enter="staffLogin" /><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="form-footer staff-footer"><span><PhLockKey :size="16" /> 预览状态：输入任意账号和密码</span><button class="action-primary" type="button" @click="staffLogin">进入工作区 <PhArrowRight :size="16" /></button></div></section><button class="inline-link" type="button" @click="go('join')"><PhArrowLeft :size="15" /> 返回参与者入口</button></main>

    <main v-else-if="page === 'task'" class="page-container">
      <div class="eyebrow"><span class="eyebrow-line"></span> 任务说明 <span class="eyebrow-index">02 / 05</span></div><div class="page-title-block page-title-row"><div><h1>了解你的创作任务</h1><p>阅读任务情境与要求，准备好后再开始计时。</p></div><span class="outlined-tag">{{ round === 1 ? "第一场" : "第二场" }} · 任务 {{ activeTask }}</span></div>
      <div v-if="assignment" class="notice-strip"><PhInfo :size="19" /><span>登录、计时、作品保存与 AI 对话已连接服务；问卷和评分仍为界面预览。</span></div><div class="task-layout"><section class="surface task-main"><div class="surface-heading"><div><span class="section-kicker">THE BRIEF</span><h2>{{ activeTask === "A" ? "核验 AI 生成的学习资料" : "评价 AI 生成的学习建议" }}</h2></div><span class="task-id">TASK {{ activeTask }}</span></div><p class="lead-copy">为高一学生设计一节 40 分钟的 AI 素养课堂活动。</p><h3>情境</h3><p>{{ activeTask === "A" ? "学生经常使用生成式 AI 搜集知识。有时 AI 给出的解释看起来完整，却可能混入错误事实或缺少来源。学校希望帮助学生形成核验 AI 生成资料的习惯。" : "学生使用生成式 AI 制作复习计划，但计划可能忽略个人薄弱环节、时间安排或实际条件。学校希望帮助学生判断和调整 AI 生成的学习建议。" }}</p><h3>你的任务</h3><p>{{ activeTask === "A" ? "设计一项让学生接触可能存在问题的 AI 资料、提出核验办法，并根据核验结果修订资料的课堂活动。" : "设计一项让学生判断 AI 学习建议是否适合具体情况，并根据学习需求改进建议的课堂活动。" }}</p><div class="rule-box"><strong>设计时请注意</strong><ul><li>让学生提出自己的判断，而不只是听教师讲解。</li><li>活动方法应适合普通学校的资源条件。</li><li>教师应能看到学生的判断依据和修订结果。</li></ul></div></section><aside class="task-aside"><section class="surface aside-card"><span class="section-kicker">YOUR OUTPUT</span><h2>你需要提交</h2><ol class="output-list"><li><span>01</span>活动目标</li><li><span>02</span>学生任务</li><li><span>03</span>活动流程与时间</li><li><span>04</span>材料与工具</li><li><span>05</span>评价方式</li></ol></section><section class="surface aside-card"><span class="section-kicker">TIME PLAN</span><h2>任务安排</h2><div class="time-row"><span>独立构思</span><strong>05 <small>分钟</small></strong></div><div class="time-row"><span>完善作品</span><strong>20 <small>分钟</small></strong></div><p class="muted-note">点击开始后进入构思阶段，请尽量一次完成。</p></section></aside></div><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="page-actions"><button class="action-secondary" type="button" @click="go('join')"><PhArrowLeft :size="16" /> 返回</button><button class="action-primary" type="button" :disabled="phaseBusy" @click="beginIdeation">我已理解，开始构思 <PhArrowRight :size="16" /></button></div>
    </main>

    <main v-else-if="page === 'idea'" class="page-container medium-page"><div class="eyebrow"><span class="eyebrow-line"></span> 独立构思 <span class="eyebrow-index">03 / 05</span></div><div class="page-title-block page-title-row"><div><h1>先写下你的想法</h1><p>不用追求完整，记录你最初的判断与设计方向。</p></div><div class="time-pill"><PhClock :size="18" /><span>剩余时间</span><strong>{{ assignment ? ideaTimeLabel : "05:00" }}</strong></div></div><div class="notice-strip"><PhInfo :size="19" /><span>{{ progress?.idea_submitted_at && progress.state === "IDEATION" ? "初始构思已提交，请等待本阶段结束。" : progress?.state === "DEVELOPMENT" ? "构思阶段已结束，可以继续完善作品。" : "这一阶段请先独立思考。后续可以继续完善这些想法。" }}</span></div><section class="surface idea-card"><div v-for="(question, index) in ['我想解决的关键问题是什么？', '我准备让学生做什么？', '我怎样判断学习活动是否有效？']" :key="question" class="idea-field"><label :for="'idea-' + index"><span>{{ String(index + 1).padStart(2, '0') }}</span>{{ question }}</label><p>{{ ['例如：学生如何判断 AI 资料是否可信。', '写下你想到的核心活动或学生任务。', '可以考虑学生的可见成果和教师的观察方式。'][index] }}</p><textarea :id="'idea-' + index" v-model="ideas[index]" :readonly="!!assignment && ideaLocked" rows="3" placeholder="在这里记录你的初步想法…"></textarea></div></section><p v-if="error || ideaSaver.error.value" class="form-error" role="alert">{{ error || ideaSaver.error.value }}。如果阶段已结束，请先复制未保存的内容。</p><div class="page-actions"><button class="action-secondary" type="button" @click="go('task')"><PhArrowLeft :size="16" /> 返回任务</button><div class="action-group"><span class="save-hint">{{ !assignment ? "想法仅在当前预览中保留" : ideaSaver.status.value === "saving" ? "保存中…" : ideaSaver.status.value === "unsaved" ? "待保存" : ideaSaver.status.value === "error" ? "保存失败" : "已保存" }}</span><button v-if="assignment && ideaSaver.status.value === 'error' && !ideaLocked" class="action-secondary" type="button" @click="ideaSaver.flush()">重试保存</button><button v-if="assignment && progress?.state === 'DEVELOPMENT' && ideaSaver.status.value === 'error'" class="action-secondary" type="button" @click="continueAfterUnsavedIdea">已复制，继续</button><button class="action-primary" type="button" :disabled="phaseBusy || (!!assignment && !!progress?.idea_submitted_at && progress.state === 'IDEATION')" @click="finishIdea">{{ progress?.state === "DEVELOPMENT" ? "继续完善作品" : progress?.idea_submitted_at ? "等待阶段结束" : "保存并提交构思" }} <PhArrowRight :size="16" /></button></div></div></main>

    <main v-else-if="page === 'submit'" class="page-container medium-page"><div class="eyebrow"><span class="eyebrow-line"></span> 提交作品 <span class="eyebrow-index">04 / 05</span></div><div class="page-title-block"><h1>检查并提交作品</h1><p>提交前请确认五个部分。正式系统中，提交后作品将被锁定。</p></div><div class="notice-strip"><PhInfo :size="19" /><span>{{ liveWork ? "确认后作品将保存到服务器并锁定，提交后不能继续修改。" : "当前为界面预览，展示的是本次编辑内容；提交不会发送到服务器。" }}</span></div><section class="surface final-preview"><div class="surface-heading"><div><span class="section-kicker">FINAL REVIEW</span><h2>课堂活动方案</h2></div><span class="outlined-tag">任务 {{ activeTask }}</span></div><template v-if="sections.length"><section v-for="section in sections" :key="section.label" class="final-section"><h3>{{ section.title }}</h3><div class="preview-html" v-html="section.html"></div></section></template><div v-else class="empty-state">从创作工作台进入后，这里会展示五个章节的内容。<button class="inline-link" type="button" @click="go('work')">前往创作工作台</button></div></section><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="page-actions"><button class="action-secondary" type="button" @click="go('work')"><PhArrowLeft :size="16" /> 返回修改</button><button class="action-primary" type="button" :disabled="phaseBusy" @click="submitWork">确认提交，填写问卷 <PhArrowRight :size="16" /></button></div></main>

    <main v-else-if="page === 'survey'" class="page-container medium-page"><div class="eyebrow"><span class="eyebrow-line"></span> 体验反馈 <span class="eyebrow-index">04 / 05</span></div><div class="page-title-block"><h1>分享你的使用体验</h1><p>请根据刚才的任务选择符合你感受的选项。没有对错之分。</p></div><div v-if="submitted" class="success-strip"><PhCheckCircle :size="20" /> {{ progress?.state === "SUBMITTED" ? "作品已提交；问卷目前仅供界面预览。" : "作品已进入提交预览，接下来请完成问卷。" }}</div><section class="surface survey-card"><div class="survey-scale"><span>1　非常不同意</span><span>5　非常同意</span></div><div v-for="(question, index) in activeQuestions" :key="question" class="survey-question"><div><span class="question-number">{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ question }}</strong><small v-if="index === 5">AI 协同场次</small></div><fieldset :aria-label="question"><label v-for="n in 5" :key="n" :class="{ selected: survey[index] === n }"><input v-model="survey[index]" type="radio" :name="'survey-' + index" :value="n" />{{ n }}</label></fieldset></div></section><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="page-actions"><button class="action-secondary" type="button" @click="go('submit')"><PhArrowLeft :size="16" /> 返回</button><button class="action-primary" type="button" @click="submitSurvey">提交反馈 <PhArrowRight :size="16" /></button></div></main>

    <main v-else-if="page === 'break'" class="page-container narrow-page"><section class="surface break-card"><span class="completion-icon"><PhCheckCircle :size="34" /></span><span class="section-kicker">SESSION COMPLETE</span><h1>第一场任务已完成</h1><p>你已经完成了第一场创作和体验反馈。可以休息片刻，再开始下一场任务。</p><div class="break-summary"><div><span>第一场</span><strong>任务 {{ taskForRound(1) }}</strong><small>已完成</small></div><span class="summary-line"></span><div><span>第二场</span><strong>任务 {{ taskForRound(2) }}</strong><small>待开始</small></div></div><button class="action-primary" type="button" @click="go('report')">查看本场报告 <PhArrowRight :size="16" /></button><button class="inline-link" type="button" @click="startSecond">准备开始第二场</button></section></main>

    <main v-else-if="page === 'report'" class="page-container"><div class="eyebrow"><span class="eyebrow-line"></span> 个人报告 <span class="eyebrow-index">05 / 05</span></div><div class="page-title-block page-title-row"><div><h1>本次创作报告</h1><p>查看作品、评价来源与创作过程，了解这次任务的表现。</p></div><span class="outlined-tag">任务 {{ taskForRound(reportRound) }} · 报告预览</span></div><div class="report-switch" aria-label="选择场次"><button v-for="n in ([1, 2] as const)" :key="n" type="button" :disabled="!reports[n].length" :class="{ active: reportRound === n }" @click="reportRound = n">第 {{ n }} 场 · 任务 {{ taskForRound(n) }}</button></div><div class="report-layout"><div><section class="surface report-card"><div class="surface-heading"><div><span class="section-kicker">TEACHER REVIEW</span><h2>教师评价</h2></div><span class="status-tag pending">等待评分</span></div><div class="pending-panel"><PhClock :size="24" /><div><strong>教师评分尚未完成</strong><p>两位教师完成独立评分后，将在这里展示三个维度的评价和评语。</p></div></div><div class="dimension-placeholder"><div v-for="d in dimensions" :key="d.name"><span>{{ d.name }}</span><div class="empty-bar"></div><small>待评分</small></div></div></section><section class="surface report-card"><div class="surface-heading"><div><span class="section-kicker">AI ASSISTANCE</span><h2>AI 辅助评价</h2></div><span class="status-tag neutral">待生成</span></div><p class="muted-copy">提交后的辅助评价将在这里显示评分依据和改进建议，与教师评分分别呈现。</p></section><section class="surface report-card"><div class="surface-heading"><div><span class="section-kicker">YOUR WORK</span><h2>作品内容</h2></div></div><div v-if="reportSections.length" class="report-sections"><div v-for="section in reportSections" :key="section.label"><strong>{{ section.title }}</strong><div class="preview-html" v-html="section.html"></div></div></div><p v-else class="muted-copy">完成创作后，这里将展示你的最终作品。</p></section></div><aside><section class="surface report-card"><span class="section-kicker">PROCESS</span><h2>创作过程</h2><div class="timeline"><div><span></span><strong>独立构思</strong><small>记录最初的活动想法</small></div><div><span></span><strong>完善作品</strong><small>编辑五个作品章节</small></div><div><span></span><strong>提交与反馈</strong><small>提交终稿并完成问卷</small></div><div><span></span><strong>等待评价</strong><small>教师评分完成后更新</small></div></div></section><p class="report-footnote">本报告反映本次任务中的表现，评价来源和生成时间将在正式系统中标注。</p></aside></div><div class="page-actions"><button class="action-secondary" type="button" @click="go('break')"><PhArrowLeft :size="16" /> 返回场次</button><button class="action-secondary" type="button" @click="printReport"><PhDownloadSimple :size="16" /> 打印报告</button></div></main>

    <main v-else-if="page === 'teacher'" class="page-container"><div class="eyebrow"><span class="eyebrow-line"></span> 教师工作台 <span class="eyebrow-index">REVIEW</span></div><div class="page-title-block page-title-row"><div><h1>待评作品</h1><p>请依据量规独立评分。作品已匿名处理，评分提交后将锁定。</p></div><span class="outlined-tag">评分教师 · 演示</span></div><div class="summary-grid three"><div class="summary-card"><span>分配作品</span><strong>03</strong><small>当前批次</small></div><div class="summary-card"><span>待完成</span><strong>{{ ratingSubmitted ? '02' : '03' }}</strong><small>需要独立评分</small></div><div class="summary-card"><span>已提交</span><strong>{{ ratingSubmitted ? '01' : '00' }}</strong><small>评分已锁定</small></div></div><section class="surface table-surface"><div class="table-title"><div><h2>作品列表</h2><p>点击作品编号查看终稿和评分量规。</p></div><span class="muted-copy">共 3 份</span></div><div class="table-scroll"><table><thead><tr><th>匿名作品编号</th><th>任务</th><th>任务版本</th><th>评分状态</th><th></th></tr></thead><tbody><tr v-for="(work, index) in ['W-8F32', 'W-4C17', 'W-9B06']" :key="work"><td><strong>{{ work }}</strong></td><td>{{ index === 1 ? '评价 AI 生成的学习建议' : '核验 AI 生成的学习资料' }}</td><td>V1.0</td><td><span class="status-tag" :class="ratingSubmitted && index === 0 ? 'success' : 'pending'">{{ ratingSubmitted && index === 0 ? '已提交' : '待评分' }}</span></td><td><button class="table-link" type="button" @click="go('rating')">{{ ratingSubmitted && index === 0 ? '查看评分' : '开始评分' }} →</button></td></tr></tbody></table></div></section><p class="bottom-note">预览中三个条目共用同一份示例作品，正式系统将按分配结果显示。</p></main>

    <main v-else-if="page === 'rating'" class="page-container"><div class="breadcrumb"><button type="button" @click="go('teacher')">作品列表</button><span>/</span><strong>W-8F32</strong></div><div class="page-title-block page-title-row"><div><h1>匿名作品评分</h1><p>任务 A · 核验 AI 生成的学习资料　/　量规 V1.0</p></div><span class="status-tag" :class="ratingSubmitted ? 'success' : 'pending'">{{ ratingSubmitted ? '已提交' : '待评分' }}</span></div><div class="rating-layout"><section class="surface review-work"><div class="surface-heading"><div><span class="section-kicker">ANONYMOUS WORK</span><h2>课堂活动方案</h2></div><span class="outlined-tag">W-8F32</span></div><div class="sample-work"><h3>1. 活动目标</h3><p>学生能够指出 AI 生成资料中需要核验的说法，并运用可靠来源说明判断依据。</p><h3>2. 学生任务</h3><p>学生分组阅读资料，标记可疑内容，查找证据并提交核验与修订卡。</p><h3>3. 活动流程与时间</h3><p>引入与个人判断（5 分钟）；小组核验与修订（20 分钟）；全班交流（10 分钟）；反思与迁移（5 分钟）。</p><h3>4. 材料与工具</h3><p>AI 生成资料、核验任务单、公开信息来源与投影设备。</p><h3>5. 评价方式</h3><p>根据核验依据、修订结果和个人反思进行评价。</p></div></section><section class="surface rating-card"><span class="section-kicker">ASSESSMENT RUBRIC</span><h2>评分量规</h2><p class="muted-copy">每项独立给出 1–5 分，请结合具体作品判断。</p><div v-for="(d, index) in dimensions" :key="d.name" class="rating-dimension"><strong>{{ d.name }}</strong><p>{{ d.hint }}</p><fieldset :aria-label="d.name"><label v-for="n in 5" :key="n" :class="{ selected: scores[index] === n, disabled: ratingSubmitted }"><input v-model="scores[index]" :disabled="ratingSubmitted" type="radio" :name="'score-' + index" :value="n" />{{ n }}</label></fieldset></div><label class="field-label" for="strength">作品优点</label><textarea id="strength" v-model="strengths" :disabled="ratingSubmitted" rows="3" placeholder="写下一项具体优点"></textarea><label class="field-label" for="improve">改进建议</label><textarea id="improve" v-model="improvements" :disabled="ratingSubmitted" rows="3" placeholder="写下一项具体建议"></textarea><p v-if="error" class="form-error" role="alert">{{ error }}</p><div v-if="reviewFlag" class="notice-strip compact">已标记为待复核（演示状态）。</div><div class="rating-actions"><button class="action-secondary" type="button" :disabled="ratingSubmitted" @click="reviewFlag = true">标记待复核</button><button class="action-primary" type="button" :disabled="ratingSubmitted" @click="submitRating">{{ ratingSubmitted ? '评分已提交' : '提交评分' }}</button></div></section></div></main>

    <main v-else-if="page === 'admin'" class="page-container"><div class="eyebrow"><span class="eyebrow-line"></span> 管理工作台 <span class="eyebrow-index">OVERVIEW</span></div><div class="page-title-block page-title-row"><div><h1>研究管理</h1><p>查看任务运行、参与进度与数据完整情况。</p></div><span class="outlined-tag">当前批次 · 演示数据</span></div><nav class="admin-tabs" aria-label="管理功能"><button v-for="tab in ([['overview','运行概览'],['tasks','任务配置'],['participants','参与进度'],['export','数据导出']] as const)" :key="tab[0]" type="button" :class="{ active: adminTab === tab[0] }" @click="adminTab = tab[0]">{{ tab[1] }}</button></nav>
      <template v-if="adminTab === 'overview'"><div class="summary-grid four"><div class="summary-card"><span>参与人数</span><strong>24</strong><small>已分配编号</small></div><div class="summary-card"><span>已完成场次</span><strong>36 <em>/ 48</em></strong><small>两场任务合计</small></div><div class="summary-card"><span>待评分作品</span><strong>12</strong><small>教师评分进行中</small></div><div class="summary-card"><span>需要关注</span><strong>03</strong><small>存在数据缺项</small></div></div><div class="admin-layout"><section class="surface table-surface"><div class="table-title"><div><h2>近期参与进度</h2><p>快速查看各场次的完成情况。</p></div><button class="table-link" type="button" @click="adminTab = 'participants'">查看全部 →</button></div><div class="table-scroll"><table><thead><tr><th>参与编号</th><th>场次</th><th>任务</th><th>状态</th></tr></thead><tbody><tr><td>P-024</td><td>第 2 场</td><td>任务 B</td><td><span class="status-tag success">已提交</span></td></tr><tr><td>P-023</td><td>第 2 场</td><td>任务 A</td><td><span class="status-tag pending">完善中</span></td></tr><tr><td>P-022</td><td>第 1 场</td><td>任务 B</td><td><span class="status-tag neutral">待评分</span></td></tr></tbody></table></div></section><section class="surface aside-card"><span class="section-kicker">ATTENTION</span><h2>需要关注</h2><div class="attention-row"><span>缺少体验问卷</span><strong>2 场</strong></div><div class="attention-row"><span>AI 评价待重试</span><strong>1 场</strong></div><div class="attention-row"><span>教师评分未齐</span><strong>12 份</strong></div><p class="muted-note">数字为界面示例，正式系统将展示实际状态。</p></section></div></template>
      <section v-else-if="adminTab === 'tasks'" class="surface config-card"><div class="surface-heading"><div><span class="section-kicker">TASK SETTINGS</span><h2>任务配置</h2><p>编辑和预览活动任务；正式使用的版本需要冻结。</p></div><span class="status-tag pending">草稿 V1.0</span></div><div class="task-switch" aria-label="选择任务"><button v-for="key in (['A', 'B'] as const)" :key="key" type="button" :class="{ active: selectedTask === key }" @click="selectedTask = key">任务 {{ key }}</button></div><label class="field-label" for="task-name">任务 {{ selectedTask }} 名称</label><input id="task-name" v-model="taskName" class="field-input" /><label class="field-label" for="task-description">任务情境</label><textarea id="task-description" v-model="taskDescription" rows="5"></textarea><div class="config-time"><div><span>独立构思</span><strong>5 分钟</strong></div><div><span>完善作品</span><strong>20 分钟</strong></div><div><span>量规版本</span><strong>R1</strong></div></div><div class="page-actions"><button class="action-secondary" type="button" @click="flash('任务预览已更新（本次界面预览）')">预览任务</button><button class="action-primary" type="button" @click="flash('任务配置已在本次预览中保存')">保存配置</button></div></section>
      <section v-else-if="adminTab === 'participants'" class="surface table-surface"><div class="table-title"><div><h2>参与进度</h2><p>检查两场任务及评分、问卷是否完整。</p></div><button class="action-secondary" type="button" @click="flash('编号分配将在正式系统中连接')"><PhUsers :size="16" /> 分配编号</button></div><div class="table-scroll"><table><thead><tr><th>参与编号</th><th>场次</th><th>作品</th><th>问卷</th><th>教师评分</th><th>状态</th></tr></thead><tbody><tr v-for="(row, i) in [['P-024','第 2 场','已提交','已完成','1 / 2','待评分'],['P-023','第 2 场','完善中','未开始','0 / 2','进行中'],['P-022','第 1 场','已提交','未完成','2 / 2','缺问卷']]" :key="i"><td v-for="cell in row" :key="cell">{{ cell }}</td></tr></tbody></table></div></section>
      <section v-else class="surface config-card"><div class="surface-heading"><div><span class="section-kicker">DATA EXPORT</span><h2>匿名数据导出</h2><p>导出前检查字段范围和数据完整情况。</p></div></div><div class="export-list"><div v-for="item in ['场次与条件', '作品版本', 'AI 对话与建议处理', '教师原始评分', '问卷回答', '任务与量规版本']" :key="item"><PhCheckCircle :size="18" /><span>{{ item }}</span></div></div><div class="notice-strip"><PhInfo :size="19" /> 界面预览不连接数据库，导出按钮仅演示操作反馈。</div><div class="page-actions"><button class="action-primary" type="button" @click="flash('正式系统将生成匿名数据文件')"><PhDownloadSimple :size="16" /> 导出数据</button></div></section>
    </main>
    <footer class="portal-footer"><span>人机协同创造力评测系统</span><span>让创意过程更清晰、更可理解</span></footer>
    <div v-if="notice" class="portal-toast" role="status">{{ notice }}</div>
  </div>
</template>
