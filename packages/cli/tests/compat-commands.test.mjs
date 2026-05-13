import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import http from 'node:http'

const requests = []
let server
let baseUrl
let exportCommand
let statsCommand
let formatPercentage

before(async () => {
  server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost')
    const body = await readJson(req)
    requests.push({ method: req.method, path: url.pathname, search: url.search, body })

    if (req.method === 'GET' && url.pathname === '/health') {
      return json(res, { status: 'ok' })
    }
    if (req.method === 'GET' && url.pathname === '/api/sessions') {
      return json(res, {
        sessions: [{ id: 'demo', title: 'Demo Session', current_version: 3 }],
      })
    }
    if (req.method === 'GET' && url.pathname === '/api/sessions/demo') {
      return json(res, {
        id: 'demo',
        title: 'Demo Session',
        current_version: 3,
        created_at: '2026-05-13T00:00:00Z',
      })
    }
    if (req.method === 'POST' && url.pathname === '/api/export') {
      return json(res, {
        file_path: '/tmp/instant-coffee-export/index.html',
        assets_file: '/tmp/instant-coffee-export/export_manifest.json',
      })
    }
    if (req.method === 'GET' && url.pathname === '/api/stats') {
      return json(res, {
        today: { tokens: 100, cost_usd: 0.01, calls: 1 },
        week: { tokens: 200, cost_usd: 0.02, calls: 2 },
        total: { tokens: 300, cost_usd: 0.03, calls: 3, sessions: 1, pages: 2 },
        by_agent: {
          writer: { tokens: 300, cost_usd: 0.03, calls: 3 },
        },
      })
    }
    if (req.method === 'GET' && url.pathname === '/api/stats/session/demo') {
      return json(res, {
        session_id: 'demo',
        total_tokens: 300,
        cost_usd: 0.03,
        calls: 3,
        by_agent: {
          writer: { tokens: 300, cost_usd: 0.03, calls: 3 },
        },
        timeline: [
          {
            timestamp: '2026-05-13T00:00:00Z',
            agent_type: 'writer',
            tokens: 300,
            cost_usd: 0.03,
          },
        ],
      })
    }

    res.statusCode = 404
    return json(res, { detail: 'not found' })
  })

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  baseUrl = `http://127.0.0.1:${server.address().port}`
  process.env.BACKEND_URL = baseUrl
  process.env.NO_COLOR = '1'

  ;({ exportCommand } = await import('../dist/commands/export.js'))
  ;({ statsCommand } = await import('../dist/commands/stats.js'))
  ;({ formatPercentage } = await import('../dist/utils/stats-formatter.js'))
})

after(async () => {
  await new Promise((resolve) => server.close(resolve))
})

test('export command calls the compatibility export route', async () => {
  const output = await captureConsole(() =>
    exportCommand('demo', { output: 'release-out', version: 'latest' })
  )

  const exportRequest = requests.find(
    (request) => request.method === 'POST' && request.path === '/api/export'
  )
  assert.ok(exportRequest)
  assert.equal(exportRequest.body.session_id, 'demo')
  assert.equal(exportRequest.body.version, 3)
  assert.match(exportRequest.body.output_dir, /release-out$/)
  assert.match(output, /Export succeeded/)
})

test('export command can resolve the latest session before export', async () => {
  await captureConsole(() => exportCommand(undefined, { version: 'v2' }))

  const listRequest = requests.find(
    (request) => request.method === 'GET' && request.path === '/api/sessions'
  )
  const latestExport = requests
    .filter((request) => request.method === 'POST' && request.path === '/api/export')
    .at(-1)
  assert.ok(listRequest)
  assert.equal(latestExport.body.session_id, 'demo')
  assert.equal(latestExport.body.version, 2)
})

test('stats command reads global and session compatibility routes', async () => {
  const overall = await captureConsole(() => statsCommand({}))
  const session = await captureConsole(() => statsCommand({ session: 'demo' }))

  assert.match(overall, /Token usage statistics/)
  assert.match(overall, /300/)
  assert.match(session, /Session demo token usage/)
  assert.ok(
    requests.some((request) => request.method === 'GET' && request.path === '/api/stats')
  )
  assert.ok(
    requests.some(
      (request) => request.method === 'GET' && request.path === '/api/stats/session/demo'
    )
  )
})

test('formatter handles zero totals without NaN', () => {
  assert.equal(formatPercentage(10, 0), '0.0%')
})

async function captureConsole(fn) {
  const originalLog = console.log
  const originalError = console.error
  const lines = []
  console.log = (...args) => lines.push(args.map(String).join(' '))
  console.error = (...args) => lines.push(args.map(String).join(' '))
  try {
    await fn()
  } finally {
    console.log = originalLog
    console.error = originalError
  }
  return lines.join('\n')
}

async function readJson(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  if (chunks.length === 0) return undefined
  const raw = Buffer.concat(chunks).toString('utf8')
  return raw ? JSON.parse(raw) : undefined
}

function json(res, payload) {
  res.setHeader('content-type', 'application/json')
  res.end(JSON.stringify(payload))
}
