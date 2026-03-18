import streamlit as st
import pandas as pd

# Set page to wide mode for better mobile viewing
st.set_page_config(page_title="Greyhound Analyzer", layout="wide")

st.title("🐕 Greyhound 60/40 Analyzer")

# Step 1: File Upload
uploaded_file = st.file_uploader("Upload Greyhound CSV", type="csv")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Standardize column names to remove hidden spaces
        df.columns = df.columns.str.strip()
        
        required = ['Greyhound_Name', 'Race_Time', 'BON', 'SP', 'Track', 'Distance', 'Date']
        
        if all(col in df.columns for col in required):
            # Convert Date safely
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']) # Remove rows with unreadable dates
            df = df.sort_values(by=['Greyhound_Name', 'Date'], ascending=[True, False])

            # --- SIDEBAR FILTERS ---
            st.sidebar.header("Settings")
            lookback = st.sidebar.selectbox("Last X Runs", options=[3, 5, 10, "All"], index=0)
            
            # Filters
            u_tracks = sorted(df['Track'].unique().tolist())
            selected_tracks = st.sidebar.multiselect("Tracks", u_tracks, default=u_tracks)
            
            u_dist = sorted(df['Distance'].unique().tolist())
            selected_dist = st.sidebar.multiselect("Distances", u_dist, default=u_dist)

            # Apply Filters
            mask = (df['Track'].isin(selected_tracks)) & (df['Distance'].isin(selected_dist))
            f_df = df[mask].copy()

            if not f_df.empty:
                # 1. Calc Time-BON
                f_df['Time_Diff'] = f_df['Race_Time'] - f_df['BON']

                # 2. Grab 'Last X' runs per dog
                if lookback != "All":
                    f_df = f_df.groupby('Greyhound_Name').head(int(lookback))

                # 3. Aggregate
                ans = f_df.groupby('Greyhound_Name').agg({
                    'Time_Diff': 'mean',
                    'SP': 'mean',
                    'Date': 'count'
                }).reset_index()
                
                # 4. Scoring (60% Time / 40% SP)
                # Lower is better for both Time_Diff and SP
                for col, score_name in [('Time_Diff', 'T_Score'), ('SP', 'S_Score')]:
                    c_min, c_max = ans[col].min(), ans[col].max()
                    if c_min != c_max:
                        ans[score_name] = 1 - (ans[col] - c_min) / (c_max - c_min)
                    else:
                        ans[score_name] = 1.0

                ans['Power_Rating'] = (ans['T_Score'] * 0.6) + (ans['S_Score'] * 0.4)
                
                # Final Display
                res = ans[['Greyhound_Name', 'Date', 'Time_Diff', 'SP', 'Power_Rating']]
                res.columns = ['Greyhound', 'Runs', 'Avg_Diff', 'Avg_SP', 'Rating']
                
                st.subheader("Rankings")
                st.dataframe(res.sort_values('Rating', ascending=False).style.format({'Rating': '{:.1%}'}))
            else:
                st.warning("No data matches those filters.")
        else:
            st.error(f"CSV missing columns. Needs: {required}")
    except Exception as e:
        st.error(f"Error processing file: {e}")
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
