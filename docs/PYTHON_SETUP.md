# Python Environment Setup

This project uses Python 3.11 with pyenv for version management.

## Why Python 3.11.13?

- **Google ADK Requirements**: Compatible with Google ADK 1.19.0+
- **Type Hints**: Better type annotation support for code quality
- **Performance**: ~25% faster than Python 3.10
- **Security**: Latest patch release with security fixes
- **Stability**: Mature and stable release with excellent library support

## Installing pyenv

### macOS

```bash
# Using Homebrew
brew install pyenv

# Add to shell configuration
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# Reload shell
source ~/.zshrc
```

### Linux (Ubuntu/Debian)

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev

# Install pyenv
curl https://pyenv.run | bash

# Add to shell configuration
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

### Windows (WSL)

Use the Linux instructions above in WSL.

For native Windows, consider using:
- **pyenv-win**: https://github.com/pyenv-win/pyenv-win
- **Anaconda**: https://www.anaconda.com/download

## Installing Python 3.11.13

```bash
# Install Python 3.11.13
pyenv install 3.11.13

# Verify installation
pyenv versions

# Expected output:
#   system
# * 3.11.13 (set by /path/to/customer-support-mas/.python-version)
```

## Project Setup

The project includes a `.python-version` file that automatically activates Python 3.11.13 when you enter the directory.

```bash
# Clone repository
git clone https://github.com/your-repo/customer-support-mas.git
cd customer-support-mas

# Verify Python version (should auto-switch to 3.11.13)
python --version
# Output: Python 3.11.13

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

## Virtual Environment Management

### Create Virtual Environment

```bash
# Using venv (recommended)
python -m venv .venv

# Using virtualenv
pip install virtualenv
virtualenv .venv
```

### Activate Virtual Environment

```bash
# macOS/Linux
source .venv/bin/activate

# Windows CMD
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### Deactivate Virtual Environment

```bash
deactivate
```

### Verify Virtual Environment

```bash
# Check Python version
python --version  # Should show 3.11.13

# Check pip location
which pip  # Should point to .venv/bin/pip

# List installed packages
pip list
```

## Dependency Management

### Install Dependencies

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Install specific package
pip install google-adk>=1.19.0

# Install with extras
pip install google-cloud-aiplatform[adk,agent_engines]
```

### Update Dependencies

```bash
# Update all packages
pip install --upgrade -r requirements.txt

# Update specific package
pip install --upgrade google-adk
```

### Freeze Dependencies

```bash
# Generate requirements.txt from current environment
pip freeze > requirements.txt

# Generate with pipreqs (only imports used in code)
pip install pipreqs
pipreqs . --force
```

## Troubleshooting

### pyenv: command not found

**Problem:**
```bash
$ pyenv
-bash: pyenv: command not found
```

**Solution:**
Add pyenv to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Reload shell
source ~/.bashrc  # or source ~/.zshrc
```

### Python version not switching

**Problem:**
```bash
$ python --version
Python 3.9.0  # Expected 3.11.13
```

**Solution:**

```bash
# Check pyenv versions
pyenv versions

# Manually set local version
pyenv local 3.11.13

# Verify .python-version file exists
cat .python-version  # Should show 3.11.13
```

### Module not found after installation

**Problem:**
```bash
$ python
>>> import google.adk
ModuleNotFoundError: No module named 'google.adk'
```

**Solution:**

1. Verify virtual environment is activated:
   ```bash
   which python  # Should point to .venv/bin/python
   ```

2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Check for typos in module name:
   ```bash
   pip list | grep adk
   ```

### SSL certificate errors during pyenv install

**Problem:**
```bash
$ pyenv install 3.11.0
ERROR: The Python ssl extension was not compiled. Missing the OpenSSL lib?
```

**Solution (macOS):**
```bash
# Install openssl via Homebrew
brew install openssl

# Set flags for pyenv
CFLAGS="-I$(brew --prefix openssl)/include" \
LDFLAGS="-L$(brew --prefix openssl)/lib" \
pyenv install 3.11.13
```

**Solution (Linux):**
```bash
# Install openssl development packages
sudo apt-get install libssl-dev

# Retry installation
pyenv install 3.11.13
```

## IDE Configuration

### Visual Studio Code

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true
}
```

### PyCharm

1. Go to **Settings → Project → Python Interpreter**
2. Click **Add Interpreter → Existing Environment**
3. Select `.venv/bin/python`
4. Click **OK**

## Alternative: Using Docker

If you prefer not to use pyenv locally:

```bash
# Use Docker container with Python 3.11
docker run -it -v $(pwd):/app python:3.11 bash
cd /app
pip install -r requirements.txt
```

## Best Practices

1. **Always use virtual environments** - Isolate project dependencies
2. **Pin Python version** - Use `.python-version` file (already configured)
3. **Keep dependencies updated** - Regular `pip install --upgrade`
4. **Use requirements.txt** - Track all dependencies
5. **Don't commit .venv/** - Already in `.gitignore`

## See Also

- [pyenv Documentation](https://github.com/pyenv/pyenv)
- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)
- [pip User Guide](https://pip.pypa.io/en/stable/user_guide/)
- [GETTING_STARTED.md](../GETTING_STARTED.md) - Complete setup checklist
