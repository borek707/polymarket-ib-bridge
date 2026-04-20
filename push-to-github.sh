#!/bin/bash
# Script to push polymarket-ib-bridge repository to GitHub

set -e

REPO_NAME="polymarket-ib-bridge"
REPO_DIR="$HOME/.openclaw/workspace/$REPO_NAME"
cd "$REPO_DIR"

echo "============================================================"
echo "🚀 Pushing $REPO_NAME to GitHub"
echo "============================================================"

# Check if already has remote
if git remote | grep -q "origin"; then
    echo "✓ Remote 'origin' already configured"
    git remote -v
else
    echo ""
    echo "⚠️  No remote configured. You need to:"
    echo ""
    echo "1. Create the repository on GitHub:"
    echo "   - Go to https://github.com/new"
    echo "   - Repository name: $REPO_NAME"
    echo "   - Make it public or private (your choice)"
    echo "   - DO NOT initialize with README (we have one already)"
    echo ""
    echo "2. Then run one of these commands based on your auth method:"
    echo ""
    echo "   Option A - HTTPS (with personal access token):"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
    echo ""
    echo "   Option B - SSH (if you have SSH keys set up):"
    echo "   git remote add origin git@github.com:YOUR_USERNAME/$REPO_NAME.git"
    echo ""
    exit 1
fi

# Check if we're on master and rename to main if needed
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "master" ]; then
    echo ""
    echo "📝 Renaming 'master' branch to 'main'..."
    git branch -m master main
    echo "✓ Branch renamed to 'main'"
fi

# Push to GitHub
echo ""
echo "📤 Pushing to GitHub..."
if git push -u origin main; then
    echo ""
    echo "============================================================"
    echo "✅ SUCCESS! Repository pushed to GitHub"
    echo "============================================================"
    echo ""
    echo "Repository URL:"
    git remote get-url origin | sed 's/\.git$//' | sed 's/git@github.com:/https:\/\/github.com\//'
else
    echo ""
    echo "❌ Push failed. Common issues:"
    echo ""
    echo "1. Not authenticated - run: gh auth login"
    echo "2. Wrong permissions - check GitHub token has 'repo' scope"
    echo "3. Repository doesn't exist on GitHub yet"
    echo ""
    exit 1
fi
