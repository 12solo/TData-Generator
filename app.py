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
This version is specifically optimized to handle metadata headers and empty row gaps.
""")

uploaded_file = st.file_uploader("Upload Reference Data (TXT or Excel)", type=['txt', 'xlsx', 'xls'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith(('xlsx', 'xls')):
            df_ref = pd.read_excel(uploaded_file)
            df_ref.columns = [str(c).strip() for c in df_ref.columns]
            df_ref = df_ref.dropna(how='all').reset_index(drop=True)
            is_excel = True
        else:
            is_excel = False
            content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            # 1. Identify the Header Row (Look for 'Carico' or similar)
            # Your file starts with "Carico..." 
            header_row_index = 0
            for i, line in enumerate(lines):
                if "Carico" in line or "Deformazione" in line:
                    header_row_index = i
                    break
            
            # 2. Clean Headers (Remove metadata like '') 
            raw_header_line = lines[header_row_index].strip()
            # Remove brackets/source info if present
            raw_header_line = re.sub(r'\[.*?\]', '', raw_header_line).strip()
            headers = [h.strip() for h in raw_header_line.split('\t') if h.strip()]
            
            # 3. Extract Numeric Data (Ignore empty rows and non-numeric noise) 
            numeric_data = []
            for line in lines[header_row_index + 1:]:
                # Split by tab or multiple spaces
                parts = re.split(r'\t+|\s+', line.strip())
                # Filter out empty strings
                parts = [p for p in parts if p]
                
                if len(parts) >= len(headers):
                    try:
                        # Convert only the columns we expect
                        row = [float(p.replace(',', '.')) for p in parts[:len(headers)]]
                        numeric_data.append(row)
                    except ValueError:
                        continue # Skip lines that aren't pure numbers
            
            df_ref = pd.DataFrame(numeric_data, columns=headers)

        if df_ref.empty:
            st.error("The file was read, but no numeric data was found. Please check the file format.")
        else:
            st.success(f"✓ Successfully loaded {len(df_ref)} data points.")
            
            # --- COLUMN MAPPING ---
            cols = df_ref.columns.tolist()
            c1, c2, c3 = st.columns(3)
            col_load = c1.selectbox("Load (N)", cols, index=0)
            col_ext = c2.selectbox("Extension (mm)", cols, index=1 if len(cols)>1 else 0)
            col_stress = c3.selectbox("Stress (MPa)", ["None"] + cols, index=2 if len(cols)>2 else 0)

            variations = {
                '2': (0.97, 1.025), '3': (1.035, 0.98), 
                '4': (0.99, 1.01),  '5': (0.955, 1.03)
            }
            
            if st.button("⚙️ Generate Corrected Files", type="primary", use_container_width=True):
                for test_num, (ext_factor, load_factor) in variations.items():
                    df_new = df_ref.copy()
                    
                    # Apply variation
                    df_new[col_load] = pd.to_numeric(df_new[col_load]) * load_factor
                    df_new[col_ext] = pd.to_numeric(df_new[col_ext]) * ext_factor
                    if col_stress != "None":
                        df_new[col_stress] = pd.to_numeric(df_new[col_stress]) * load_factor
                    
                    # Add noise
                    np.random.seed(hash(test_num) % 10000)
                    noise = np.random.normal(0, 0.02, len(df_new))
                    df_new[col_load] += noise
                    
                    # Export
                    if is_excel:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_new.to_excel(writer, index=False)
                        st.download_button(f"📥 Download Test {test_num} (Excel)", output.getvalue(), f"Test_{test_num}.xlsx")
                    else:
                        # Format output to match your source style
                        csv = df_new.to_csv(sep='\t', index=False, float_format='%.5g')
                        st.download_button(f"📥 Download Test {test_num} (TXT)", csv, f"Test_{test_num}.txt")
                        
    except Exception as e:
        st.error(f"Error: {e}")
