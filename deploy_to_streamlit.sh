#!/bin/bash
# Deploy to Streamlit Cloud

set -e

echo "🚀 Preparing for Streamlit deployment..."

# 1. Ensure requirements.txt exists at root
if [ ! -f requirements.txt ]; then
    echo "Creating root requirements.txt..."
    cp stone_age/python/pre_consultant/requirements.txt requirements.txt
fi

# 2. Add .streamlit config (already created)
mkdir -p .streamlit

# 3. Update .gitignore
cat >> .gitignore << 'GITIGNORE'
# Secrets and credentials
credential.txt
.env
secrets.toml
*.db
*.sqlite
logs/
__pycache__/
*.log
alpha_correlation_db.sqlite
test_corr*.db
GITIGNORE

# 4. Commit and push
git add .
git commit -m "Prepare for Streamlit Cloud deployment" || echo "No changes to commit"
git push origin main 2>/dev/null || git push origin $(git branch --show-current)

echo ""
echo "✅ Ready to deploy!"
echo ""
echo "Next steps:"
echo "1. Go to https://share.streamlit.io"
echo "2. Sign in with your GitHub account"
echo "3. Click 'New app'"
echo "4. Select your repository"
echo "5. Configure:"
echo "   - Branch: main (or your current branch)"
echo "   - App file path: stone_age/python/pre_consultant/streamlit_wq_alpha_app.py"
echo "6. Add secrets in the dashboard (Settings → Secrets):"
echo ""
echo "[api_keys]"
echo "openai = \"your-openai-key\""
echo "nvidia = \"your-nvidia-key\""
echo "opencode = \"your-opencode-key\""
echo ""
echo "[wq_credentials]"
echo "email = \"your-email@example.com\""
echo "password = \"your-password\""
echo ""
echo "7. Click 'Deploy!'"
echo ""
echo "🎉 Happy alpha hunting!"
