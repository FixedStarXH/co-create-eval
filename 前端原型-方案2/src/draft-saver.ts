import { onBeforeUnmount, ref } from 'vue'

type Result = { revision: number; saved_at: string }

export function useDraftSaver<T>(read: () => T, save: (revision: number, value: T) => Promise<Result>) {
  const revision = ref(0)
  const status = ref<'saved' | 'unsaved' | 'saving' | 'error'>('saved')
  const error = ref('')
  let dirty = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let inFlight: Promise<boolean> | null = null
  function reset(value: number) { revision.value = value; dirty = false; status.value = 'saved'; error.value = ''; if (timer) clearTimeout(timer) }
  function changed() { dirty = true; status.value = 'unsaved'; if (timer) clearTimeout(timer); timer = setTimeout(() => { void flush() }, 1200) }
  function flush(): Promise<boolean> {
    if (timer) clearTimeout(timer)
    if (inFlight) return inFlight
    inFlight = (async () => {
      while (dirty) {
        dirty = false
        const snapshot = JSON.parse(JSON.stringify(read())) as T
        status.value = 'saving'
        try { const result = await save(revision.value, snapshot); revision.value = result.revision; status.value = dirty ? 'unsaved' : 'saved'; error.value = '' }
        catch (e) { dirty = true; status.value = 'error'; error.value = e instanceof Error ? e.message : '保存失败'; return false }
      }
      return true
    })().finally(() => { inFlight = null })
    return inFlight
  }
  onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
  return { revision, status, error, reset, changed, flush }
}
