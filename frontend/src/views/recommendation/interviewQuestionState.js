// 推荐详情页「AI 面试题」异步状态隔离控制器：按推荐 ID 保留未完成生成请求并防止跨推荐串台
export function createInterviewQuestionState() {
  return {
    questionSets: [],
    questionLoading: false,
    questionGenerating: false,
    questionError: '',
  }
}

export function createInterviewQuestionController(state = createInterviewQuestionState()) {
  let active = true
  let currentRecId = ''
  let listSeq = 0
  const inFlightGenerations = new Map()

  const normalizeId = (id) => (id === null || id === undefined ? '' : String(id))

  const isListCurrent = (recId, seq) =>
    active && seq === listSeq && normalizeId(recId) !== '' && normalizeId(recId) === currentRecId

  function mergeQuestionSets(headSets, tailSets) {
    const merged = []
    const seenIds = new Set()
    for (const item of [...(headSets || []), ...(tailSets || [])]) {
      if (!item) continue
      const id = item.id
      if (id !== undefined && id !== null) {
        if (seenIds.has(id)) continue
        seenIds.add(id)
      }
      merged.push(item)
    }
    return merged
  }

  function resetForRecommendation(recId) {
    currentRecId = normalizeId(recId)
    ++listSeq
    state.questionSets = []
    state.questionLoading = false
    state.questionError = ''
    state.questionGenerating = currentRecId !== '' && inFlightGenerations.has(currentRecId)
  }

  function dispose() {
    active = false
    ++listSeq
    inFlightGenerations.clear()
  }

  async function loadList(recId, fetcher) {
    const targetId = normalizeId(recId)
    if (!active || !targetId || targetId !== currentRecId) return
    const seq = ++listSeq
    state.questionLoading = true
    state.questionError = ''
    try {
      const res = await fetcher(recId)
      if (!isListCurrent(targetId, seq)) return
      const incoming = res?.items || []
      const incomingIds = new Set(
        incoming.map((item) => item?.id).filter((id) => id !== undefined && id !== null),
      )
      const newerLocal = state.questionSets.filter((item) => !incomingIds.has(item?.id))
      state.questionSets = mergeQuestionSets(newerLocal, incoming)
    } catch (e) {
      if (!isListCurrent(targetId, seq)) return
      state.questionError = e?.message || String(e)
    } finally {
      if (isListCurrent(targetId, seq)) {
        state.questionLoading = false
      }
    }
  }

  async function generate(recId, expectedVersion, generator, { onSuccess, onError } = {}) {
    const targetId = normalizeId(recId)
    if (!active || !targetId || targetId !== currentRecId || inFlightGenerations.has(targetId)) {
      return
    }
    inFlightGenerations.set(targetId, true)
    state.questionGenerating = true
    state.questionError = ''
    try {
      const created = await generator(recId, { expected_version: expectedVersion })
      inFlightGenerations.delete(targetId)
      if (!active || targetId !== currentRecId) return
      state.questionSets = mergeQuestionSets([created], state.questionSets)
      onSuccess?.('已生成面试题组', created)
    } catch (e) {
      inFlightGenerations.delete(targetId)
      if (!active || targetId !== currentRecId) return
      const msg = e?.message || String(e)
      state.questionError = msg
      onError?.(msg, e)
    } finally {
      inFlightGenerations.delete(targetId)
      if (active && targetId === currentRecId) {
        state.questionGenerating = false
      }
    }
  }

  return {
    state,
    resetForRecommendation,
    dispose,
    loadList,
    generate,
  }
}
