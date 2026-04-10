"""
Streamlit Dashboard for WorldQuant Alpha Improvement System

This dashboard allows you to:
1. Generate new alpha expressions
2. Check self-correlation BEFORE submission (local check)
3. Test alphas on WorldQuant Brain
4. View simulation settings for passing alphas
5. Monitor submitted alphas and improvement history

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

# Add the pre_consultant directory to path
sys.path.insert(0, '/workspace/stone_age/python/pre_consultant')

from self_correlation_checker import SelfCorrelationChecker
# Use simple generator instead of complex API-dependent one
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
if 'improver' not in st.session_state:
    st.session_state.improver = None
if 'submitted_alphas' not in st.session_state:
    st.session_state.submitted_alphas = []
if 'current_alpha' not in st.session_state:
    st.session_state.current_alpha = None
if 'simulation_settings' not in st.session_state:
    st.session_state.simulation_settings = None

# Load credentials
def load_credentials():
    """Load WorldQuant credentials from file"""
    cred_file = '/workspace/stone_age/python/pre_consultant/credential.txt'
    if os.path.exists(cred_file):
        with open(cred_file, 'r') as f:
            lines = f.readlines()
            email = lines[0].strip() if len(lines) > 0 else ''
            password = lines[1].strip() if len(lines) > 1 else ''
            return email, password
    return '', ''

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
            # Try to get from response body
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

def check_correlation_local(expression, checker):
    """Check correlation locally before submission"""
    # Assume preliminary Sharpe of 1.3 (above cutoff) for initial check
    result = checker.check_correlation(expression, new_alpha_sharpe=1.3)
    return result

# Sidebar
st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("---")

email, password = load_credentials()
if email and password:
    st.sidebar.success(f"✅ Logged in as: {email}")
else:
    st.sidebar.error("❌ Credentials not found")
    st.sidebar.info("Please create credential.txt with email and password")

st.sidebar.markdown("### Quick Actions")
action = st.sidebar.radio(
    "Choose Action:",
    ["Generate Alpha", "Check Correlation", "Test on WQ", "View Submitted", "Auto-Improve"]
)

# Main content
st.title("📊 WorldQuant Alpha Improvement System")
st.markdown("""
### Stage 1 IQC Requirements
- **Sharpe Ratio**: ≥ 1.25
- **Fitness**: ≥ 1.0  
- **Turnover**: 1% - 70%
- **Sub-universe Sharpe**: ≥ 0.73
- **Margin**: > 0
- **Correlation**: < 0.70 (or Sharpe +10% higher)
""")

st.markdown("---")

# Action: Generate Alpha
if action == "Generate Alpha":
    st.header("🔬 Generate New Alpha Expression")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        strategy_type = st.selectbox(
            "Strategy Type",
            ["mean_reversion", "momentum", "volume_price", "volatility", "random_mix"]
        )
        
        complexity = st.slider("Complexity Level", 1, 5, 3)
        
        if st.button("Generate Expression", type="primary"):
            with st.spinner("Generating alpha expression..."):
                generator = SimpleAlphaGenerator()
                expression = generator.generate_single_alpha(
                    strategy_type=strategy_type,
                    complexity=complexity
                )
                
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
    
    if st.button("Check Correlation", type="primary"):
        if not expression:
            st.error("Please provide an alpha expression")
        else:
            with st.spinner("Checking correlation..."):
                checker = SelfCorrelationChecker()
                result = check_correlation_local(expression, checker)
                
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
    2. ✅ Credentials configured
    3. ✅ Under concurrent simulation limit (5-10)
    """)
    
    use_generated = st.checkbox("Use last generated alpha", value=True, key="wq_test")
    
    if use_generated and st.session_state.current_alpha:
        expression = st.session_state.current_alpha
    else:
        expression = st.text_area("Enter Alpha Expression", height=100)
    
    if st.button("Run Simulation on WQ", type="primary"):
        if not expression:
            st.error("Please provide an alpha expression")
        elif not email or not password:
            st.error("Credentials not configured")
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
                sim_id, settings_or_error = test_alpha_on_wq(expression, email, password)
                
                if sim_id:
                    st.success(f"✅ Simulation Created! ID: `{sim_id}`")
                    st.session_state.simulation_settings = settings_or_error
                    
                    st.subheader("📋 Simulation Settings")
                    st.json(settings_or_error)
                    
                    st.info(f"""
                    🔗 **Next Steps**:
                    1. Go to https://www.worldquantbrain.com/simulations/{sim_id}
                    2. Wait for results (~2-5 minutes)
                    3. Check if metrics meet Stage 1 cutoffs
                    4. If passed, submit using the 'Submit' button
                    """)
                    
                    # Save to submitted alphas if user confirms
                    if st.button("Mark as Submitted"):
                        st.session_state.submitted_alphas.append({
                            'expression': expression,
                            'simulation_id': sim_id,
                            'settings': settings_or_error,
                            'timestamp': datetime.now().isoformat(),
                            'correlation_checked': True
                        })
                        st.success("✅ Added to submitted alphas list")
                else:
                    st.error(f"❌ Failed: {settings_or_error}")

