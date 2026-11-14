import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm'
import axios from 'axios'

// 加载实际 API 模块，只替换登录状态和路由，Axios 仍运行真实拦截器。
async function loadApi() {
  const context = createContext({ Blob })
  const store = { token: '', logoutCount: 0, logout() { this.logoutCount++ } }
  const redirects = []
  const router = {
    currentRoute: { value: { name: 'Candidates', fullPath: '/candidates/20' } },
    push: (route) => redirects.push(route),
  }
  const dependency = (name, value) => new SyntheticModule([name], function () {
    this.setExport(name, value)
  }, { context })
  const dependencies = {
    axios: dependency('default', axios),
    '@/stores/user': dependency('useUserStore', () => store),
    '@/router': dependency('default', router),
  }
  const request = new SourceTextModule(
    await readFile(new URL('../src/api/request.js', import.meta.url), 'utf8'),
    { context, initializeImportMeta: (meta) => { meta.env = {} } },
  )
  await request.link((name) => dependencies[name])
  await request.evaluate()
  const modules = {}
  for (const name of ['match', 'resume', 'recommendation']) {
    const module = new SourceTextModule(
      await readFile(new URL(`../src/api/${name}.js`, import.meta.url), 'utf8'),
      { context },
    )
    await module.link(() => request)
    await module.evaluate()
    modules[name] = module.namespace
  }
  return { request: request.namespace.default, ...modules, store, redirects }
}

test('AI 请求为主备模型留出等待时间，普通列表保持原超时', async () => {
  const api = await loadApi()
  const calls = []
  api.request.defaults.adapter = async (config) => {
    calls.push(config)
    return { data: { ok: true }, status: 200, headers: {}, config }
  }
  await api.match.runMatch({ job_id: 10 })
  await api.resume.extractSkills(20, 0)
  await api.recommendation.generateInterviewQuestions(30, { expected_version: 2 })
  await api.match.listMatches({ page: 1 })
  await api.recommendation.listInterviewQuestions(30)
  assert.deepEqual(calls.map((call) => call.timeout), [150000, 150000, 150000, 10000, 10000])
  assert.deepEqual(calls.map((call) => call.url), [
    '/api/v1/matches',
    '/api/v1/resumes/20/extract-skills',
    '/api/v1/recommendations/30/interview-questions',
    '/api/v1/matches',
    '/api/v1/recommendations/30/interview-questions',
  ])
})

for (const code of ['ECONNABORTED', 'ETIMEDOUT']) {
  for (const businessStatus of [false, true]) {
    test(`${code} 超时提示先确认结果，不自动重试（businessStatus=${businessStatus}）`, async () => {
      const api = await loadApi()
      let calls = 0
      api.request.defaults.adapter = async (config) => {
        calls++
        throw new axios.AxiosError('SYNTHETIC_INTERNAL_DETAIL', code, config)
      }
      await assert.rejects(api.request.post('/api/v1/matches', {}, { businessStatus }), (error) => {
        const message = businessStatus ? error.message : error
        assert.match(message, /超时/)
        assert.match(message, /刷新.*确认.*结果/)
        assert.doesNotMatch(message, /SYNTHETIC_INTERNAL_DETAIL/)
        return true
      })
      assert.equal(calls, 1)
      assert.equal(api.store.logoutCount, 0)
    })
  }
}

for (const blob of [false, true]) {
  test(`服务器业务错误保留状态与说明（blob=${blob}）`, async () => {
    const api = await loadApi()
    const data = { detail: '技能已变化，请刷新后重试' }
    api.request.defaults.adapter = async (config) => {
      throw new axios.AxiosError('SYNTHETIC', 'ERR_BAD_REQUEST', config, null, {
        status: 409, data: blob ? new Blob([JSON.stringify(data)]) : data,
      })
    }
    await assert.rejects(api.match.runMatch({}), (error) => {
      assert.equal(error.status, 409)
      assert.equal(error.message, data.detail)
      return true
    })
  })
}

test('登录失效仍清除状态并保留返回地址', async () => {
  const api = await loadApi()
  api.request.defaults.adapter = async (config) => {
    throw new axios.AxiosError('SYNTHETIC', 'ERR_BAD_REQUEST', config, null, {
      status: 401, data: { detail: '请重新登录' },
    })
  }
  await assert.rejects(api.match.runMatch({}), (error) => error.status === 401)
  assert.equal(api.store.logoutCount, 1)
  assert.equal(api.redirects[0].name, 'Login')
  assert.equal(api.redirects[0].query.redirect, '/candidates/20')
})
