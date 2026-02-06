/**
 * 测试 pi-ai 调用 OpenAI Codex
 */

import { readFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'
import { getModel, complete, getOAuthApiKey } from '@mariozechner/pi-ai'

const AUTH_FILE = join(homedir(), '.pi', 'agent', 'auth.json')

async function main() {
  // 加载认证信息
  const auth = JSON.parse(readFileSync(AUTH_FILE, 'utf-8'))

  // 获取 API key
  const result = await getOAuthApiKey('openai-codex', auth)
  if (!result) {
    throw new Error('Failed to get API key')
  }

  console.log('API key obtained successfully')
  console.log('Account ID:', auth['openai-codex']?.accountId)

  // 获取模型
  const model = getModel('openai-codex', 'gpt-5.1-codex-mini')
  console.log('\nUsing model:', model.name)
  console.log('API:', model.api)
  console.log('Base URL:', model.baseUrl)

  // 调用 API
  console.log('\nCalling API...')
  const response = await complete(
    model,
    {
      systemPrompt: 'You are a helpful assistant.',
      messages: [{ role: 'user', content: 'Say hello in 3 languages, be brief' }],
    },
    {
      apiKey: result.apiKey,
    }
  )

  // 输出结果
  console.log('\n--- Response ---')
  for (const block of response.content) {
    if (block.type === 'text') {
      console.log(block.text)
    }
  }
  console.log('----------------')
  console.log('Stop reason:', response.stopReason)
  console.log('Usage:', response.usage)
}

main().catch(console.error)
