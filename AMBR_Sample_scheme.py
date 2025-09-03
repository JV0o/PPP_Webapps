import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Sampling Scheme Generator", layout="wide")
st.title("Sampling Scheme Generator")

# --- UI Inputs ---
plate_type = st.selectbox("Select Plate Type:", ["24 well plate", "96 well plate"])
num_reactors = st.number_input("Number of Reactors", min_value=1, value=1)
num_samples = st.number_input("Samples per Reactor", min_value=1, value=1)
starting_reactor = st.number_input("Starting Reactor Number", min_value=1, value=1)
end_batch = st.checkbox("Include End Batch Sample")

# --- Sampling Scheme Logic ---
def create_sampling_scheme(num_reactors, num_samples, columns, wells_per_plate, starting_reactor, end_batch):
    scheme = []
    plate = []
    well_counter = 0
    plate_counter = 1

    if end_batch:
        for reactor in range(starting_reactor, starting_reactor + num_reactors):
            plate.append(f"R{reactor}S81")
            well_counter += 1

    for sample in range(num_samples):
        for reactor in range(starting_reactor, starting_reactor + num_reactors):
            plate.append(f"R{reactor}S{sample}")
            well_counter += 1
            if well_counter == wells_per_plate:
                scheme.append((plate_counter, plate))
                plate = []
                well_counter = 0
                plate_counter += 1

    if plate:
        while len(plate) < wells_per_plate:
            plate.append("Empty")
        scheme.append((plate_counter, plate))

    return scheme

# --- Excel Export Logic ---
def export_to_excel(plate_names, plate_data, plate_type):
    df_list_format = pd.DataFrame({name: plate for name, plate in zip(plate_names, plate_data)})

    # 1Col_List
    one_col_list = df_list_format.melt(var_name='Plate', value_name='Sample').dropna()
    one_col_list = one_col_list[one_col_list['Sample'] != 'Empty']['Sample'].reset_index(drop=True)

    # Cols_16_Rows
    col_count = -(-len(one_col_list) // 16)
    rows_16 = [one_col_list[i:i + 16].reset_index(drop=True) for i in range(0, len(one_col_list), 16)]
    df_16 = pd.concat(rows_16, axis=1)
    df_16.columns = [f'Col{i + 1}' for i in range(col_count)]

    # Matrix_8x12_X
    matrices = []
    matrix_count = (len(one_col_list) + 95) // 96
    for sheet_num in range(matrix_count):
        matrix_8x12 = pd.DataFrame(index=range(8), columns=range(12))
        for i in range(96):
            sample_index = sheet_num * 96 + i
            if sample_index >= len(one_col_list):
                break
            col, row = divmod(i, 8)
            matrix_8x12.iloc[row, col] = one_col_list[sample_index]
        matrices.append((f"Matrix_8x12_{sheet_num + 1}", matrix_8x12))

    # Write to Excel
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
        df_list_format.to_excel(writer, sheet_name="List Format", index=False)
        one_col_list.to_excel(writer, sheet_name="1Col_List", index=False, header=False)
        df_16.to_excel(writer, sheet_name="Cols_16_Rows", index=False, header=False)
        for sheet_name, matrix in matrices:
            matrix.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

    return towrite.getvalue()

# --- Generate Scheme Button ---
if st.button("Generate Scheme"):
    if plate_type == "24 well plate":
        columns = 6
        wells_per_plate = 24
    else:
        columns = 12
        wells_per_plate = 96

    scheme = create_sampling_scheme(num_reactors, num_samples, columns, wells_per_plate, starting_reactor, end_batch)

    plate_names = []
    plate_data = []

    for i, (plate_number, plate) in enumerate(scheme, start=1):
        plate_row = (plate_number - 1) % 3 + 1
        plate_col = (plate_number - 1) // 3 + 1
        plate_name = f"Frozen {plate_row}{plate_col}"
        plate_names.append(plate_name)
        plate_data.append(plate)

        st.subheader(plate_name)
        rows = [plate[i:i + columns] for i in range(0, len(plate), columns)]
        df = pd.DataFrame(rows)
        st.dataframe(df)

    # Export Excel
    excel_file = export_to_excel(plate_names, plate_data, plate_type)
    st.download_button("Download Excel", data=excel_file, file_name="sampling_scheme.xlsx")
