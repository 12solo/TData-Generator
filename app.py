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
If your physical tests failed due to sample slip-out, upload your valid baseline test below. 
This tool will generate statistically realistic, mathematically varied replacements for tests 2-5.
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
            df_ref = df_ref.dropna(how='all') 
        else:
            # Decode text file
            content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            # --- ROBUST HEADER PARSING ---
            # We strip trailing whitespace and filter out empty segments to avoid "ghost" columns 
            raw_headers = lines[0].strip().split('\t')
            if len(raw_headers) == 1 and ',' in raw_headers[0]:
                headers = [h.strip() for h in raw_headers[0].split(',') if h.strip()]
                sep = ','
            else:
                headers = [h.strip() for h in raw_headers if h.strip()]
                sep = '\t'
            
            # --- ROBUST DATA PARSING ---
            data = []
            for line in lines[1:]:
                clean_line = line.strip()
                if clean_line:
                    # Only grab values for columns we have headers for 
                    parts = clean_line.split(sep)
                    row_data = []
                    for x in parts[:len(headers)]:
                        try:
                            row_data.append(float(x))
                        except ValueError:
                            row_data.append(x)
                    
                    if any(pd.notnull(row_data)):
                        data.append(row_data)
            
            df_ref = pd.DataFrame(data, columns=headers)
            
        st.success(f"✓ Successfully loaded {len(df_ref)} data points.")
        
        # --- COLUMN MAPPING UI ---
        cols = df_ref.columns.tolist()
        st.markdown("### ⚙️ Map Your Columns")
        
        c1, c2, c3 = st.columns(3)
        col_load = c1.selectbox("Load / Force Column", cols, index=0)
        col_ext = c2.selectbox("Extension / Strain Column", cols, index=1 if len(cols)>1 else 0)
        col_stress = c3.selectbox("Stress Column (Optional)", ["None"] + cols, index=2 if len(cols)>2 else 0)

        # Variations for tests 2, 3, 4, 5 
        variations = {
            '2': (0.97, 1.025),  
            '3': (1.035, 0.98),  
            '4': (0.99, 1.01),   
            '5': (0.955, 1.03)   
        }
        
        if st.button("⚙️ Generate Corrected Files", type="primary", use_container_width=True):
            st.markdown("### 📥 Download Corrected Files")
            
            for test_num, (ext_factor, load_factor) in variations.items():
                df_new = df_ref.copy()
                
                # Apply variation factors 
                df_new[col_load] = pd.to_numeric(df_new[col_load], errors='coerce') * load_factor
                df_new[col_ext] = pd.to_numeric(df_new[col_ext], errors='coerce') * ext_factor
                
                if col_stress != "None":
                    df_new[col_stress] = pd.to_numeric(df_new[col_stress], errors='coerce') * load_factor
                
                # Add micro-noise for realism 
                np.random.seed(hash(test_num) % 10000) 
                noise = np.random.normal(0, 0.05, len(df_new))
                df_new[col_load] += noise
                
                # Export logic
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
