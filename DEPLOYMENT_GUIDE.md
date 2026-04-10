# Streamlit Cloud Deployment Guide for WorldQuant Alpha System

## 🚀 Quick Deployment Steps

### Option 1: Deploy to Streamlit Cloud (Recommended - Free)

#### Step 1: Prepare Your Repository
Your code is already in a Git repository at `/workspace`. Ensure it's pushed to GitHub:

```bash
cd /workspace
git add .
git commit -m "Ready for Streamlit deployment"
git push origin main  # or your branch name
```

#### Step 2: Connect to Streamlit Cloud

1. **Go to** [share.streamlit.io](https://share.streamlit.io)
2. **Sign in** with your GitHub account
3. **Click** "New app"
4. **Select** your repository from the dropdown
5. **Configure**:
   - **Branch**: `main` (or your working branch)
   - **App file path**: `stone_age/python/pre_consultant/streamlit_wq_alpha_app.py`
   - **Advanced settings** (optional):
     - Python version: 3.12
     - System packages: Leave default

6. **Click** "Deploy!"

#### Step 3: Add Requirements File

Streamlit Cloud automatically reads `requirements.txt`. Ensure yours includes:

```txt
requests>=2.31.0
streamlit>=1.30.0
pandas>=2.0.0
scikit-learn>=1.3.0
cryptography>=41.0.0
openai>=1.0.0
```

Create/update `/workspace/requirements.txt` at the root:

```bash
cd /workspace
cat > requirements.txt << 'EOF'
requests>=2.31.0
streamlit>=1.30.0
pandas>=2.0.0
scikit-learn>=1.3.0
cryptography>=41.0.0
openai>=1.0.0
EOF

git add requirements.txt
git commit -m "Add root requirements.txt for Streamlit Cloud"
git push origin main
```

#### Step 4: Configure Secrets (IMPORTANT!)

For security, **DO NOT** commit credentials. Use Streamlit Secrets:

1. In Streamlit Cloud dashboard, go to your app
2. Click the three dots (⋮) → "Settings"
3. Scroll to "Secrets"
4. Add your secrets in TOML format:

```toml
[api_keys]
openai = "your-openai-key-here"
nvidia = "your-nvidia-key-here"
opencode = "your-opencode-key-here"

[wq_credentials]
email = "your-email@example.com"
password = "your-password-here"
```

5. **Save** secrets

#### Step 5: Update App to Use Secrets

Modify your app to read from `st.secrets`:

```python
# In streamlit_wq_alpha_app.py
if st.secrets.get("api_keys"):
    openai_key = st.secrets.api_keys.openai
    nvidia_key = st.secrets.api_keys.nvidia
    # etc.
```

---

### Option 2: Self-Hosted Deployment (VPS/Cloud)

#### On Ubuntu/Debian Server:

```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv -y

# Create virtual environment
cd /workspace
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r stone_age/python/pre_consultant/requirements.txt

# Run Streamlit
streamlit run stone_age/python/pre_consultant/streamlit_wq_alpha_app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true
```

#### Using Docker:

Create `Dockerfile` at root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "stone_age/python/pre_consultant/streamlit_wq_alpha_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t wq-alpha-app .
docker run -p 8501:8501 wq-alpha-app
```

---

### Option 3: Deploy to Hugging Face Spaces (Free)

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new space"
3. Choose:
   - **Space name**: `wq-alpha-system`
   - **License**: MIT
   - **SDK**: Streamlit
   - **Python version**: 3.12

4. Connect your GitHub repo or upload files
5. Add `requirements.txt` at root
6. Set entry point in `.streamlit/config.toml`:

```toml
[server]
port = 7860
enableCORS = false
```

---

## 🔐 Security Best Practices

### 1. Never Commit Credentials
- Use Streamlit Secrets (`st.secrets`)
- Or environment variables
- Add sensitive files to `.gitignore`:

```gitignore
credential.txt
*.key
.env
secrets.toml
```

### 2. Environment Variables (Alternative)

Set via Streamlit Cloud UI or locally:

```bash
export OPENAI_API_KEY="your-key"
export NVIDIA_API_KEY="your-key"
export WQ_EMAIL="your-email"
export WQ_PASSWORD="your-password"
```

In your app:
```python
import os
openai_key = os.getenv("OPENAI_API_KEY")
```

---

## 📊 Monitoring Your Deployment

### Check App Status
- Streamlit Cloud: Dashboard shows "Running" / "Stopped"
- Logs available in "Logs" tab
- Auto-sleeps after inactivity (free tier)

### Troubleshooting

**App won't start?**
1. Check logs in Streamlit Cloud dashboard
2. Verify `requirements.txt` has all dependencies
3. Ensure entry point file path is correct

**Import errors?**
```python
# Add this at top of your app
import sys
sys.path.insert(0, '/workspace/stone_age/python/pre_consultant')
```

**Database issues?**
- SQLite works on Streamlit Cloud
- For production, consider PostgreSQL addon

---

## 🎯 Post-Deployment Checklist

- [ ] App loads without errors
- [ ] API key input fields work
- [ ] WorldQuant authentication succeeds
- [ ] Alpha generation produces valid expressions
- [ ] Local correlation check runs before submission
- [ ] Simulation settings display correctly
- [ ] Submitted alphas are tracked in database
- [ ] Secrets are properly configured (not hardcoded)

---

## 💡 Pro Tips

1. **Free Tier Limits**: Streamlit Cloud free tier sleeps after 24h inactivity
2. **Custom Domain**: Available on paid plans
3. **Auto-Updates**: App auto-redeploys on git push to connected branch
4. **Collaboration**: Add team members in Streamlit Cloud settings
5. **Performance**: Use caching (`@st.cache_data`) for expensive operations

---

## 🆘 Support Resources

- [Streamlit Documentation](https://docs.streamlit.io)
- [Streamlit Community Forum](https://discuss.streamlit.io)
- [GitHub Issues](https://github.com/streamlit/streamlit/issues)
- [WorldQuant BRAIN API Docs](https://platform.worldquantbrain.com/docs)

---

## 📝 Example: Complete Deployment Script

```bash
#!/bin/bash
# deploy_to_streamlit.sh

set -e

echo "🚀 Preparing for Streamlit deployment..."

# 1. Ensure requirements.txt exists at root
if [ ! -f requirements.txt ]; then
    echo "Creating root requirements.txt..."
    cp stone_age/python/pre_consultant/requirements.txt requirements.txt
fi

# 2. Add .streamlit config
mkdir -p .streamlit
cat > .streamlit/config.toml << 'EOF'
[server]
headless = true
port = 8501
enableCORS = false

[browser]
gatherUsageStats = false
EOF

# 3. Update .gitignore
cat >> .gitignore << 'EOF'
# Secrets and credentials
credential.txt
.env
secrets.toml
*.db
*.sqlite
logs/
__pycache__/
EOF

# 4. Commit and push
git add .
git commit -m "Prepare for Streamlit Cloud deployment" || echo "No changes to commit"
git push origin main

echo "✅ Ready to deploy!"
echo "Next steps:"
echo "1. Go to https://share.streamlit.io"
echo "2. Connect your repository"
echo "3. Set app file path: stone_age/python/pre_consultant/streamlit_wq_alpha_app.py"
echo "4. Add secrets in the dashboard"
echo "5. Deploy!"
```

Make executable and run:
```bash
chmod +x deploy_to_streamlit.sh
./deploy_to_streamlit.sh
```

---

## 🎉 You're Ready!

Your WorldQuant Alpha System is now deployable on Streamlit Cloud with:
- ✅ Local correlation checking (saves API calls)
- ✅ Multi-provider AI support (OpenAI, NVIDIA, OpenCode)
- ✅ Secure credential management
- ✅ Real-time alpha generation and testing
- ✅ Simulation settings tracking

**Happy alpha hunting! 📈**
