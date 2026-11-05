<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { participantApi, type DraftContent, type Progress } from './participant-api'
import { useDraftSaver } from './draft-saver'
import {
  PhArrowUUpLeft,
  PhArrowUUpRight,
  PhCaretDown,
  PhCaretUp,
  PhCheckCircle,
  PhEye,
  PhFileText,
  PhFloppyDisk,
  PhLinkSimple,
  PhListBullets,
  PhListNumbers,
  PhTextAlignCenter,
  PhTextAlignLeft,
  PhTextB,
  PhTextItalic,
  PhTextUnderline,
  PhX,
} from '@phosphor-icons/vue'

const props = defineProps<{ active: boolean; task: 'A' | 'B'; aiEnabled: boolean; sessionId?: string; csrf?: string; initialDraft?: Progress['draft']; deadline?: string | null; serverTime?: string }>()
const emit = defineEmits<{ back: []; continue: [sections: { label: string; title: string; html: string }[], revision: number] }>()

type SectionId = 'goal' | 'student' | 'flow' | 'resource' | 'assessment'
type SaveState = 'saved' | 'saving'
type SuggestionState = 'pending' | 'adopted' | 'ignored'

interface Section {
  id: SectionId
  label: string
  title: string
  hint: string
  html: string
}

const sections = ref<Section[]>([
  {
    id: 'goal',
    label: '目标',
    title: '1. 活动目标',
    hint: '写清学生完成活动后能做什么，建议使用可观察的行为表述。',
    html: '<p>完成活动后，学生能够：</p><ol><li>指出 AI 生成学习资料中可能存在的事实错误、证据不足或来源不明的问题。</li><li>运用可核验的信息来源，对资料中的关键说法进行判断，并说明修订依据。</li></ol>',
  },
  {
    id: 'student',
    label: '学生任务',
    title: '2. 学生任务',
    hint: '描述学生要亲自完成的任务，而不只是教师要讲授的内容。',
    html: '<p>学生以 3—4 人小组为单位，阅读一段 AI 生成的学习资料，标记可疑说法，查找至少一种可靠来源进行核验。各组提交一张“核验与修订卡”，包含原说法、核验依据、判断结论和修订后的表述。</p>',
  },
  {
    id: 'flow',
    label: '活动流程',
    title: '3. 活动流程与时间分配',
    hint: '请按时间顺序，详细描述每个阶段的活动安排、教师活动、学生活动及预期产出。建议总时长 40 分钟。',
    html: '<h3>1. 引入与情境激发（5 分钟）</h3><ul><li><strong>教师活动：</strong>展示一段由 AI 生成的关于“气候变化对城市的影响”的学习资料片段，并提出问题：这段内容是否可信？如果用于课堂学习，你会如何判断？</li><li><strong>学生活动：</strong>快速阅读材料，结合已有知识进行初步判断，在便签纸上写下至少一个需要进一步核验的点。</li><li><strong>预期产出：</strong>形成个人初步判断与 1—2 个待核验问题。</li></ul><h3>2. 小组核验与信息查证（20 分钟）</h3><ul><li><strong>教师活动：</strong>提供核验任务单和可信信息来源清单，介绍核验策略（如来源判断、数据比对、观点一致性检验等），巡视并提供必要指导。</li><li><strong>学生活动：</strong>以 3—4 人为小组，对 AI 生成资料中的关键信息进行核验，查找并引用可靠来源，记录核验过程与结论。</li><li><strong>预期产出：</strong>完成小组核验记录表，列出核验结论与所引用的权威来源链接。</li></ul><h3>3. 全班分享与交流（10 分钟）</h3><ul><li><strong>教师活动：</strong>邀请 2—3 个小组进行汇报，组织全班讨论：不同小组的结论是否一致？有哪些信息容易被误判？我们可以形成哪些判断准则？</li><li><strong>学生活动：</strong>倾听其他组汇报，提出质疑或补充，比较不同信息来源的可靠性，归纳核验要点。</li><li><strong>预期产出：</strong>形成班级层面的“AI 资料核验要点清单”。</li></ul><h3>4. 反思与迁移（5 分钟）</h3><ul><li><strong>教师活动：</strong>引导学生回顾本节课的学习过程，提炼可迁移的核验方法，并讨论在其他学科学习中如何应用。</li><li><strong>学生活动：</strong>完成个人反思：本节课我学到了什么？在今后的学习中，我将如何更审慎地使用 AI 生成的资料？</li><li><strong>预期产出：</strong>提交学习反思卡（3—5 句话）。</li></ul>',
  },
  {
    id: 'resource',
    label: '资源',
    title: '4. 材料与工具',
    hint: '只列出普通学校条件下可以获得的资源。',
    html: '<ul><li>一段含有待核验说法的 AI 生成学习资料。</li><li>投影设备、学生已有的手机或电脑。</li><li>核验任务单、可信来源清单与小组修订卡模板。</li></ul>',
  },
  {
    id: 'assessment',
    label: '评价',
    title: '5. 评价方式',
    hint: '说明教师如何看见学生的核验依据与修订结果。',
    html: '<p>教师根据小组提交的“核验与修订卡”检查三项表现：是否指出需要核验的关键说法，是否提供可追溯的依据，修订是否与证据一致。再结合个人反思卡，判断学生能否把核验方法迁移到新的学习情境。</p>',
  },
])
if (props.task === 'B') {
  const sample = [
    '<p>学生能够识别 AI 生成学习计划中与个人学习情况不匹配的建议，并说明调整依据。</p>',
    '<p>学生对照学习情境，判断一份复习计划的适用性，并提出可执行的调整。</p>',
    '<h3>1. 情境导入（5 分钟）</h3><p>展示一份 AI 生成的复习计划，让学生提出初步判断。</p><h3>2. 分析与调整（20 分钟）</h3><p>小组对照学习目标、时间和薄弱环节，标出计划的问题并提出修改。</p><h3>3. 分享与交流（10 分钟）</h3><p>各组介绍调整依据，比较不同方案的适用情境。</p><h3>4. 反思迁移（5 分钟）</h3><p>学生写下使用 AI 学习建议时需要关注的个人条件。</p>',
    '<p>AI 生成的示例复习计划、学习情境卡、修改记录单与投影设备。</p>',
    '<p>教师根据学生指出的问题、给出的调整依据与修改方案进行评价。</p>',
  ]
  sections.value = sections.value.map((section, index) => ({ ...section, html: sample[index] }))
}

