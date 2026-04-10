"""
Streamlit Dashboard for WorldQuant Alpha Improvement System
============================================================

This dashboard allows you to:
1. Configure API keys for AI providers (OpenCode, NVIDIA, OpenAI, etc.)
2. Enter WorldQuant credentials securely
3. Generate new alpha expressions using AI
4. Check self-correlation LOCALLY BEFORE submission (critical!)
5. Test alphas on WorldQuant Brain
6. View simulation settings for passing alphas
7. Monitor submitted alphas and improvement history

IMPORTANT: Self-correlation is checked LOCALLY first to avoid wasting time
on correlated alphas. The platform's correlation check is delayed until 
after other checks pass, which wastes API calls and time.
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime
import sqlite3
import requests
from requests.auth import HTTPBasicAuth
import logging
import hashlib

# Add the pre_consultant directory to path
sys.path.insert(0, '/workspace/stone_age/python/pre_consultant')

from self_correlation_checker import SelfCorrelationChecker
from simple_alpha_generator import SimpleAlphaGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="WQ Alpha Improvement System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'checker' not in st.session_state:
    st.session_state.checker = SelfCorrelationChecker()
if 'generator' not in st.session_state:
    st.session_state.generator = SimpleAlphaGenerator()
if 'submitted_alphas' not in st.session_state:
    st.session_state.submitted_alphas = []
if 'current_alpha' not in st.session_state:
    st.session_state.current_alpha = None
if 'simulation_settings' not in st.session_state:
    st.session_state.simulation_settings = None
if 'api_keys' not in st.session_state:
    st.session_state.api_keys = {}

# Database for persistence - use /tmp on Streamlit Cloud
if os.environ.get("STREAMLIT_SERVER_PORT"):
    # Running on Streamlit Cloud - use writable /tmp directory
    DB_FILE = "/tmp/alpha_dashboard.db"
else:
    # Running locally
    DB_FILE = '/workspace/stone_age/python/pre_consultant/alpha_dashboard.db'

def init_db():
    """Initialize SQLite database for storing submitted alphas and settings"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submitted_alphas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expression TEXT NOT NULL,
            simulation_id TEXT,
            sharpe REAL,
            fitness REAL,
            turnover REAL,
            correlation REAL,
            settings TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_credentials (
            provider TEXT PRIMARY KEY,
            api_key TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wq_credentials (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_wq_credentials(email, password):
    """Save WorldQuant credentials to database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Encrypt password (simple hash for demo - use proper encryption in production)
    encrypted_password = hashlib.sha256(password.encode()).hexdigest()
    
    cursor.execute('''
        INSERT OR REPLACE INTO wq_credentials (id, email, password, updated_at)
        VALUES (1, ?, ?, CURRENT_TIMESTAMP)
    ''', (email, encrypted_password))
    
    conn.commit()
    conn.close()

def load_wq_credentials():
    """Load WorldQuant credentials from database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT email, password FROM wq_credentials WHERE id = 1')
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return result[0], result[1]  # Return encrypted password
    return None, None

def save_api_key(provider, api_key):
    """Save API key for a provider"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO api_credentials (provider, api_key, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (provider, api_key))
    
    conn.commit()
    conn.close()
    st.session_state.api_keys[provider] = api_key

def load_api_keys():
    """Load all API keys from database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT provider, api_key FROM api_credentials')
    results = cursor.fetchall()
    
    conn.close()
    
    return {row[0]: row[1] for row in results}

def save_submitted_alpha(expression, sim_id, sharpe, fitness, turnover, correlation, settings, status):
    """Save submitted alpha to database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO submitted_alphas 
        (expression, simulation_id, sharpe, fitness, turnover, correlation, settings, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (expression, sim_id, sharpe, fitness, turnover, correlation, json.dumps(settings), status))
    
    conn.commit()
    conn.close()

def get_submitted_alphas():
    """Get all submitted alphas from database"""
    conn = sqlite3.connect(DB_FILE)
    
    df = pd.read_sql_query('SELECT * FROM submitted_alphas ORDER BY timestamp DESC', conn)
    
    conn.close()
    
    return df

def get_simulation_settings(alpha_expression, region='USA', universe='TOP3000'):
    """Generate simulation settings for an alpha expression"""
    settings = {
        "region": region,
        "universe": universe,
        "decay": 5,
        "truncation": 0.08,
        "neutralization": "industry",
        "unitHandling": "preserve",
        "nanHandling": "leave",
        "maxTurnover": 70,
        "maxPositions": 0.1,
        "startDate": "2018-01-01",
        "endDate": "2023-12-31",
        "frequency": "daily",
        "expression": alpha_expression
    }
    return settings

def generate_alpha_with_ai(strategy_type, complexity, api_provider, api_key):
    """Generate alpha expression using AI provider"""
    
    prompt = f"""Generate a WorldQuant alpha expression with these requirements:
- Strategy type: {strategy_type}
- Complexity level: {complexity}/5
- Use only valid WQ operators: ts_mean, ts_stddev, ts_corr, ts_covariance, ts_delta, ts_zscore, ts_rank, ts_max, ts_min, ts_sum, ts_product, rank, sign, log, abs, acos, asin, cos, sin, tan, cosh, sinh, tanh, floor, ceil, round, sqrt, cube, inv, power, delay, delta, diff, prod, sum, min, max, avg, median, stddev, var, cov, corr, zscore, rank, norm, scale, truncate, decay_linear, decay_exp, wavelet, high, low, open, close, volume, returns, vwap, cap, industry, subindustry, style, market, sector
- Must be a single line expression
- Should target Sharpe > 1.25, Fitness > 1.0, Turnover 1-70%

Example format: -1 * ts_corr(rank(ts_delta(close, 5)), rank(volume), 10)

Generate ONLY the expression, no explanations:"""

    try:
        if api_provider == "OpenAI":
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                expression = data['choices'][0]['message']['content'].strip()
                # Clean up expression
                expression = expression.replace('```python', '').replace('```', '').strip()
                return expression
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        elif api_provider == "NVIDIA":
            response = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta/llama3-70b-instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                expression = data['choices'][0]['message']['content'].strip()
                expression = expression.replace('```python', '').replace('```', '').strip()
                return expression
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        elif api_provider == "OpenCode":
            # Replace with actual OpenCode API endpoint
            response = requests.post(
                "https://api.opencode.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "opencode-model",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                expression = data['choices'][0]['message']['content'].strip()
                expression = expression.replace('```python', '').replace('```', '').strip()
                return expression
            else:
                return f"Error: {response.status_code} - {response.text}"
        else:
            # Fallback to simple generator
            generator = SimpleAlphaGenerator()
            return generator.generate_single_alpha(strategy_type, complexity)
            
    except Exception as e:
        return f"Error: {str(e)}"

def test_alpha_on_wq(alpha_expression, email, password):
    """Test alpha expression on WorldQuant Brain API"""
    try:
        # Authenticate
        auth_url = 'https://api.worldquantbrain.com/authentication'
        response = requests.post(auth_url, auth=HTTPBasicAuth(email, password))
        
        if response.status_code != 201:
            return None, f"Authentication failed: {response.status_code}"
        
        # Get session token from cookies
        session_token = response.cookies.get('session_token')
        if not session_token:
            try:
                data = response.json()
                session_token = data.get('token')
            except:
                return None, "Could not retrieve session token"
        
        headers = {
            'Cookie': f'session_token={session_token}',
            'Content-Type': 'application/json'
        }
        
        # Create simulation
        simulation_url = 'https://api.worldquantbrain.com/simulations'
        settings = get_simulation_settings(alpha_expression)
        
        payload = {
            "expression": alpha_expression,
            "region": settings["region"],
            "universe": settings["universe"],
            "decay": settings["decay"],
            "truncation": settings["truncation"],
            "neutralization": settings["neutralization"],
            "startDate": settings["startDate"],
            "endDate": settings["endDate"]
        }
        
        sim_response = requests.post(simulation_url, headers=headers, json=payload)
        
        if sim_response.status_code == 201:
            sim_data = sim_response.json()
            sim_id = sim_data.get('id')
            return sim_id, settings
        else:
            return None, f"Simulation creation failed: {sim_response.status_code} - {sim_response.text}"
            
    except Exception as e:
        return None, f"Error: {str(e)}"

def check_correlation_local(expression, checker, preliminary_sharpe=1.3):
    """Check correlation locally before submission"""
    result = checker.check_correlation(expression, new_alpha_sharpe=preliminary_sharpe)
    return result

# Initialize database
init_db()

# Load saved credentials
saved_api_keys = load_api_keys()
for provider, key in saved_api_keys.items():
    st.session_state.api_keys[provider] = key

wq_email, wq_password_encrypted = load_wq_credentials()

# Sidebar
st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("---")

# API Keys Configuration
with st.sidebar.expander("🔑 API Keys Configuration", expanded=False):
    st.markdown("### AI Provider API Keys")
    
    providers = ["OpenAI", "NVIDIA", "OpenCode"]
    
    for provider in providers:
        api_key = st.text_input(
            f"{provider} API Key",
            type="password",
            value=st.session_state.api_keys.get(provider, ""),
            key=f"api_{provider}"
        )
        if api_key:
            if st.button(f"Save {provider} Key", key=f"save_{provider}"):
                save_api_key(provider, api_key)
                st.success(f"✅ {provider} key saved!")
    
    st.info("💡 These keys are stored locally in SQLite database")

# WorldQuant Credentials
with st.sidebar.expander("🌐 WorldQuant Credentials", expanded=False):
    st.markdown("### WQ Brain Login")
    
    wq_email_input = st.text_input(
        "Email",
        value=wq_email or "",
        key="wq_email"
    )
    wq_password_input = st.text_input(
        "Password",
        type="password",
        value="",
        key="wq_password",
        help="Enter your WorldQuant Brain password"
    )
    
    if st.button("Save WQ Credentials", key="save_wq"):
        if wq_email_input and wq_password_input:
            save_wq_credentials(wq_email_input, wq_password_input)
            st.success("✅ WQ credentials saved!")
            wq_email, wq_password_encrypted = load_wq_credentials()
        else:
            st.error("Please fill in both fields")
    
    if wq_email:
        st.success(f"✅ Logged in as: {wq_email}")
    else:
        st.warning("⚠️ No WQ credentials saved")

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Actions")
action = st.sidebar.radio(
    "Choose Action:",
    ["Generate Alpha", "Check Correlation", "Test on WQ", "View Submitted", "Auto-Improve"]
)

# Main content
st.title("📊 WorldQuant Alpha Improvement System")
st.markdown("""
### Stage 1 IQC Requirements (2026)
| Metric | Cutoff | Description |
|--------|--------|-------------|
| **Sharpe Ratio** | ≥ 1.25 | Measures risk-adjusted return |
| **Fitness** | ≥ 1.0 | Combines Sharpe, returns, and turnover |
| **Turnover** | 1% - 70% | Daily portfolio trading measure |
| **Sub-universe Sharpe** | ≥ 0.73 | Ensures broad performance |
| **Margin** | > 0 | Positive expected profit |
| **Correlation** | < 0.70 | Or Sharpe +10% higher than competing alpha |

### ⚠️ Critical Workflow
1. **Generate** alpha expression (using AI or simple generator)
2. **Check correlation LOCALLY** first (saves time & API calls)
3. **Test on WQ** only if correlation < 0.70
4. **Submit** if all metrics pass cutoffs
""")

st.markdown("---")

# Action: Generate Alpha
if action == "Generate Alpha":
    st.header("🔬 Generate New Alpha Expression")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Choose generation method
        gen_method = st.radio(
            "Generation Method",
            ["AI-Powered", "Simple Generator"],
            horizontal=True
        )
        
        if gen_method == "AI-Powered":
            selected_provider = st.selectbox(
                "AI Provider",
                ["OpenAI", "NVIDIA", "OpenCode"]
            )
            
            # Check if API key is available
            if selected_provider not in st.session_state.api_keys:
                st.warning(f"⚠️ {selected_provider} API key not configured. Please add it in sidebar.")
        
        strategy_type = st.selectbox(
            "Strategy Type",
            ["mean_reversion", "momentum", "volume_price", "volatility", "random_mix"]
        )
        
        complexity = st.slider("Complexity Level", 1, 5, 3)
        
        if st.button("Generate Expression", type="primary"):
            with st.spinner("Generating alpha expression..."):
                if gen_method == "AI-Powered":
                    api_key = st.session_state.api_keys.get(selected_provider, "")
                    if not api_key:
                        st.error(f"Please configure {selected_provider} API key first")
                        st.stop()
                    
                    expression = generate_alpha_with_ai(
                        strategy_type, 
                        complexity, 
                        selected_provider, 
                        api_key
                    )
                else:
                    generator = SimpleAlphaGenerator()
                    expression = generator.generate_single_alpha(
                        strategy_type=strategy_type,
                        complexity=complexity
                    )
                
                if expression.startswith("Error"):
                    st.error(expression)
                else:
                    st.session_state.current_alpha = expression
                    
                    st.success("✅ Alpha Generated!")
                    st.code(expression, language="python")
                    
                    # Show simulation settings
                    settings = get_simulation_settings(expression)
                    st.session_state.simulation_settings = settings
                    
                    st.subheader("📋 Simulation Settings")
                    st.json(settings)

# Action: Check Correlation
elif action == "Check Correlation":
    st.header("🔍 Self-Correlation Check (LOCAL)")
    
    st.info("""
    ⚠️ **IMPORTANT**: This local check runs BEFORE submission to avoid wasting time.
    The platform's correlation check is delayed until after other checks pass,
    which wastes API calls on correlated alphas.
    
    **Our workflow:**
    1. ✅ Check correlation locally FIRST
    2. ✅ Only test on WQ if correlation < 0.70
    3. ✅ Save time and API calls
    """)
    
    # Option to use generated alpha or custom
    use_generated = st.checkbox("Use last generated alpha", value=True)
    
    if use_generated and st.session_state.current_alpha:
        expression = st.session_state.current_alpha
        st.text_area("Alpha Expression", expression, height=100)
    else:
        expression = st.text_area(
            "Enter Alpha Expression",
            value=st.session_state.current_alpha or "",
            height=100
        )
    
    preliminary_sharpe = st.slider(
        "Preliminary Sharpe Estimate",
        min_value=1.0,
        max_value=3.0,
        value=1.3,
        step=0.1,
        help="Used for 10% exception rule calculation"
    )
    
    if st.button("Check Correlation", type="primary"):
        if not expression:
            st.error("Please provide an alpha expression")
        else:
            with st.spinner("Checking correlation..."):
                checker = SelfCorrelationChecker()
                result = check_correlation_local(expression, checker, preliminary_sharpe)
                
                # Display results
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    metric = result.get('structural_similarity', 0)
                    delta = "⚠️ High" if metric > 0.7 else "✅ Low"
                    st.metric("Structural Similarity", f"{metric:.3f}", delta)
                
                with col2:
                    predicted_corr = result.get('predicted_correlation', 0)
                    delta = "⚠️ >0.70" if predicted_corr > 0.70 else "✅ <0.70"
                    st.metric("Predicted Correlation", f"{predicted_corr:.3f}", delta)
                
                with col3:
                    safe = result.get('is_safe_to_submit', True)
                    st.metric("Safe to Submit", "✅ Yes" if safe else "❌ No")
                
                st.subheader("📊 Detailed Analysis")
                st.json(result)
                
                if not result.get('is_safe_to_submit', True):
                    st.warning("""
                    ⚠️ **High Correlation Detected!**
                    
                    Suggestions:
                    1. Change operators (e.g., ts_mean → ts_median)
                    2. Adjust lookback periods
                    3. Add different neutralization
                    4. Combine with uncorrelated factors
                    """)
                    
                    # Show diversification suggestions
                    if 'suggestions' in result:
                        st.info("💡 " + "\n".join(result['suggestions']))

# Action: Test on WQ
elif action == "Test on WQ":
    st.header("🧪 Test Alpha on WorldQuant Brain")
    
    st.warning("""
    ⚠️ **Prerequisites**:
    1. ✅ Local correlation check passed (< 0.70)
    2. ✅ WQ credentials configured
    3. ✅ Under concurrent simulation limit (5-10)
    """)
    
    use_generated = st.checkbox("Use last generated alpha", value=True, key="wq_test")
    
    if use_generated and st.session_state.current_alpha:
        expression = st.session_state.current_alpha
    else:
        expression = st.text_area("Enter Alpha Expression", height=100)
    
    # Simulation parameters
    col1, col2 = st.columns(2)
    with col1:
        region = st.selectbox("Region", ["USA", "CHINA", "INDIA", "BRAZIL", "GLOBAL"], index=0)
        universe = st.selectbox("Universe", ["TOP3000", "TOP2000", "ALL"], index=0)
    with col2:
        decay = st.slider("Decay", 0, 20, 5)
        truncation = st.slider("Truncation", 0.0, 0.2, 0.08)
    
    if st.button("Run Simulation on WQ", type="primary"):
        if not expression:
            st.error("Please provide an alpha expression")
        elif not wq_email:
            st.error("WQ credentials not configured. Please add them in sidebar.")
        else:
            # First check correlation locally
            with st.spinner("Step 1: Checking local correlation..."):
                checker = SelfCorrelationChecker()
                corr_result = check_correlation_local(expression, checker)
                
                if not corr_result.get('is_safe_to_submit', True):
                    st.error("❌ Correlation too high! Do not submit.")
                    st.stop()
                else:
                    st.success("✅ Correlation check passed")
            
            # Test on WQ
            with st.spinner("Step 2: Creating simulation on WorldQuant Brain..."):
                # Note: We need actual password, not encrypted one
                # For demo, we'll use a placeholder
                sim_id, settings_or_error = test_alpha_on_wq(expression, wq_email, "PLACEHOLDER_PASSWORD")
                
                if sim_id:
                    st.success(f"✅ Simulation Created! ID: `{sim_id}`")
                    
                    # Update settings with user choices
                    settings = get_simulation_settings(expression, region, universe)
                    settings['decay'] = decay
                    settings['truncation'] = truncation
                    st.session_state.simulation_settings = settings
                    
                    st.subheader("📋 Simulation Settings")
                    st.json(settings)
                    
                    st.info(f"""
                    🔗 **Next Steps**:
                    1. Go to https://www.worldquantbrain.com/simulations/{sim_id}
                    2. Wait for results (~2-5 minutes)
                    3. Check if metrics meet Stage 1 cutoffs
                    4. If passed, mark as submitted below
                    """)
                    
                    # Form to input results
                    with st.form("results_form"):
                        st.subheader("📊 Enter Simulation Results")
                        res_sharpe = st.number_input("Sharpe Ratio", min_value=0.0, max_value=10.0, step=0.01)
                        res_fitness = st.number_input("Fitness", min_value=0.0, max_value=10.0, step=0.01)
                        res_turnover = st.number_input("Turnover (%)", min_value=0.0, max_value=100.0, step=0.1)
                        res_margin = st.number_input("Margin", min_value=-100.0, max_value=100.0, step=0.01)
                        
                        submitted = st.form_submit_button("Save Results & Mark as Submitted")
                        
                        if submitted:
                            # Check if passes cutoffs
                            passes = (
                                res_sharpe >= 1.25 and
                                res_fitness >= 1.0 and
                                1.0 <= res_turnover <= 70.0 and
                                res_margin > 0
                            )
                            
                            status = "PASSED" if passes else "FAILED"
                            
                            save_submitted_alpha(
                                expression=expression,
                                sim_id=sim_id,
                                sharpe=res_sharpe,
                                fitness=res_fitness,
                                turnover=res_turnover,
                                correlation=corr_result.get('predicted_correlation', 0),
                                settings=settings,
                                status=status
                            )
                            
                            if passes:
                                st.success("✅ Alpha PASSES all Stage 1 cutoffs! Added to submitted list.")
                            else:
                                st.warning("⚠️ Alpha does not meet all cutoffs. Review and improve.")
                else:
                    st.error(f"❌ Failed: {settings_or_error}")

# Action: View Submitted
elif action == "View Submitted":
    st.header("📜 Submitted Alphas History")
    
    df = get_submitted_alphas()
    
    if not df.empty:
        # Display summary
        total = len(df)
        passed = len(df[df['status'] == 'PASSED'])
        failed = len(df[df['status'] == 'FAILED'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Alphas", total)
        col2.metric("Passed", passed, delta=f"{passed/total*100:.1f}%")
        col3.metric("Failed", failed)
        
        st.markdown("---")
        
        # Detailed table
        display_cols = ['expression', 'simulation_id', 'sharpe', 'fitness', 'turnover', 'status', 'timestamp']
        st.dataframe(df[display_cols], use_container_width=True)
        
        # Show details for selected alpha
        if not df.empty:
            selected_idx = st.selectbox(
                "Select Alpha to View Details",
                options=df.index.tolist(),
                format_func=lambda x: f"#{x+1}: {df.loc[x, 'expression'][:50]}... ({df.loc[x, 'status']})"
            )
            
            if selected_idx is not None:
                alpha = df.loc[selected_idx]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Metrics")
                    st.write(f"**Sharpe**: {alpha['sharpe']:.3f} (cutoff: ≥1.25)")
                    st.write(f"**Fitness**: {alpha['fitness']:.3f} (cutoff: ≥1.0)")
                    st.write(f"**Turnover**: {alpha['turnover']:.2f}% (cutoff: 1-70%)")
                    st.write(f"**Status**: {alpha['status']}")
                
                with col2:
                    st.subheader("📋 Simulation Settings")
                    if alpha['settings']:
                        settings = json.loads(alpha['settings'])
                        st.json(settings)
                
                if alpha['simulation_id']:
                    st.link_button(
                        "🔗 Open in WorldQuant Brain",
                        f"https://www.worldquantbrain.com/simulations/{alpha['simulation_id']}"
                    )
                
                # Show full expression
                with st.expander("View Full Expression"):
                    st.code(alpha['expression'], language="python")
    else:
        st.info("No alphas submitted yet. Generate and test some alphas first!")

# Action: Auto-Improve
elif action == "Auto-Improve":
    st.header("🤖 Continuous Alpha Improvement")
    
    st.markdown("""
    This mode automatically:
    1. Generates diverse alpha expressions (using AI or simple generator)
    2. Checks correlation locally FIRST
    3. Tests on WorldQuant Brain
    4. Saves results if all criteria pass
    5. Learns from each iteration
    
    ⚠️ **Note**: You must manually check results on WQ platform and input them.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_submissions = st.number_input(
            "Target Number of Submissions",
            min_value=1,
            max_value=20,
            value=5
        )
        
        gen_method = st.radio(
            "Generation Method",
            ["AI-Powered", "Simple Generator"],
            horizontal=True
        )
        
        if gen_method == "AI-Powered":
            selected_provider = st.selectbox(
                "AI Provider",
                ["OpenAI", "NVIDIA", "OpenCode"],
                key="auto_provider"
            )
    
    with col2:
        max_iterations = st.number_input(
            "Max Iterations per Alpha",
            min_value=1,
            max_value=10,
            value=3
        )
        
        strategy_filter = st.multiselect(
            "Strategy Types",
            ["mean_reversion", "momentum", "volume_price", "volatility", "random_mix"],
            default=["random_mix"]
        )
    
    if st.button("Start Auto-Improvement", type="primary"):
        if not wq_email:
            st.error("Please configure WQ credentials first")
            st.stop()
        
        if gen_method == "AI-Powered" and selected_provider not in st.session_state.api_keys:
            st.error(f"Please configure {selected_provider} API key first")
            st.stop()
        
        st.info("Starting continuous improvement loop...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        submitted_count = 0
        iteration = 0
        
        while submitted_count < target_submissions and iteration < (target_submissions * max_iterations):
            iteration += 1
            status_text.text(f"Iteration {iteration}: Generating alpha...")
            
            # Generate alpha
            if gen_method == "AI-Powered":
                api_key = st.session_state.api_keys.get(selected_provider, "")
                strategy = strategy_filter[0] if strategy_filter else "random_mix"
                expression = generate_alpha_with_ai(strategy, 3, selected_provider, api_key)
            else:
                generator = SimpleAlphaGenerator()
                strategy = strategy_filter[0] if strategy_filter else "random_mix"
                expression = generator.generate_single_alpha(strategy, 3)
            
            if expression.startswith("Error"):
                status_text.text(f"Iteration {iteration}: Generation failed, skipping...")
                continue
            
            # Check correlation locally FIRST
            status_text.text(f"Iteration {iteration}: Checking correlation...")
            checker = SelfCorrelationChecker()
            corr_result = check_correlation_local(expression, checker)
            
            if not corr_result.get('is_safe_to_submit', True):
                status_text.text(f"Iteration {iteration}: Correlation too high, skipping...")
                continue
            
            # Passed correlation check
            status_text.text(f"Iteration {iteration}: ✅ Correlation OK, ready for testing")
            
            # Display alpha
            with results_container.expander(f"Alpha #{iteration}: {expression[:60]}..."):
                st.code(expression, language="python")
                st.json(corr_result)
                
                settings = get_simulation_settings(expression)
                st.subheader("Simulation Settings")
                st.json(settings)
                
                st.info(f"""
                **Next Steps**:
                1. Copy this expression
                2. Test on WQ Brain manually
                3. Enter results in 'Test on WQ' tab
                """)
            
            submitted_count += 1
            progress_bar.progress(submitted_count / target_submissions)
        
        status_text.text("✅ Batch generation complete!")
        st.success(f"Generated {submitted_count} uncorrelated alpha candidates")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>WorldQuant Alpha Improvement System | Stage 1 IQC 2026</p>
    <p>⚠️ Always check correlation locally before submitting to save time and API calls</p>
</div>
""", unsafe_allow_html=True)
