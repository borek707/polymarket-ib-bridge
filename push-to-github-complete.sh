#!/bin/bash
# Complete script to push polymarket-ib-bridge to GitHub
# Run this after setting up GitHub authentication

set -e

REPO_NAME="polymarket-ib-bridge"
REPO_DIR="$HOME/.openclaw/workspace/$REPO_NAME"
cd "$REPO_DIR"

echo "============================================================"
echo "🚀 Setting up GitHub repository for $REPO_NAME"
echo "============================================================"

# Check if gh is authenticated
if ! gh auth status &>/dev/null; then
    echo ""
    echo "❌ Not authenticated with GitHub."
    echo ""
    echo "To authenticate, run one of these:"
    echo ""
    echo "Option 1 - Interactive (opens browser):"
    echo "  gh auth login"
    echo ""
    echo "Option 2 - Using Personal Access Token:"
    echo "  export GH_TOKEN='your_github_token_here'"
    echo "  gh auth status"
    echo ""
    echo "To create a token: https://github.com/settings/tokens"
    echo "Required scopes: repo (full control of private repositories)"
    echo ""
    exit 1
fi

echo "✅ Authenticated with GitHub"
echo ""

# Check if repo already exists on GitHub
if gh repo view "$REPO_NAME" &>/dev/null; then
    echo "✓ Repository '$REPO_NAME' already exists on GitHub"
else
    echo "📦 Creating GitHub repository..."
    gh repo create "$REPO_NAME" --public --source=. --push --description="Arbitrage prediction markets: Track whales on Polymarket, execute on Interactive Brokers" --homepage=""
    echo "✅ Repository created and pushed!"
    exit 0
fi

# If repo exists but no remote configured, add it
if ! git remote | grep -q "origin"; then
    echo "🔗 Adding remote..."
    USER=$(gh api user -q '.login')
    git remote add origin "https://github.com/$USER/$REPO_NAME.git"
fi

# Check current branch and rename to main if needed
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "master" ]; then
    echo "📝 Renaming 'master' to 'main'..."
    git branch -m master main
fi

# Push to GitHub
echo ""
echo "📤 Pushing code to GitHub..."
git push -u origin main

echo ""
echo "============================================================"
echo "✅ SUCCESS! Repository pushed to GitHub"
echo "============================================================"
echo ""
REPO_URL=$(gh repo view "$REPO_NAME" --json url -q '.url')
echo "Repository URL: $REPO_URL"
echo ""
