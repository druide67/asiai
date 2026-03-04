# Installation

## Homebrew (recommended)

```bash
brew tap druide67/tap
brew install asiai
```

## pip / pipx

```bash
pip install asiai
```

Or with pipx for isolated install:

```bash
pipx install asiai
```

## From source

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e .
```

### Development install

```bash
pip install -e ".[dev]"
```

### With TUI dashboard

```bash
pip install -e ".[tui]"
```

## Verify installation

```bash
asiai --version
asiai detect
```
