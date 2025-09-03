import streamlit as st
import pandas as pd
import io

# UI
st.title("Sampling Scheme Generator")

plate_type = st.selectbox("Select Plate Type:", ["24 well plate", "96 well plate"])
num_reactors = st.number_input("Number of Reactors", min_value=1, value=1)
num_samples = st.number_input("Samples per Reactor", min_value=1, value=1)
starting_reactor = st.number_input("Starting Reactor Number", min_value=1, value=1)
end_batch = st.checkbox("Include End Batch Sample")

# Sampling Logic
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

# Generate on button click
if st.button("Generate Scheme"):
    if plate_type == "24 well plate":
        columns = 6
        wells_per_plate = 24
    else:
        columns = 12
        wells_per_plate = 96

    scheme = create_sampling_scheme(num_reactors, num_samples, columns, wells_per_plate, starting_reactor, end_batch)

    for i, (plate_number, plate) in enumerate(scheme, start=1):
        plate_row = (plate_number - 1) % 3 + 1
        plate_col = (plate_number - 1) // 3 + 1
        plate_name = f"Frozen {plate_row}{plate_col}"
        st.subheader(plate_name)

        rows = [plate[i:i+columns] for i in range(0, len(plate), columns)]
        df = pd.DataFrame(rows)
        st.dataframe(df)

    # Excel Download
    df_all = pd.DataFrame({f"Plate {i+1}": p for i, (_, p) in enumerate(scheme)})

    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
        df_all.to_excel(writer, sheet_name="List Format", index=False)
        #writer.save()
    st.download_button("Download Excel", towrite.getvalue(), "sampling_scheme.xlsx")