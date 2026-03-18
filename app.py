import streamlit as st
import pandas as pd

st.set_page_config(page_title="Greyhound Form Analyzer", layout="wide")

st.title("🐕 Greyhound Multi-Form Analyzer")
st.markdown("Calculate power ratings based on **Last 3, 5, or 10** runs.")

uploaded_file = st.file_uploader("Upload Greyhound CSV", type="csv")

if uploaded_file is not None:
    # Load data
    df = pd.read_csv(uploaded_file)
    
    # Required columns (Date is now included to ensure we get the 'Latest' runs)
    required = ['Greyhound_Name', 'Race_Time', 'BON', 'SP', 'Track', 'Distance', 'Date']
    
    if all(col in df.columns for col in required):
        # Ensure Date is actually a datetime object for sorting
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by=['Greyhound_Name', 'Date'], ascending=[True, False])

        # --- SIDEBAR FILTERS ---
        st.sidebar.header("Analysis Settings")
        
        # 1. Lookback Filter
        lookback = st.sidebar.selectbox("Form Depth (Last X Runs)", options=[3, 5, 10, "All"], index=0)
        
        # 2. Track/Distance Filters
        selected_tracks = st.sidebar.multiselect("Filter Track", options=df['Track'].unique(), default=df['Track'].unique())
        selected_dist = st.sidebar.multiselect("Filter Distance", options=df['Distance'].unique(), default=df['Distance'].unique())
        
        # 3. Weights (60/40)
        time_w = st.sidebar.slider("Time-BON Weight (%)", 0, 100, 60)
        sp_w = 100 - time_w

        # --- DATA PROCESSING ---
        # Apply Track/Distance filters first
        mask = (df['Track'].isin(selected_tracks)) & (df['Distance'].isin(selected_dist))
        filtered_df = df[mask].copy()

        if not filtered_df.empty:
            # Calculate Time Difference
            filtered_df['Time_Diff'] = filtered_df['Race_Time'] - filtered_df['BON']

            # Apply the "Last X" logic per Greyhound
            if lookback != "All":
                filtered_df = filtered_df.groupby('Greyhound_Name').head(lookback)

            # Aggregate
            analysis = filtered_df.groupby('Greyhound_Name').agg({
                'Time_Diff': 'mean',
                'SP': 'mean',
                'Date': 'count' # To show how many races were actually found
            }).reset_index()
            analysis.rename(columns={'Date': 'Runs_Analyzed'}, inplace=True)

            # --- SCORING ENGINE ---
            # Time Score (Lower Diff is better)
            t_min, t_max = analysis['Time_Diff'].min(), analysis['Time_Diff'].max()
            if t_max != t_min:
                analysis['Time_Score'] = 1 - (analysis['Time_Diff'] - t_min) / (t_max - t_min)
            else:
                analysis['Time_Score'] = 1.0

            # SP Score (Lower SP is better)
            s_min, s_max = analysis['SP'].min(), analysis['SP'].max()
            if s_max != s_min:
                analysis['SP_Score'] = 1 - (analysis['SP'] - s_min) / (s_max - s_min)
            else:
                analysis['SP_Score'] = 1.0

            # Final 60/40 Weighting
            analysis['Power_Rating'] = (analysis['Time_Score'] * (time_w/100)) + (analysis['SP_Score'] * (sp_w/100))
            
            # --- DISPLAY ---
            results = analysis[['Greyhound_Name', 'Runs_Analyzed', 'Time_Diff', 'SP', 'Power_Rating']].sort_values(by='Power_Rating', ascending=False)
            
            st.subheader(f"Rankings (Based on Last {lookback} runs)")
            st.dataframe(results.style.format({
                'Time_Diff': '{:.3f}', 
                'SP': '{:.2f}', 
                'Power_Rating': '{:.2%}'
            }).background_gradient(subset=['Power_Rating'], cmap='RdYlGn'))
            
            st.download_button("Export Form Analysis", results.to_csv(index=False), "greyhound_form_results.csv")
        else:
            st.warning("No data found for the selected Track/Distance.")
    else:
        st.error(f"Your CSV must have these headers: {required}")