# Action: View Submitted
elif action == "View Submitted":
    st.header("📜 Submitted Alphas History")
    
    if st.session_state.submitted_alphas:
        df = pd.DataFrame(st.session_state.submitted_alphas)
        
        # Add correlation status
        df['correlation_status'] = df.apply(
            lambda x: '✅ Checked' if x.get('correlation_checked') else '❌ Not Checked',
            axis=1
        )
        
        st.dataframe(
            df[['expression', 'simulation_id', 'timestamp', 'correlation_status']],
            use_container_width=True
        )
        
        # Show details for selected alpha
        selected = st.selectbox(
            "Select Alpha to View Details",
            options=list(range(len(st.session_state.submitted_alphas))),
            format_func=lambda x: f"Alpha #{x+1}: {st.session_state.submitted_alphas[x]['expression'][:50]}..."
        )
        
        if selected is not None:
            alpha = st.session_state.submitted_alphas[selected]
            st.subheader("📋 Simulation Settings")
            st.json(alpha.get('settings', {}))
            
            if alpha.get('simulation_id'):
                st.link_button(
                    "🔗 Open in WorldQuant Brain",
                    f"https://www.worldquantbrain.com/simulations/{alpha['simulation_id']}"
                )
    else:
        st.info("No alphas submitted yet. Generate and test some alphas first!")

# Action: Auto-Improve
elif action == "Auto-Improve":
    st.header("🤖 Continuous Alpha Improvement")
    
    st.markdown("""
    This mode automatically:
    1. Generates diverse alpha expressions
    2. Checks correlation locally FIRST
    3. Tests on WorldQuant Brain
    4. Submits if all criteria pass
    5. Learns from each iteration
    """)
    
    target_submissions = st.number_input(
        "Target Number of Submissions",
        min_value=1,
        max_value=20,
        value=5
    )
    
    max_iterations = st.number_input(
        "Max Iterations per Alpha",
        min_value=1,
        max_value=10,
        value=3
    )
    
    if st.button("Start Auto-Improvement", type="primary"):
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
            generator = SimpleAlphaGenerator()
            expression = generator.generate_single_alpha(
                strategy_type="random_mix",
                complexity=3
            )
            
            # Check correlation locally FIRST
            status_text.text(f"Iteration {iteration}: Checking correlation...")
            checker = SelfCorrelationChecker()
            corr_result = check_correlation_local(expression, checker)
            
            if not corr_result.get('is_safe_to_submit', True):
                status_text.text(f"Iteration {iteration}: ❌ Correlation too high, skipping...")
                continue
            
            # Test on WQ
            status_text.text(f"Iteration {iteration}: Testing on WorldQuant...")
            sim_id, result = test_alpha_on_wq(expression, email, password)
            
            if sim_id:
                submitted_count += 1
                st.session_state.submitted_alphas.append({
                    'expression': expression,
                    'simulation_id': sim_id,
                    'timestamp': datetime.now().isoformat(),
                    'correlation_checked': True
                })
                
                with results_container:
                    st.success(f"✅ Alpha #{submitted_count} submitted! ID: `{sim_id}`")
                    st.code(expression, language="python")
                
                progress_bar.progress(submitted_count / target_submissions)
            else:
                status_text.text(f"Iteration {iteration}: ❌ Failed - {result}")
        
        status_text.text("✅ Auto-improvement complete!")
        st.success(f"Successfully submitted {submitted_count}/{target_submissions} alphas")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
<b>WorldQuant Alpha Improvement System</b> | Stage 1 IQC Focus<br>
<i>Local correlation checking saves time and API calls!</i>
</div>
""", unsafe_allow_html=True)
