import assert from 'node:assert/strict'
import test from 'node:test'
import { createInterviewQuestionController } from '../src/views/recommendation/interviewQuestionState.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

test('切换推荐 A -> B 后，A 的迟到成功响应不会写入 B 的列表、提示或加载态', async () => {
  const ctrl = createInterviewQuestionController()
  const genA = deferred()
  const listB = deferred()
  const notices = []

  ctrl.resetForRecommendation(101)
  const genPromise = ctrl.generate(101, 2, () => genA.promise, {
    onSuccess: (msg) => notices.push({ type: 'success', msg }),
    onError: (msg) => notices.push({ type: 'error', msg }),
  })
  assert.equal(ctrl.state.questionGenerating, true)

  // 用户在 A 请求尚未完成时切换到 B
  ctrl.resetForRecommendation(202)
  assert.equal(ctrl.state.questionGenerating, false)
  assert.deepEqual(ctrl.state.questionSets, [])

  const listPromise = ctrl.loadList(202, () => listB.promise)
  assert.equal(ctrl.state.questionLoading, true)

  listB.resolve({ items: [{ id: 2001, recommendation_id: 202 }] })
  await listPromise
  assert.equal(ctrl.state.questionLoading, false)
  assert.deepEqual(ctrl.state.questionSets, [{ id: 2001, recommendation_id: 202 }])

  // A 的生成请求迟到成功：绝不能污染 B
  genA.resolve({ id: 1001, recommendation_id: 101 })
  await genPromise
  assert.deepEqual(ctrl.state.questionSets, [{ id: 2001, recommendation_id: 202 }])
  assert.equal(ctrl.state.questionGenerating, false)
  assert.equal(ctrl.state.questionError, '')
  assert.deepEqual(notices, [])

  // 回到 A 重新拉取列表时，可看到服务端已落库的题组
  ctrl.resetForRecommendation(101)
  await ctrl.loadList(101, async () => ({ items: [{ id: 1001, recommendation_id: 101 }] }))
  assert.deepEqual(ctrl.state.questionSets, [{ id: 1001, recommendation_id: 101 }])
})

test('切换推荐 A -> B 后，A 的迟到失败与旧列表响应均不污染 B', async () => {
  const ctrl = createInterviewQuestionController()
  const genA = deferred()
  const listA = deferred()
  const notices = []

  ctrl.resetForRecommendation(101)
  const listAPromise = ctrl.loadList(101, () => listA.promise)
  const genAPromise = ctrl.generate(101, 2, () => genA.promise, {
    onSuccess: (msg) => notices.push({ type: 'success', msg }),
    onError: (msg) => notices.push({ type: 'error', msg }),
  })

  ctrl.resetForRecommendation(202)
  await ctrl.loadList(202, async () => ({ items: [{ id: 2002, recommendation_id: 202 }] }))

  listA.reject(new Error('A列表失败'))
  genA.reject(new Error('A生成超时'))
  await Promise.all([listAPromise, genAPromise])

  assert.deepEqual(ctrl.state.questionSets, [{ id: 2002, recommendation_id: 202 }])
  assert.equal(ctrl.state.questionError, '')
  assert.equal(ctrl.state.questionLoading, false)
  assert.equal(ctrl.state.questionGenerating, false)
  assert.deepEqual(notices, [])
})

test('快速 A -> B -> A：B 可独立生成，切回 A 保持生成中且最多发起一次 POST，完成后更新 A 列表', async () => {
  const ctrl = createInterviewQuestionController()
  const genA = deferred()
  const genB = deferred()
  let postCountA = 0
  let postCountB = 0
  const notices = []

  // 1. 在 A 发起生成
  ctrl.resetForRecommendation(101)
  await ctrl.loadList(101, async () => ({ items: [{ id: 1000, recommendation_id: 101 }] }))
  const genAPromise = ctrl.generate(
    101,
    2,
    () => {
      postCountA++
      return genA.promise
    },
    {
      onSuccess: (msg) => notices.push({ rec: 101, type: 'success', msg }),
      onError: (msg) => notices.push({ rec: 101, type: 'error', msg }),
    },
  )
  assert.equal(ctrl.state.questionGenerating, true)

  // 2. A 未完成时切到 B：B 按钮可用且能独立发起生成
  ctrl.resetForRecommendation(202)
  assert.equal(ctrl.state.questionGenerating, false)
  const genBPromise = ctrl.generate(
    202,
    2,
    () => {
      postCountB++
      return genB.promise
    },
    {
      onSuccess: (msg) => notices.push({ rec: 202, type: 'success', msg }),
      onError: (msg) => notices.push({ rec: 202, type: 'error', msg }),
    },
  )
  assert.equal(ctrl.state.questionGenerating, true)
  assert.equal(postCountB, 1)

  // 3. A 仍未完成时快速切回 A：A 保持生成中，再次触发 generate 不会发起第 2 次 POST
  ctrl.resetForRecommendation(101)
  await ctrl.loadList(101, async () => ({ items: [{ id: 1000, recommendation_id: 101 }] }))
  assert.equal(ctrl.state.questionGenerating, true)
  await ctrl.generate(101, 2, () => {
    postCountA++
    return genA.promise
  })
  assert.equal(postCountA, 1)

  // B 先完成，不应影响当前 A 页面
  genB.resolve({ id: 2001, recommendation_id: 202 })
  await genBPromise
  assert.equal(ctrl.state.questionGenerating, true)
  assert.deepEqual(notices, [])

  // 4. A 最终完成：当前停留在 A，立即更新 A 的题组列表并关闭生成中状态
  genA.resolve({ id: 1001, recommendation_id: 101 })
  await genAPromise
  assert.equal(ctrl.state.questionGenerating, false)
  assert.deepEqual(
    ctrl.state.questionSets.map((item) => item.id),
    [1001, 1000],
  )
  assert.deepEqual(notices, [{ rec: 101, type: 'success', msg: '已生成面试题组' }])
})

