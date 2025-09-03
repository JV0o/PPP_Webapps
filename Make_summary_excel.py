import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Plate Mapper & Benchling Prep", layout="wide")

st.title("🧪 Plate Mapper & Benchling Prep (Streamlit)")
st.write(
    "Upload your sample scheme, timepoints file, and Benchling export to generate an Excel file with `benchling` and `overview` sheets."
)

# -----------------------------
# Helpers
# -----------------------------

def get_well_positions(plate_used: int):
    if plate_used == 24:
        return [
            'A1','A2','A3','A4','A5','A6',
            'B1','B2','B3','B4','B5','B6',
            'C1','C2','C3','C4','C5','C6',
            'D1','D2','D3','D4','D5','D6'
        ]
    elif plate_used == 96:
        rows = list("ABCDEFGH")
        cols = [str(i) for i in range(1,13)]
        return [f"{r}{c}" for r in rows for c in cols]
    else:
        raise ValueError("Unsupported plate size. Choose 24 or 96.")


def process_excel(excel_file, plate_used: int) -> pd.DataFrame:
    df = pd.read_excel(excel_file, sheet_name="List Format", engine='openpyxl')
    well_positions = get_well_positions(plate_used)
    num_samples = len(well_positions)

    combined_samples = []
    plate_info = []
    well_info = []
    reactor_number_info = []
    sample_number_info = []

    for column in df.columns:
        plate_number = column.split()[-1]
        samples = df[column].dropna().tolist()

        for i, sample in enumerate(samples):
            if sample == 'Empty':
                reactor_number = 'Empty'
                sample_number = 'Empty'
            else:
                reactor_part = sample.split('S')[0]
                sample_part = sample.split('S')[1]
                if len(reactor_part) >= 3:
                    reactor_number = 'R' + reactor_part[1] + reactor_part[2]
                else:
                    reactor_number = 'R0' + reactor_part[1]
                sample_number = 'S' + sample_part.zfill(2)

            combined_samples.append(sample)
            plate_info.append(plate_number)
            well_info.append(well_positions[i % num_samples])
            reactor_number_info.append(reactor_number)
            sample_number_info.append(sample_number)

    combined_df = pd.DataFrame({
        'Sample': combined_samples,
        'Plate': plate_info,
        'Destination Well': well_info,
        'Reactor': reactor_number_info,
        'Timepoint (#)': sample_number_info,
    })
    return combined_df


def process_timepoints_and_benchling(timepoints_file, benchling_csv_file) -> pd.DataFrame:
    # Benchling CSV with columns: 'Reactor/Plate/Flask Number', 'Entity', 'Base Medium'
    bdf = pd.read_csv(benchling_csv_file)
    df2 = bdf[['Reactor/Plate/Flask Number', 'Entity']]
    df3 = bdf[['Reactor/Plate/Flask Number', 'Base Medium']]

    dmb = dict(df2.values)
    dmb2 = dict(df3.values)

    # A-H -> 1-8 map
    n2n = {chr(65 + i): i + 1 for i in range(8)}

    # Read timepoints lines (txt or csv treated as text lines)
    raw = timepoints_file.read()
    if isinstance(raw, bytes):
        text = raw.decode('utf-8', errors='ignore')
    else:
        text = str(raw)

    lines = text.splitlines()
    data = []
    regex = r"Bioreactor\s+(\d+)\"\,(\S+)\,\"Sample\s+(\S+)\s+mL+\s.+\s+(\d+)\/([A-Z]+\d+)"

    for line in lines:
        matches = re.search(regex, line)
        if matches:
            time_str = matches.group(2)
            if 'h' in time_str:
                try:
                    time_value = float(time_str.replace('h', ''))
                except ValueError:
                    time_value = None
            else:
                try:
                    time_value = float(time_str)
                except ValueError:
                    time_value = None

            well = matches.group(5)
            well_row = well[0]
            data.append({
                'Reactor': f"R{int(matches.group(1)):02d}",
                'Timepoint (h)': time_str,
                'Time_Value': time_value,
                'Volume': matches.group(3),
                'Plate': matches.group(4),
                'Destination Well': well,
                'Well_Number': n2n.get(well_row)
            })

    csv_df = pd.DataFrame(data)
    if not csv_df.empty:
        csv_df = csv_df[csv_df['Volume'] != '2.00']
        csv_df['Parent culture'] = csv_df['Reactor'].map(dmb)
        csv_df['Medium'] = csv_df['Reactor'].map(dmb2)
    return csv_df


