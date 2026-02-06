# browser-use-tools

浏览器自动化工具集，支持 browser-use (Python) 和 browser-use-node (Node.js)。

## 安装步骤

```bash
# 1. 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Node.js 和 uv
brew install node uv

# 3. 安装 GitHub CLI 并登录
brew install gh
gh auth login

# 4. 克隆项目
gh repo clone qbtrade/browser-use-tools
cd browser-use-tools

# 5. 安装 Python 依赖
uv sync

# 6. 安装 Node.js 依赖
npm install

# 7. 安装 Playwright 浏览器
npx playwright install
```