const activeId = ref<SectionId>('flow')
const activeSection = computed(() => sections.value.find((section) => section.id === activeId.value)!)
const editor = ref<HTMLDivElement | null>(null)
const saveState = ref<SaveState>('saved')
const saver = useDraftSaver<DraftContent>(() => Object.fromEntries(sections.value.map(section => [section.id, section.html])) as DraftContent, (revision, value) => participantApi.saveDraft(props.sessionId!, props.csrf!, revision, value))
const displayedSaveState = computed(() => props.sessionId ? saver.status.value : saveState.value)
let loadedSession = ''
let serverOffset = 0
const remainingSeconds = ref(18 * 60 + 42)
const taskExpanded = ref(false)
const adviceExpanded = ref(true)
const suggestionState = ref<SuggestionState>('pending')
const adoptOpen = ref(false)
const adoptMode = ref<'direct' | 'edit'>('edit')
const adoptTarget = ref<SectionId>('flow')
const chatOpen = ref(false)
const chatInput = ref('')
const chatMessages = ref<{ role: 'user' | 'assistant'; text: string }[]>([])
const previewOpen = ref(false)
const originalSuggestion = computed(() => props.task === 'A' ? '在“小组核验与信息查证”阶段增加具体的分工说明，例如设置“资料检索、信息比对、结论撰写、汇报准备”四个角色，以提高小组协作的清晰度。' : '让学生分别从学习目标、可用时间和个人薄弱环节三个方面检查 AI 生成的复习计划，并解释调整依据。')
const adoptText = ref(originalSuggestion.value)
const toast = ref('')
const previewCloseButton = ref<HTMLButtonElement | null>(null)
const adoptTextarea = ref<HTMLTextAreaElement | null>(null)

let saveTimer: number | undefined
let countdownTimer: number | undefined
let toastTimer: number | undefined

const timeLabel = computed(() => {
  const minutes = Math.floor(remainingSeconds.value / 60)
  const seconds = remainingSeconds.value % 60
  return String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0')
})

const characterCount = computed(() => {
  const plain = activeSection.value.html.replace(/<[^>]+>/g, '').replace(/\s/g, '')
  return plain.length
})