def build_output_excel(merged_df: pd.DataFrame) -> bytes:
    # benchling_df: only rows with numeric Time_Value
    benchling_df = merged_df[merged_df['Time_Value'].notna() & (merged_df['Time_Value'] != '')].copy()

    # Insert benchling-specific columns
    columns_before = ['Benchling sample', 'Destination Plate', 'Benchling sample SOA']
    columns_after = ['Dilution', 'Raw Absorbance Value #1', 'Raw Absorbance Value #2']

    df_before = pd.DataFrame(columns=columns_before)
    df_after = pd.DataFrame(columns=columns_after)

    benchling_df = pd.concat([df_before, benchling_df, df_after], axis=1)
    benchling_df.insert(0, '#', range(1, len(benchling_df) + 1))
    benchling_df.rename(columns={'Reactor': 'Reactor/Plate Number'}, inplace=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        benchling_df.to_excel(writer, sheet_name='benchling', index=False)
        merged_df.to_excel(writer, sheet_name='overview', index=False)

        workbook = writer.book
        worksheet = writer.sheets['benchling']

        text_format = workbook.add_format({'num_format': '@'})
        worksheet.write('U2', 'XXX_PD_001_AMBR')
        worksheet.write('U3', 'Plate name benchling')
        worksheet.write('U4', 'XXX_PD_001_AMBR_SOA_plate#1')
        worksheet.write('V3', 'Plate Nr (from AMBR)')
        worksheet.write('V4', '11')
        worksheet.write('V2', 'CAREFUL TO WRITE THE PLATE NR AS TEXT')
        worksheet.write('S1', 'CDW')
        worksheet.write('T1', 'replicate #')
        worksheet.write('U1', 'Not used')
        worksheet.write('V1', 'Not used')

        worksheet.set_column('P:P', None, text_format)
        worksheet.set_column('Q:Q', None, text_format)
        worksheet.set_column('R:R', None, text_format)
        worksheet.set_column('S:S', None, text_format)

        # Determine number of rows actually written (including header)
        n_rows = len(benchling_df) + 1  # +1 header; Excel rows start at 1

        for row in range(2, n_rows + 1):  # start at row 2 (first data row)
            worksheet.write(f'T{row}', 1)  # replicate # = 1
            worksheet.write_formula(f'B{row}', f'=$U$2&"_"&H{row}&"__"&I{row}')
            worksheet.write_formula(f'C{row}', f'=IF(F{row}=$V$4,$U$4,IF(F{row}=$V$5,$U$5))')
            worksheet.write_formula(f'D{row}', f'=$U$2&"_"&H{row}&"__"&I{row}&"_"&"SOA"&"_"&"#"&T{row}')

    output.seek(0)
    return output.read()

# -----------------------------
# UI
# -----------------------------
col1, col2, col3 = st.columns(3)
with col1:
    plate_used = st.selectbox("Plate type", [24, 96], index=1)
with col2:
    excel_file = st.file_uploader("Sample scheme Excel (sheet: 'List Format')", type=["xlsx", "xls"], accept_multiple_files=False)
with col3:
    timepoints_file = st.file_uploader("Timepoints file (txt or csv as text)", type=["txt", "csv"], accept_multiple_files=False)

benchling_csv_file = st.file_uploader("Benchling export CSV (Fermentation Culture - Main)", type=["csv"], accept_multiple_files=False)

if excel_file is not None:
    try:
        combined_df = process_excel(excel_file, plate_used)
        st.success("Sample scheme processed.")
        with st.expander("Preview: Combined sample scheme"):
            st.dataframe(combined_df.head(50))
    except Exception as e:
        st.error(f"Error processing Excel: {e}")
        st.stop()
else:
    st.info("Please upload the sample scheme Excel to continue.")

if excel_file is not None and timepoints_file is not None and benchling_csv_file is not None:
    try:
        timepoints_df = process_timepoints_and_benchling(timepoints_file, benchling_csv_file)
        if timepoints_df is None or timepoints_df.empty:
            st.warning("Parsed timepoints are empty or unrecognized. Check file format and regex assumptions.")
        else:
            st.success("Timepoints + Benchling CSV processed.")
            with st.expander("Preview: Timepoints parsed"):
                st.dataframe(timepoints_df.head(50))

        merged_df = pd.merge(
            combined_df, timepoints_df, on=['Plate', 'Destination Well', 'Reactor'], how='left'
        )
        merged_df = merged_df.sort_values(by=['Reactor', 'Time_Value'])

        st.subheader("Merged overview")
        st.dataframe(merged_df.head(200))

        output_bytes = build_output_excel(merged_df)
        st.download_button(
            label="⬇️ Download Excel (benchling + overview)",
            data=output_bytes,
            file_name="plate_mapping_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.error(f"Error processing files: {e}")
