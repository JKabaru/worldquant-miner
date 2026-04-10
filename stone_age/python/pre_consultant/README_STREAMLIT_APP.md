# 📊 WorldQuant Alpha Improvement System - Streamlit App

## 🚀 Quick Start

The Streamlit app is now running at: **http://localhost:8502**

### Access the Dashboard
- **Local**: http://localhost:8502
- **Network**: http://21.0.7.31:8502
- **External**: http://47.236.195.196:8502

---

## ✨ Key Features

### 1. 🔑 AI Provider Integration
Support for multiple AI providers (no Ollama):
- **OpenAI** - GPT-3.5/4 models
- **NVIDIA** - Llama3-70B and other models
- **OpenCode** - Open source code models

Users can enter their API keys securely in the sidebar. Keys are stored in SQLite database.

### 2. 🌐 WorldQuant Credentials
- Enter your WQ Brain email and password in the sidebar
- Credentials are encrypted and stored locally
- Different users can use different login details

### 3. 🔍 Local Self-Correlation Check (CRITICAL!)
**This runs BEFORE submission to avoid wasting time:**
- Checks expression structural similarity
- Predicts correlation using pattern matching
- Implements 10% Sharpe improvement exception rule
- Provides diversification suggestions if correlation > 0.70

⚠️ **Important**: The platform's correlation check is delayed until after other checks pass. Our local check prevents wasting API calls on correlated alphas.

### 4. 📋 Simulation Settings
When an alpha passes all checks, you get:
- Complete simulation configuration
- Region, universe, decay, truncation settings
- Neutralization and handling parameters
- Ready-to-use settings for manual testing

### 5. 📊 Workflow

```
1. Generate Alpha (AI or Simple Generator)
   ↓
2. Check Correlation LOCALLY ✅
   ↓ (if correlation < 0.70)
3. Test on WorldQuant Brain
   ↓
4. Enter Results Manually
   ↓
5. Save to Database (with simulation settings)
   ↓
6. View History & Track Progress
```

---

## 🎯 Stage 1 IQC Requirements (2026)

| Metric | Cutoff | Description |
|--------|--------|-------------|
| **Sharpe Ratio** | ≥ 1.25 | Risk-adjusted return |
| **Fitness** | ≥ 1.0 | Sharpe + returns + turnover |
| **Turnover** | 1% - 70% | Daily portfolio trading |
| **Sub-universe Sharpe** | ≥ 0.73 | Broad performance |
| **Margin** | > 0 | Positive expected profit |
| **Correlation** | < 0.70 | Or Sharpe +10% higher |

---

## 🛠️ How to Use

### Step 1: Configure API Keys
1. Open the sidebar (☰ icon)
2. Expand "🔑 API Keys Configuration"
3. Enter your API key for your preferred provider
4. Click "Save"

### Step 2: Add WorldQuant Credentials
1. In sidebar, expand "🌐 WorldQuant Credentials"
2. Enter your WQ Brain email and password
3. Click "Save WQ Credentials"

### Step 3: Generate Alpha
1. Select "Generate Alpha" from Quick Actions
2. Choose generation method (AI-Powered or Simple)
3. Select strategy type and complexity
4. Click "Generate Expression"
5. View the expression and simulation settings

### Step 4: Check Correlation (LOCAL)
1. Select "Check Correlation" from Quick Actions
2. Use generated alpha or enter custom expression
3. Set preliminary Sharpe estimate
4. Click "Check Correlation"
5. Review results:
   - ✅ Safe to submit if correlation < 0.70
   - ❌ High correlation → modify expression

### Step 5: Test on WorldQuant
1. Select "Test on WQ" from Quick Actions
2. Ensure correlation check passed
3. Configure simulation parameters (region, universe, etc.)
4. Click "Run Simulation on WQ"
5. Get simulation ID and settings
6. **Manually check results** on WQ Brain website
7. Enter results in the form
8. Save to database

### Step 6: View Submitted Alphas
1. Select "View Submitted" from Quick Actions
2. See all submitted alphas with metrics
3. Filter by status (PASSED/FAILED)
4. View detailed simulation settings
5. Click link to open in WQ Brain

### Step 7: Auto-Improve (Optional)
1. Select "Auto-Improve" from Quick Actions
2. Set target submissions and max iterations
3. Choose generation method and strategies
4. Click "Start Auto-Improvement"
5. System generates uncorrelated candidates
6. Manually test each on WQ Brain

---

## 💾 Data Storage

All data is stored locally in SQLite database:
- `alpha_dashboard.db` - Submitted alphas, credentials, API keys
- Encrypted passwords (SHA-256 hash)
- Persistent across sessions

---

## 🔧 Technical Details

### Files Created
- `streamlit_wq_alpha_app.py` - Main Streamlit application
- `requirements.txt` - Python dependencies
- `alpha_dashboard.db` - SQLite database (created on first run)

### Dependencies
```
requests>=2.31.0
streamlit>=1.30.0
pandas>=2.0.0
scikit-learn>=1.3.0
```

### Running the App
```bash
cd /workspace/stone_age/python/pre_consultant
streamlit run streamlit_wq_alpha_app.py --server.port 8502
```

---

## ⚠️ Important Notes

1. **Local Correlation Check First**: Always check correlation locally before submitting to WQ. This saves time and API calls.

2. **Manual Results Entry**: Due to API limitations, you must manually check simulation results on the WQ Brain website and enter them in the app.

3. **Password Security**: Passwords are hashed before storage. For production use, consider stronger encryption.

4. **Concurrent Simulations**: WQ limits concurrent simulations to 5-10. Monitor your active runs.

5. **API Keys**: API keys for AI providers are stored locally. Keep them secure.

---

## 🎯 Next Steps

1. **Access the dashboard** at http://localhost:8502
2. **Configure your credentials** (AI provider + WQ)
3. **Generate your first alpha**
4. **Check correlation locally**
5. **Test on WQ Brain**
6. **Submit passing alphas**
7. **Track progress** in the dashboard

Good luck with Stage 1 IQC! 🚀
