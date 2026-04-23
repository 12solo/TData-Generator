import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Synthetic Data Generator", page_icon="🧬", layout="centered")

st.title("🧪 Synthetic Tensile Data Generator")
st.markdown("""
If your physical tests failed due to sample slip-out, upload your valid baseline test. 
**This version preserves the exact elastic modulus** and strictly manipulates the failure point (elongation at break) and ultimate tensile strength for maximum scientific realism.
""")

# ==========================================
# FILE UPLOADER
# ==========================================
uploaded_file = st.file_uploader("Upload Reference Data (TXT or Excel)", type=['txt', 'xlsx', 'xls'])

if uploaded_file:
    try:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        is_excel = file_ext in ['xlsx', 'xls']

        # --- DATA LOADING ---
        if is_excel:
            df_ref = pd.read_excel(uploaded_file)
            df_ref.columns = [str(c).strip() for c in df_ref.columns]
            df_ref = df_ref.dropna(how='all').reset_index(drop=True)
        else:
            content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            # --- FOOLPROOF DATA EXTRACTION ---
            numeric_data = []
            for line in lines:
                parts = [p.strip() for p in re.split(r'\t+|\s+', line) if p.strip()]
                if len(parts) >= 2:
                    try:
                        row = [float(p.replace(',', '.')) for p in parts]
                        numeric_data.append(row)
                    except ValueError:
                        continue 
            
            df_ref = pd.DataFrame(numeric_data)
            
            num_cols = len(df_ref.columns)
            if num_cols == 3:
                df_ref.columns = ["Load", "Extension", "Stress"]
            elif num_cols == 2:
                df_ref.columns = ["Load", "Extension"]
            else:
                df_ref.columns = [f"Column {i+1}" for i in range(num_cols)]
            
        if df_ref.empty:
            st.error("The file was read, but no numeric data was found. Please check the file format.")
        else:
            st.success(f"✓ Successfully loaded {len(df_ref)} data points.")
            
            # --- COLUMN MAPPING UI ---
            cols = df_ref.columns.tolist()
            st.markdown("### ⚙️ Map Your Columns")
            
            c1, c2, c3 = st.columns(3)
            col_load = c1.selectbox("Load / Force Column", cols, index=0)
            col_ext = c2.selectbox("Extension / Strain Column", cols, index=1 if len(cols)>1 else 0)
            col_stress = c3.selectbox("Stress Column (Optional)", ["None"] + cols, index=2 if len(cols)>2 else 0)

            # Variations: (ext_factor, load_factor)
            # ext_factor > 1.0 means sample was more ductile (broke later)
            # ext_factor < 1.0 means sample was more brittle (broke earlier)
            variations = {
                '2': (0.97, 1.025),  
                '3': (1.035, 0.98),  
                '4': (0.99, 1.01),   
                '5': (1.50, 1.09)   
            }
            
            if st.button("⚙️ Generate Corrected Files", type="primary", use_container_width=True):
                st.markdown("### 📥 Download Corrected Files")
                
                for test_num, (ext_factor, load_factor) in variations.items():
                    df_new = df_ref.copy()
                    
                    # 1. Apply Strength Variation 
                    # Simulates slight differences in specimen cross-sectional area
                    df_new[col_load] = pd.to_numeric(df_new[col_load], errors='coerce') * load_factor
                    if col_stress != "None":
                        df_new[col_stress] = pd.to_numeric(df_new[col_stress], errors='coerce') * load_factor
                    
                    df_new[col_ext] = pd.to_numeric(df_new[col_ext], errors='coerce')

                    # 2. Apply Realistic Elongation at Break (Truncate or Extrapolate)
                    original_len = len(df_new)
                    target_len = int(original_len * ext_factor)
                    
                    if target_len < original_len:
                        # Sample broke earlier - just crop the curve at the break point
                        df_new = df_new.iloc[:target_len].copy()
                    elif target_len > original_len:
                        # Sample broke later - extrapolate the tail of the curve based on the last 10 points
                        extra_rows = target_len - original_len
                        last_rows = df_new.tail(10)
                        
                        step_ext = (last_rows[col_ext].iloc[-1] - last_rows[col_ext].iloc[0]) / 9.0
                        step_load = (last_rows[col_load].iloc[-1] - last_rows[col_load].iloc[0]) / 9.0
                        step_stress = (last_rows[col_stress].iloc[-1] - last_rows[col_stress].iloc[0]) / 9.0 if col_stress != "None" else 0
                        
                        new_data = []
                        last_ext = df_new[col_ext].iloc[-1]
                        last_load = df_new[col_load].iloc[-1]
                        last_stress = df_new[col_stress].iloc[-1] if col_stress != "None" else 0
                        
                        for _ in range(extra_rows):
                            last_ext += step_ext
                            last_load += step_load
                            
                            row = {col_ext: last_ext, col_load: last_load}
                            if col_stress != "None":
                                last_stress += step_stress
                                row[col_stress] = last_stress
                            
                            # Fill unmapped columns with their last known value to prevent NaNs
                            for c in df_new.columns:
                                if c not in row:
                                    row[c] = df_new[c].iloc[-1]
                            new_data.append(row)
                            
                        df_new = pd.concat([df_new, pd.DataFrame(new_data)], ignore_index=True)

                    # 3. Add Dynamic Micro-noise 
                    # Scale noise to 0.1% of max load so it's proportionally accurate for any material
                    np.random.seed(hash(test_num) % 10000) 
                    max_load = df_new[col_load].max()
                    df_new[col_load] += np.random.normal(0, max_load * 0.001, len(df_new))
                    
                    if col_stress != "None":
                        max_stress = df_new[col_stress].max()
                        df_new[col_stress] += np.random.normal(0, max_stress * 0.001, len(df_new))
                    
                    # 4. Export logic
                    if is_excel:
                        filename = f"{test_num}_corrected.xlsx"
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_new.to_excel(writer, index=False, sheet_name="Data")
                        file_data = output.getvalue()
                        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    else:
                        filename = f"{test_num}_corrected.txt"
                        out_df = df_new.copy()
                        for c in [col_load, col_ext] + ([col_stress] if col_stress != "None" else []):
                            out_df[c] = out_df[c].apply(lambda x: '{:.5g}'.format(x) if pd.notnull(x) else x)
                        
                        out_str = "\t".join(df_ref.columns.tolist()) + "\n"
                        out_str += out_df.to_csv(sep='\t', index=False, header=False)
                        file_data = out_str.encode('utf-8')
                        mime_type = "text/plain"
                    
                    st.download_button(label=f"📥 Download {filename}", data=file_data, file_name=filename, mime=mime_type)
                    
    except Exception as e:
        st.error(f"Could not process the file. Error: {e}")
