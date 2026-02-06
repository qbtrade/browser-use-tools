# browser-use-tools

浏览器自动化工具集，支持 browser-use (Python) 和 browser-use-node (Node.js)。

## 安装步骤

```bash
# 1. 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Node.js 和 uv
brew install node uv

# 3. 克隆项目
git clone <repo-url>
cd browser-use-tools

# 4. 安装 Python 依赖
uv sync

# 5. 安装 Node.js 依赖
npm install

# 6. 安装 Playwright 浏览器
npx playwright install
```