function showToast(message: string) {
  toast.value = message
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => { toast.value = '' }, 3200)
}

function renderEditor() {
  if (editor.value) editor.value.innerHTML = activeSection.value.html
}

function captureEditor() {
  if (editor.value) activeSection.value.html = editor.value.innerHTML
}

function queueSave() {
  if (props.sessionId) { saver.changed(); return }
  saveState.value = 'saving'
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveState.value = 'saved' }, 900)
}

function onEditorInput() {
  captureEditor()
  queueSave()
}

async function saveDraft() {
  captureEditor()
  if (props.sessionId) {
    if (await saver.flush()) showToast('草稿已保存')
    else showToast(saver.error.value)
    return
  }
  queueSave()
  showToast('草稿已在本页暂存（演示状态）')
}

async function leaveWorkbench() { captureEditor(); if (!props.sessionId || await saver.flush()) emit('back'); else showToast(saver.error.value) }
async function continueWorkbench() { captureEditor(); if (props.sessionId && !(await saver.flush())) { showToast(saver.error.value); return }; emit('continue', sections.value.map(({ label, title, html }) => ({ label, title, html })), saver.revision.value) }

watch(() => [props.active, props.sessionId, props.initialDraft] as const, async ([active, id, draft]) => {
  if (active && id && draft && loadedSession !== id) {
    sections.value = sections.value.map(section => ({ ...section, html: draft.sections[section.id] ?? '' }))
    saver.reset(draft.revision)
    loadedSession = id
    await nextTick()
    renderEditor()
  }
}, { immediate: true })
watch(() => props.serverTime, value => { if (value) serverOffset = Date.parse(value) - Date.now() }, { immediate: true })

async function setSection(id: SectionId) {
  if (id === activeId.value) return
  captureEditor()
  activeId.value = id
  await nextTick()
  renderEditor()
}

function format(command: string) {
  if (props.sessionId && remainingSeconds.value <= 0) return
  editor.value?.focus()
  document.execCommand(command, false)
  onEditorInput()
}

function setBlockFormat(event: Event) {
  const target = event.target as HTMLSelectElement
  editor.value?.focus()
  document.execCommand('formatBlock', false, target.value)
  onEditorInput()
}

function setFontSize(event: Event) {
  const target = event.target as HTMLSelectElement
  editor.value?.focus()
  document.execCommand('fontSize', false, target.value)
  onEditorInput()
}

function addLink() {
  const url = window.prompt('请输入链接地址（需以 https:// 开头）')
  if (!url) return
  if (!url.startsWith('https://')) {
    showToast('请使用以 https:// 开头的链接')
    return
  }
  editor.value?.focus()
  document.execCommand('createLink', false, url)
  onEditorInput()
}

function onPaste(event: ClipboardEvent) {
  event.preventDefault()
  const plainText = event.clipboardData?.getData('text/plain') ?? ''
  document.execCommand('insertText', false, plainText)
}

async function openAdopt(mode: 'direct' | 'edit') {
  if (props.sessionId && remainingSeconds.value <= 0) return
  adoptMode.value = mode
  adoptTarget.value = activeId.value
  adoptText.value = originalSuggestion.value
  adoptOpen.value = true
  await nextTick()
  if (mode === 'edit') adoptTextarea.value?.focus()
}

function sendDemoMessage() {
  const question = chatInput.value.trim()
  if (!question) return
  chatMessages.value.push({ role: 'user', text: question }, { role: 'assistant', text: '示例回复：可以先让学生比较两份来源，再说明每次修改的依据。你可以结合实际课堂条件决定是否使用。' })
  chatInput.value = ''
}

async function confirmAdopt() {
  const value = adoptText.value.trim()
  if (!value) {
    showToast('请先填写要采纳的文字')
    return
  }
  captureEditor()
  const safeText = value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const target = sections.value.find((section) => section.id === adoptTarget.value)!
  target.html += '<p><strong>补充：</strong>' + safeText + '</p>'
  suggestionState.value = 'adopted'
  adoptOpen.value = false
  queueSave()
  await nextTick()
  renderEditor()
  showToast('已由你确认，文字加入“' + target.label + '”')
}

function ignoreSuggestion() {
  suggestionState.value = 'ignored'
  showToast('已忽略这条建议')
}

