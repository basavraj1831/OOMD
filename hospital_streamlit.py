"""
Streamlit UI for the Hospital Management System
with Doctor assignment, Discharge, and ₹0 bill after discharge.

Run this file with:

    streamlit run hospital_streamlit.py
"""

import streamlit as st
from datetime import datetime

from Hospital_management_project import (
    HospitalManagement,
    DOCTORS,
    load_data,
    save_data,
    BED_TYPES,
)




def main():
    st.set_page_config(page_title="🏥 Sanjivni Hospital Management", layout="wide")
    st.markdown(
    """
    <h1 style="
        margin-bottom: 30px;
        text-align: center;
        items-align: center;
        font-size: 50px;
        font-family: Arial, sans-serif;
    ">
        <span style='color:#ff4d4d;'>Sanjivni</span> Hospital
    </h1>
    """,
    unsafe_allow_html=True
)


    # -------- Load persisted patient data --------
    if "patients" not in st.session_state:
        raw = load_data()
        st.session_state.patients = [HospitalManagement.from_dict(d) for d in raw]

    if "inst" not in st.session_state:
        st.session_state.inst = None

    # -------- Sidebar inputs --------
    st.sidebar.header("🧍Patient Information : ")

    defaults = {
        "sidebar_name": "",
        "sidebar_age": 30,
        "sidebar_address": "",
        "sidebar_admit": "",
        "sidebar_nights": 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    name = st.sidebar.text_input("Full Name", value=st.session_state.sidebar_name)
    age = st.sidebar.number_input("Age", min_value=0, value=st.session_state.sidebar_age)
    address = st.sidebar.text_area("Address", value=st.session_state.sidebar_address)
    admit_date = st.sidebar.text_input(
        "Admission Date (YYYY-MM-DD)",
        value=st.session_state.sidebar_admit or datetime.today().strftime("%Y-%m-%d")
    )

    # Automatically calculate nights based on admission date
    try:
        if admit_date:
            admit_dt = datetime.strptime(admit_date, "%Y-%m-%d").date()
            today = datetime.today().date()
            nights = max((today - admit_dt).days, 1)  # At least 1 night
        else:
            nights = 1
    except ValueError:
        nights = 1

    # -------- Create or Update Patient --------
    if st.sidebar.button("💾 Create Patient"):
        if not name:
            st.sidebar.error("⚠️ Please enter a patient name.")
        else:
            if st.session_state.inst is None:
                inst = HospitalManagement()
                inst.set_patient_data(name, int(age), address, admit_date, "")
                st.session_state.patients.append(inst)
                st.session_state.inst = inst
                save_data(st.session_state.patients)
                st.sidebar.success(f"✅ Created Patient — ID: {inst.patient_id}")
            else:
                inst = st.session_state.inst
                inst.set_patient_data(name, int(age), address, admit_date, "")
                save_data(st.session_state.patients)
                st.sidebar.success(f"✅ Updated Patient {inst.patient_id}")

    # -------- Bed Selection (main page) --------

    st.subheader("🛏️ Bed Selection :")

    available_beds = HospitalManagement.compute_available_beds([p.to_dict() for p in st.session_state.patients])
    bed_type = st.selectbox(
            "Select Bed Type",
            [BED_TYPES[i] for i in sorted(BED_TYPES.keys())],
            index=0
        )

    beds_for_type = available_beds.get(bed_type, []).copy()
    if st.session_state.inst and st.session_state.inst.bed_id:
            inst_bed = st.session_state.inst.bed_id
            if inst_bed.startswith(bed_type) and inst_bed not in beds_for_type:
                beds_for_type.insert(0, inst_bed)

    bed_choice = st.selectbox("Choose Bed", beds_for_type or ["No beds available"])

    if st.button("🛏️ Assign Bed"):
            inst = st.session_state.inst
            if not inst:
                st.warning("⚠️ Create or load a patient first.")
            elif bed_choice == "No beds available":
                st.warning("⚠️ No bed available for this type.")
            else:
                st.session_state.inst.set_bed_choice(bed_choice, nights)
                save_data(st.session_state.patients)
                st.success(f"✅ Assigned Bed {bed_choice} to patient {st.session_state.inst.patient_id}")

    # -------- Doctor Assignment --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("👨‍⚕️ Doctor Assignment :")

    doctor_names = [f"{d.name} ({d.specialty}) — ₹{d.fee}" for d in DOCTORS]
    doctor_display = ["(none)"] + doctor_names

    default_doc_index = 0
    if st.session_state.inst and st.session_state.inst.assigned_doctor:
        doc_str = f"{st.session_state.inst.assigned_doctor.name} ({st.session_state.inst.assigned_doctor.specialty}) — ₹{st.session_state.inst.assigned_doctor.fee}"
        if doc_str in doctor_names:
            default_doc_index = doctor_names.index(doc_str) + 1

    selected_doc = st.selectbox("Select Doctor", doctor_display, index=default_doc_index)

    if st.button("🩺 Assign Doctor"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif selected_doc == "(none)":
            st.warning("⚠️ Select a valid doctor.")
        else:
            doc_index = doctor_names.index(selected_doc)
            inst.assign_doctor(DOCTORS[doc_index].id)
            save_data(st.session_state.patients)
            st.success(f"✅ Assigned {DOCTORS[doc_index].name} to patient {inst.patient_id}")

    # -------- Treatments --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("💉 Treatments / Procedures :")
    col1, col2 = st.columns(2)
    t_values = {
        "Consultations (₹500)": col1.number_input("Consultations", min_value=0, value=0),
        "Minor Procedures (₹4000)": col1.number_input("Minor Procedures", min_value=0, value=0),
        "Major Surgeries (₹25000)": col1.number_input("Major Surgeries", min_value=0, value=0),
        "Physio Sessions (₹800)": col2.number_input("Physio Sessions", min_value=0, value=0),
        "ICU Care (₹5000)": col2.number_input("ICU Care Extras", min_value=0, value=0),
    }

    if st.button("➕ Add Treatments"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add treatments after discharge.")
        else:
            for i, qty in enumerate(t_values.values(), start=1):
                if qty:
                    inst.add_treatment_item(i, qty)
            save_data(st.session_state.patients)
            st.success(f"✅ Added Treatments | Total: ₹{inst.treatment_charge}")

    # -------- Pharmacy (two columns) --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("💊 Pharmacy Items :")
    col1, col2 = st.columns(2)
    p_values = {
        "Paracetamol (₹10)": col1.number_input("Paracetamol", min_value=0, value=0),
        "Antibiotic Course (₹400)": col1.number_input("Antibiotic Course", min_value=0, value=0),
        "Painkiller (₹50)": col1.number_input("Painkiller", min_value=0, value=0),
        "Injection (₹150)": col2.number_input("Injection", min_value=0, value=0),
        "Medicine Kit (₹700)": col2.number_input("Medicine Kit", min_value=0, value=0),
    }

    if st.button("➕ Add Pharmacy"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add medicines after discharge.")
        else:
            for i, qty in enumerate(p_values.values(), start=1):
                if qty:
                    inst.add_pharmacy_item(i, qty)
            save_data(st.session_state.patients)
            st.success(f"✅ Added Pharmacy | Total: ₹{inst.pharmacy_charge}")

    # -------- Lab Tests (two columns) --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("🧪 Lab Tests :")
    col1, col2 = st.columns(2)
    l_values = {
        "Blood Test (₹400)": col1.number_input("Blood Test", min_value=0, value=0),
        "X-Ray (₹800)": col1.number_input("X-Ray", min_value=0, value=0),
        "MRI (₹7000)": col1.number_input("MRI", min_value=0, value=0),
        "CT Scan (₹5000)": col2.number_input("CT Scan", min_value=0, value=0),
        "Ultrasound (₹1200)": col2.number_input("Ultrasound", min_value=0, value=0),
    }

    if st.button("➕ Add Lab Tests"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add lab tests after discharge.")
        else:
            for i, qty in enumerate(l_values.values(), start=1):
                if qty:
                    inst.add_lab_test(i, qty)
            save_data(st.session_state.patients)
            st.success(f"✅ Added Lab Tests | Total: ₹{inst.lab_charge}")

    # -------- Billing --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("🧾 Generate Bill :")

    # Initialize the toggle state
    if "show_bill" not in st.session_state:
        st.session_state.show_bill = False

    # Button to toggle
    if st.button("📄 Show Bill"):
        st.session_state.show_bill = not st.session_state.show_bill  # Toggle True/False

    # Conditionally display the bill
    if st.session_state.show_bill:
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        else:
            bill_text = inst.get_bill_text()
            st.text_area("Bill Summary", value=bill_text, height=400)


    # -------- Patient Management --------
    st.markdown("<hr style='border: 2px solid white'>", unsafe_allow_html=True)

    st.subheader("📋 Patient Management :")

    if st.session_state.patients:
        sel = st.selectbox(
            "Select Patient",
            [f"{p.patient_id}: {p.name}{' (DISCHARGED)' if p.discharged else ''}" for p in st.session_state.patients],
        )

        pid = int(sel.split(":")[0])
        selected = next((p for p in st.session_state.patients if p.patient_id == pid), None)

        if selected:
            # st.write(selected.get_bill_text())

            if selected.discharged:
                st.info("✅ Patient already discharged.")
            else:
                col1, col2, col3 = st.columns([1, 0.1, 1])
                with col1:
                    if st.button("Load Patient Form"):
                        st.session_state.inst = selected
                        st.session_state.sidebar_name = selected.name
                        st.session_state.sidebar_age = selected.age
                        st.session_state.sidebar_address = selected.address
                        st.session_state.sidebar_admit = selected.admit_date
                        st.rerun()

                with col3:
                    if st.button("🏁 Discharge Patient"):
                        selected.discharge(datetime.today().date())
                        save_data(st.session_state.patients)
                        st.success(f"✅ Patient {selected.patient_id} discharged successfully.")

                

    else:
        st.info("No patients found. Add a new one using the sidebar.")


if __name__ == "__main__":
    main()
