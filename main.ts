/**
 * Browser-Use Demo with pi-ai OAuth
 *
 * 使用 pi-ai 通过 OpenAI Codex OAuth 认证，
 * 然后将获取的 API key 传递给 browser-use-node 进行浏览器自动化
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'fs'
import { homedir } from 'os'
import { join, dirname } from 'path'
import { ChatOpenAI } from '@langchain/openai'
import { Agent, Browser, Controller } from 'browser-use-node'
import { getOAuthApiKey, loginOpenAICodex } from '@mariozechner/pi-ai'

// 认证文件路径 - 使用 pi-ai 默认位置
const AUTH_FILE = join(homedir(), '.pi', 'agent', 'auth.json')

/**
 * 加载或创建认证信息
 */
async function getApiKey(): Promise<string> {
  let auth: Record<string, any> = {}

  // 尝试从文件加载已有认证
  if (existsSync(AUTH_FILE)) {
    try {
      auth = JSON.parse(readFileSync(AUTH_FILE, 'utf-8'))
    } catch (e) {
      console.log('Failed to parse auth.json, will re-authenticate')
    }
  }

  // 检查是否已有有效的 OAuth 凭证
  if (auth['openai-codex']) {
    const result = await getOAuthApiKey('openai-codex', auth)
    if (result) {
      // 保存刷新后的凭证
      auth['openai-codex'] = { type: 'oauth', ...result.newCredentials }
      mkdirSync(dirname(AUTH_FILE), { recursive: true })
      writeFileSync(AUTH_FILE, JSON.stringify(auth, null, 2))
      console.log('Using existing OAuth token (refreshed if needed)')
      return result.apiKey
    }
  }

  // 需要重新登录
  console.log('No valid OAuth token found. Starting login flow...')
  console.log('Please follow the instructions to authenticate with OpenAI Codex.')

  const credentials = await loginOpenAICodex({
    onAuth: (url, instructions) => {
      console.log(`\nOpen this URL to authenticate:\n${url}`)
      if (instructions) {
        console.log(`\n${instructions}`)
      }
    },
    onPrompt: async (prompt) => {
      // 简单的交互式提示
      process.stdout.write(`\n${prompt.message}: `)
      return new Promise((resolve) => {
        process.stdin.once('data', (data) => {
          resolve(data.toString().trim())
        })
      })
    },
    onProgress: (message) => {
      console.log(message)
    },
  })

  // 保存凭证
  auth['openai-codex'] = { type: 'oauth', ...credentials }
  mkdirSync(dirname(AUTH_FILE), { recursive: true })
  writeFileSync(AUTH_FILE, JSON.stringify(auth, null, 2))
  console.log(`OAuth credentials saved to ${AUTH_FILE}`)

  // 获取 API key
  const result = await getOAuthApiKey('openai-codex', auth)
  if (!result) {
    throw new Error('Failed to get API key after login')
  }

  return result.apiKey
}

/**
 * 主函数
 */
async function main() {
  console.log('=== Browser-Use Demo with pi-ai OAuth ===\n')

  // 获取 API key
  const apiKey = await getApiKey()
  console.log('API key obtained successfully\n')

  // 创建 LangChain OpenAI 实例
  // OpenAI Codex 使用特殊的 base URL
  const llm = new ChatOpenAI({
    openAIApiKey: apiKey,
    modelName: 'gpt-4o', // 或其他支持的模型
    configuration: {
      baseURL: 'https://api.openai.com/v1', // 标准 OpenAI API
    },
  })

  // 创建浏览器实例
  const browser = new Browser({
    headless: false, // 设置为 false 以便观察自动化过程
  })

  // 先创建 browserContext，避免 Agent 内部的 bug
  const browserContext = await browser.newContext()

  // 创建控制器
  const controller = new Controller()

  // 创建 Agent - 传入 browserContext 而不是 browser
  // 这样 Agent 不会尝试自己管理 browserContext 的生命周期
  const agent = new Agent({
    task: 'Go to Google and search for "browser automation with AI"',
    llm,
    browserContext, // 使用已创建的 browserContext
    controller,
  })

  console.log('Starting browser automation task...\n')

  // 运行任务
  try {
    await agent.run()
    console.log('\nTask completed!')
  } catch (error) {
    console.error('Error during execution:', error)
  } finally {
    // 关闭浏览器上下文和浏览器
    try {
      await browserContext.close()
    } catch (e) {
      // 忽略关闭错误
    }
    try {
      await browser.close()
    } catch (e) {
      // 忽略关闭错误
    }
  }
}

// 运行主函数
main().catch(console.error)