async function openPreview() {
  captureEditor()
  previewOpen.value = true
  await nextTick()
  previewCloseButton.value?.focus()
}

function onGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    adoptOpen.value = false
    previewOpen.value = false
  }
}
function warnUnsaved(event: BeforeUnloadEvent) { if (props.active && props.sessionId && saver.status.value !== 'saved') { event.preventDefault(); event.returnValue = '' } }

onMounted(() => {
  renderEditor()
  countdownTimer = window.setInterval(() => {
    if (!props.active) return
    if (props.sessionId && props.deadline) remainingSeconds.value = Math.max(0, Math.ceil((Date.parse(props.deadline) - Date.now() - serverOffset) / 1000))
    else if (remainingSeconds.value > 0) remainingSeconds.value -= 1
    if (remainingSeconds.value === 0 && countdownTimer) {
      if (props.sessionId) { void saver.flush(); showToast('创作时间已结束，正在保存最后的修改') }
      else showToast('演示计时已结束；原型不会自动提交')
      window.clearInterval(countdownTimer)
    }
  }, 1000)
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('beforeunload', warnUnsaved)
})

onBeforeUnmount(() => {
  if (saveTimer) window.clearTimeout(saveTimer)
  if (countdownTimer) window.clearInterval(countdownTimer)
  if (toastTimer) window.clearTimeout(toastTimer)
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('beforeunload', warnUnsaved)
})
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="brand">
        <span class="brand-icon" aria-hidden="true"><PhFileText :size="25" weight="fill" /></span>
        <span class="brand-name">人机协同创造力评测系统</span>
        <span class="header-divider" aria-hidden="true"></span>
        <span class="header-context">任务 {{ task }} · 完善作品</span>
      </div>
      <div class="header-status">
        <button class="text-button" type="button" @click="leaveWorkbench">返回构思</button>
        <span class="timer" role="timer" aria-label="剩余时间">剩余 {{ timeLabel }}</span>
        <span class="status-dot" :class="{ saving: displayedSaveState !== 'saved' }" aria-hidden="true"></span>
        <span class="save-label" role="status" :title="sessionId ? saver.error.value : '演示状态；刷新页面后不会保留编辑内容'">{{ displayedSaveState === 'saving' ? '保存中…' : displayedSaveState === 'unsaved' ? '待保存' : displayedSaveState === 'error' ? '保存失败，请重试' : '已保存' }}</span>
        <button class="text-button save-button" type="button" @click="saveDraft"><PhFloppyDisk :size="16" />保存草稿</button>
        <button class="preview-button" type="button" @click="openPreview"><PhEye :size="18" />预览作品</button>
        <button class="preview-button" type="button" @click="continueWorkbench">提交与问卷</button>
      </div>
    </header>

    <nav class="section-nav" aria-label="作品章节">
      <button
        v-for="section in sections"
        :key="section.id"
        type="button"
        class="section-tab"
        :class="{ active: activeId === section.id }"
        :aria-current="activeId === section.id ? 'step' : undefined"
        @click="setSection(section.id)"
      >{{ section.label }}</button>
    </nav>

    <div class="mobile-notice">正式创作建议使用电脑；手机上可查看此演示页面。</div>

    <section class="task-panel" aria-label="任务要求">
      <button class="task-toggle" type="button" :aria-expanded="taskExpanded" @click="taskExpanded = !taskExpanded">
        <strong>任务要求</strong>
        <span class="task-divider" aria-hidden="true"></span>
        <span class="task-text">{{ task === 'A' ? '设计一节 40 分钟课堂活动，面向高一学生，帮助他们核验 AI 生成的学习资料。' : '设计一节 40 分钟课堂活动，帮助高一学生评价并调整 AI 生成的学习建议。' }}</span>
        <PhCaretUp v-if="taskExpanded" :size="18" aria-hidden="true" />
        <PhCaretDown v-else :size="18" aria-hidden="true" />
      </button>
      <div v-if="taskExpanded" class="task-details">
        <p>请写出活动目标、学生任务、活动流程与时间分配、材料与工具、评价方式。活动应让学生提出自己的判断，并展示依据与修订结果。</p>
        <p>先独立构思，再完善作品；最终作品建议约 500—800 字。评分关注新颖性、教育适切性与可实施性。</p>
      </div>
    </section>

    <main class="workspace">
      <section class="editor-panel" :aria-labelledby="'section-title-' + task">
        <div class="editor-heading">
          <h1 :id="'section-title-' + task">{{ activeSection.title }}</h1>
          <p>{{ activeSection.hint }}</p>
        </div>
        <div class="toolbar" role="toolbar" aria-label="文字编辑工具">
          <label class="sr-only" :for="'block-format-' + task">段落样式</label>
          <select :id="'block-format-' + task" class="tool-select" title="段落样式" @change="setBlockFormat">
            <option value="p">正文</option>
            <option value="h3">小标题</option>
          </select>
          <span class="tool-separator" aria-hidden="true"></span>
          <label class="sr-only" :for="'font-size-' + task">字号</label>
          <select :id="'font-size-' + task" class="tool-select size-select" title="字号" @change="setFontSize">
            <option value="2">14px</option>
            <option value="3" selected>16px</option>
            <option value="4">18px</option>
          </select>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" class="tool-button" aria-label="加粗" title="加粗" @mousedown.prevent @click="format('bold')"><PhTextB :size="18" /></button>
          <button type="button" class="tool-button" aria-label="斜体" title="斜体" @mousedown.prevent @click="format('italic')"><PhTextItalic :size="18" /></button>
          <button type="button" class="tool-button" aria-label="下划线" title="下划线" @mousedown.prevent @click="format('underline')"><PhTextUnderline :size="18" /></button>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" class="tool-button" aria-label="项目符号列表" title="项目符号列表" @mousedown.prevent @click="format('insertUnorderedList')"><PhListBullets :size="19" /></button>
          <button type="button" class="tool-button" aria-label="编号列表" title="编号列表" @mousedown.prevent @click="format('insertOrderedList')"><PhListNumbers :size="19" /></button>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" class="tool-button" aria-label="左对齐" title="左对齐" @mousedown.prevent @click="format('justifyLeft')"><PhTextAlignLeft :size="19" /></button>
          <button type="button" class="tool-button" aria-label="居中" title="居中" @mousedown.prevent @click="format('justifyCenter')"><PhTextAlignCenter :size="19" /></button>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" class="tool-button" aria-label="插入链接" title="插入链接" @mousedown.prevent @click="addLink"><PhLinkSimple :size="18" /></button>
          <span class="toolbar-spacer"></span>
          <button type="button" class="tool-button" aria-label="撤销" title="撤销" @mousedown.prevent @click="format('undo')"><PhArrowUUpLeft :size="18" /></button>
          <button type="button" class="tool-button" aria-label="重做" title="重做" @mousedown.prevent @click="format('redo')"><PhArrowUUpRight :size="18" /></button>
        </div>
        <div class="editor-scroll">
          <div ref="editor" class="rich-editor" :contenteditable="!sessionId || remainingSeconds > 0" role="textbox" aria-multiline="true" :aria-label="activeSection.title" spellcheck="true" @input="onEditorInput" @paste="onPaste"></div>
        </div>
        <div class="editor-footer">
          <span>当前章节 {{ characterCount }} 字</span>
          <span>编辑器内滚动可继续查看内容</span>
        </div>
      </section>
    </main>

    <section v-if="aiEnabled" class="ai-dock" aria-label="AI 建议">
      <div class="ai-dock-heading">
        <button class="dock-toggle" type="button" :aria-expanded="adviceExpanded" @click="adviceExpanded = !adviceExpanded">
          <strong>AI 建议 · 示例</strong>
          <PhCaretUp v-if="adviceExpanded" :size="16" />
          <PhCaretDown v-else :size="16" />
        </button>
        <button class="chat-toggle" type="button" @click="chatOpen = !chatOpen">{{ chatOpen ? '收起对话' : '提出问题' }}</button>
        <span v-if="!adviceExpanded" class="collapsed-note">点击展开，查看与当前作品相关的建议</span>
      </div>
      <div v-if="adviceExpanded" class="ai-dock-body">
        <p v-if="suggestionState === 'pending'" class="suggestion-text">{{ originalSuggestion }}</p>
        <p v-else-if="suggestionState === 'adopted'" class="suggestion-result"><PhCheckCircle :size="18" />建议已由你确认加入作品；你仍可继续编辑。</p>
        <p v-else class="suggestion-result">你已忽略这条建议，作品内容没有变化。</p>
        <div class="ai-actions">
          <template v-if="suggestionState === 'pending'">
            <button class="adopt-button" type="button" @click="openAdopt('edit')">改写后采纳</button>
            <button class="ignore-button" type="button" @click="openAdopt('direct')">直接采纳</button>
            <button class="ignore-button" type="button" @click="ignoreSuggestion">暂不采纳</button>
          </template>
          <button v-else class="ignore-button" type="button" @click="suggestionState = 'pending'">重新查看建议</button>
        </div>
      </div>
      <div v-if="chatOpen" class="chat-panel"><div class="chat-panel-head"><strong>与 AI 讨论</strong><span>示例对话 · 尚未连接模型</span></div><div class="chat-history"><p v-if="!chatMessages.length">可以询问如何完善活动步骤、学生任务或评价方式。</p><div v-for="(message, index) in chatMessages" :key="index" :class="['chat-message', message.role]"><strong>{{ message.role === 'user' ? '你' : 'AI · 示例' }}</strong><span>{{ message.text }}</span></div></div><form class="chat-form" @submit.prevent="sendDemoMessage"><label class="sr-only" :for="'chat-input-' + task">向 AI 提问</label><input :id="'chat-input-' + task" v-model="chatInput" placeholder="例如：如何让学生说明判断依据？" /><button class="adopt-button" type="submit" :disabled="!chatInput.trim()">发送</button></form></div>
    </section>
    <section v-else class="ai-dock" aria-label="任务提示"><div class="ai-dock-heading"><strong>任务提示</strong></div><p class="suggestion-text">请独立完善方案，并结合学习情境说明判断依据与修改结果。</p></section>

    <div v-if="toast" class="toast" role="status">{{ toast }}</div>

    <div v-if="adoptOpen" class="modal-backdrop" @click.self="adoptOpen = false">
      <section class="modal adopt-modal" role="dialog" aria-modal="true" :aria-labelledby="'adopt-title-' + task">
        <button class="modal-close" type="button" aria-label="关闭" @click="adoptOpen = false"><PhX :size="20" /></button>
        <h2 :id="'adopt-title-' + task">{{ adoptMode === 'edit' ? '改写后采纳 AI 建议' : '确认采纳 AI 建议' }}</h2>
        <p>选择要加入的章节，并由你确认。AI 不会自动覆盖作品。</p>
        <label :for="'adopt-target-' + task">目标章节</label>
        <select :id="'adopt-target-' + task" v-model="adoptTarget" class="adopt-select"><option v-for="section in sections" :key="section.id" :value="section.id">{{ section.label }}</option></select>
        <label :for="'adopt-text-' + task">要加入作品的文字</label>
        <textarea :id="'adopt-text-' + task" ref="adoptTextarea" v-model="adoptText" :readonly="adoptMode === 'direct'" rows="6"></textarea>
        <div class="modal-actions">
          <button class="secondary-button" type="button" @click="adoptOpen = false">取消</button>
          <button class="primary-button" type="button" @click="confirmAdopt">确认加入作品</button>
        </div>
      </section>
    </div>

    <div v-if="previewOpen" class="modal-backdrop" @click.self="previewOpen = false">
      <section class="modal preview-modal" role="dialog" aria-modal="true" :aria-labelledby="'preview-title-' + task">
        <div class="preview-header">
          <div>
            <span class="preview-kicker">作品预览 · 任务 {{ task }}</span>
            <h2 :id="'preview-title-' + task">高中 AI 素养课堂活动方案</h2>
          </div>
          <button ref="previewCloseButton" class="modal-close" type="button" aria-label="关闭预览" @click="previewOpen = false"><PhX :size="20" /></button>
        </div>
        <p class="preview-intro">{{ sessionId ? '这是目前五个章节的预览。确认提交前，你仍可返回编辑。' : '这是目前五个章节的内容预览。此演示原型不会提交作品或连接真实评分服务。' }}</p>
        <div class="preview-content">
          <section v-for="section in sections" :key="section.id">
            <h3>{{ section.title }}</h3>
            <div class="preview-html" v-html="section.html"></div>
          </section>
        </div>
        <div class="modal-actions"><button class="primary-button" type="button" @click="previewOpen = false">返回继续编辑</button></div>
      </section>
    </div>
  </div>
</template>
