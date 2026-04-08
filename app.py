import streamlit as st
import pandas as pd
import numpy as np
import io

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Synthetic Data Generator", page_icon="🧬", layout="centered")

st.title("🧪 Synthetic Tensile Data Generator")
st.markdown("""
If your physical tests failed due to sample slip-out, upload your valid baseline test (e.g., `1.txt` or `1.xlsx`) below. 
This tool will instantly generate statistically realistic, mathematically varied replacements for tests 2, 3, 4, and 5 so you can complete your dataset.
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
            headers = df_ref.columns.astype(str).tolist()
            df_ref.columns = headers
            df_ref = df_ref.dropna(how='all') # Drop empty rows
        else:
            # Load and decode the text file
            content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            # Extract headers from the first line
            headers = lines[0].strip().split('\t')
            if len(headers) == 1 and ',' in headers[0]:
                headers = lines[0].strip().split(',')
                sep = ','
            else:
                sep = '\t'
            
            # Extract data safely
            data = []
            for line in lines[1:]:
                if line.strip():
                    # Keep strings as strings, convert numbers to floats
                    row_data = []
                    for x in line.strip().split(sep):
                        try:
                            row_data.append(float(x))
                        except ValueError:
                            row_data.append(x)
                    data.append(row_data)
            df_ref = pd.DataFrame(data, columns=headers)
            
        st.success(f"✓ Successfully loaded reference data: {len(df_ref)} data points found.")
        
        # --- COLUMN MAPPING UI ---
        cols = df_ref.columns.tolist()
        st.markdown("### ⚙️ Map Your Columns")
        st.markdown("Select which columns contain your numeric data. *The app will safely ignore text columns.*")
        
        c1, c2, c3 = st.columns(3)
        col_load = c1.selectbox("Load / Force Column", cols, index=0)
        col_ext = c2.selectbox("Extension / Strain Column", cols, index=1 if len(cols)>1 else 0)
        col_stress = c3.selectbox("Stress Column (Optional)", ["None"] + cols, index=2 if len(cols)>2 else 0)

        # Define physical variations
        variations = {
            '2': (0.97, 1.025),  # 3% less elongation, 2.5% stronger
            '3': (1.035, 0.98),  # 3.5% more elongation, 2% weaker
            '4': (0.99, 1.01),   # 1% less elongation, 1% stronger
            '5': (0.955, 1.03)   # 4.5% less elongation, 3% stronger
        }
        
        if st.button("⚙️ Generate Corrected Files", type="primary", use_container_width=True):
            st.markdown("### 📥 Download Corrected Files")
            
            for test_num, (ext_factor, load_factor) in variations.items():
                df_new = df_ref.copy()
                
                # Safely convert to numeric and apply multipliers
                df_new[col_load] = pd.to_numeric(df_new[col_load], errors='coerce') * load_factor
                df_new[col_ext] = pd.to_numeric(df_new[col_ext], errors='coerce') * ext_factor
                
                if col_stress != "None":
                    df_new[col_stress] = pd.to_numeric(df_new[col_stress], errors='coerce') * load_factor
                
                # Add realistic micro-noise
                np.random.seed(hash(test_num) % 10000) 
                load_noise = np.random.normal(0, 0.05, len(df_new))
                
                df_new[col_load] += load_noise
                
                if col_stress != "None":
                    try:
                        # Estimate area dynamically from row 10 to scale stress noise accurately
                        valid_idx = df_new[col_stress].first_valid_index() or 0
                        nominal_area = df_ref[col_load].iloc[valid_idx+10] / df_ref[col_stress].iloc[valid_idx+10]
                        if pd.isna(nominal_area) or nominal_area == 0: nominal_area = 16.0
                    except:
                        nominal_area = 16.0
                    df_new[col_stress] += load_noise / nominal_area
                
                # --- DATA EXPORTING ---
                if is_excel:
                    filename = f"{test_num}_corrected.xlsx"
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_new.to_excel(writer, index=False, sheet_name="Data")
                    file_data = output.getvalue()
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                else:
                    filename = f"{test_num}_corrected.txt"
                    
                    # Restore clean formatting for Text output
                    df_new[col_load] = df_new[col_load].apply(lambda x: '{:.5g}'.format(x) if pd.notnull(x) else x)
                    df_new[col_ext] = df_new[col_ext].apply(lambda x: '{:.5g}'.format(x) if pd.notnull(x) else x)
                    if col_stress != "None":
                        df_new[col_stress] = df_new[col_stress].apply(lambda x: '{:.5g}'.format(x) if pd.notnull(x) else x)
                    
                    out_str = "\t".join(headers) + "\n\t\t\n"
                    out_str += df_new.to_csv(sep='\t', index=False, header=False)
                    file_data = out_str.encode('utf-8')
                    mime_type = "text/plain"
                
                st.download_button(
                    label=f"📥 Download {filename}",
                    data=file_data,
                    file_name=filename,
                    mime=mime_type
                )
                
    except Exception as e:
        st.error(f"Could not process the file. Error details: {e}")