test('快速 A -> B -> A 时旧请求失败：正确恢复 A 的加载态并展示失败提示', async () => {
  const ctrl = createInterviewQuestionController()
  const genA = deferred()
  const notices = []

  ctrl.resetForRecommendation(101)
  const genAPromise = ctrl.generate(101, 2, () => genA.promise, {
    onSuccess: (msg) => notices.push({ type: 'success', msg }),
    onError: (msg) => notices.push({ type: 'error', msg }),
  })

  ctrl.resetForRecommendation(202)
  assert.equal(ctrl.state.questionGenerating, false)

  ctrl.resetForRecommendation(101)
  assert.equal(ctrl.state.questionGenerating, true)

  genA.reject(new Error('大模型服务异常，请稍后重试'))
  await genAPromise

  assert.equal(ctrl.state.questionGenerating, false)
  assert.equal(ctrl.state.questionError, '大模型服务异常，请稍后重试')
  assert.deepEqual(notices, [{ type: 'error', msg: '大模型服务异常，请稍后重试' }])
})

test('A 生成 -> 切到 B 独立生成 -> 切回 A 发起 GET -> POST 先返回 1002 -> GET 迟到只返回 1001，最终显示 [1002, 1001]', async () => {
  const ctrl = createInterviewQuestionController()
  const genA = deferred()
  const genB = deferred()
  const listAOnReturn = deferred()
  const notices = []

  // 1. A 开始生成
  ctrl.resetForRecommendation(101)
  const genAPromise = ctrl.generate(101, 2, () => genA.promise, {
    onSuccess: (msg) => notices.push({ rec: 101, type: 'success', msg }),
    onError: (msg) => notices.push({ rec: 101, type: 'error', msg }),
  })
  assert.equal(ctrl.state.questionGenerating, true)

  // 2. 切到 B，确认 B 仍可独立生成
  ctrl.resetForRecommendation(202)
  assert.equal(ctrl.state.questionGenerating, false)
  const genBPromise = ctrl.generate(202, 2, () => genB.promise, {
    onSuccess: (msg) => notices.push({ rec: 202, type: 'success', msg }),
    onError: (msg) => notices.push({ rec: 202, type: 'error', msg }),
  })
  assert.equal(ctrl.state.questionGenerating, true)

  // 3. 切回 A 并发起历史 GET（尚未返回）
  ctrl.resetForRecommendation(101)
  assert.equal(ctrl.state.questionGenerating, true)
  const listAPromise = ctrl.loadList(101, () => listAOnReturn.promise)
  assert.equal(ctrl.state.questionLoading, true)

  // 4. POST 先成功返回新题组 1002
  genA.resolve({ id: 1002, recommendation_id: 101 })
  await genAPromise
  assert.equal(ctrl.state.questionGenerating, false)
  assert.deepEqual(
    ctrl.state.questionSets.map((item) => item.id),
    [1002],
  )
  assert.deepEqual(notices, [{ rec: 101, type: 'success', msg: '已生成面试题组' }])

  // 5. GET 迟到且只返回旧题组 1001：按题组 ID 合并，新题组在前、旧题组可见、不丢 1002
  listAOnReturn.resolve({ items: [{ id: 1001, recommendation_id: 101 }] })
  await listAPromise
  assert.equal(ctrl.state.questionLoading, false)
  assert.equal(ctrl.state.questionGenerating, false)
  assert.deepEqual(
    ctrl.state.questionSets.map((item) => item.id),
    [1002, 1001],
  )

  // 6. 再次刷新若服务端同时返回 [1002, 1001]，同一题组只出现一次
  await ctrl.loadList(101, async () => ({
    items: [
      { id: 1002, recommendation_id: 101 },
      { id: 1001, recommendation_id: 101 },
    ],
  }))
  assert.deepEqual(
    ctrl.state.questionSets.map((item) => item.id),
    [1002, 1001],
  )

  // 清理 B 的未决 Promise，确认不影响 A
  genB.resolve({ id: 2001, recommendation_id: 202 })
  await genBPromise
  assert.deepEqual(
    ctrl.state.questionSets.map((item) => item.id),
    [1002, 1001],
  )
})
